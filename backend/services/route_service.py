from google.maps import routeoptimization_v1
from services.date_time_service import DateTimeService
from models import patients, vehicles
from config import Config

class RouteOptimizationService:
    def __init__(self, project_id=Config.GOOGLE_PROJECT_ID):
        self.project_id = project_id
        self.client = routeoptimization_v1.RouteOptimizationClient()

    def optimize_routes(self, non_tk_patients, available_vehicles, selected_weekday, week_number):
        # Optimiert die Routen für die gegebenen Patienten und Fahrzeuge
        
        # Erstellt Lieferungen für Hausbesuche
        shipments = self._create_shipments(non_tk_patients)
        
        # Erstellt Fahrzeugmodelle
        vehicles_model = self._create_vehicle_models(available_vehicles)
        
        # Erstellt und sendet die Optimierungsanfrage
        request = routeoptimization_v1.OptimizeToursRequest({
            "parent": f"projects/{self.project_id}",
            "model": {
                "shipments": shipments,
                "vehicles": vehicles_model,
                "global_start_time": DateTimeService.get_start_time(selected_weekday, week_number),
                "global_end_time": DateTimeService.get_end_time(selected_weekday, week_number)
            },
            "consider_road_traffic": True
        })
        
        return self.client.optimize_tours(request)

    def _create_shipments(self, patients):
        # Erstellt Lieferungsmuster für Patienten
        shipments = []
        for patient in patients:
            duration_seconds = self._get_visit_duration(patient.visit_type)
            pickups = [{
                "arrival_location": {
                    "latitude": patient.lat,
                    "longitude": patient.lon
                },
                "duration": f"{duration_seconds}s"
            }]
            shipments.append({"pickups": pickups})
        return shipments

    def _create_vehicle_models(self, vehicles):
        # Erstellt Fahrzeugmodelle für die Optimierung
        vehicles_model = []
        for v in vehicles:
            stellenumfang = getattr(v, 'stellenumfang', 100)
            # Basis-Sekunden aus Stellenumfang (7h = 25200s bei 100%)
            base_seconds = int((stellenumfang / 100.0) * 7 * 3600)
            # Hard cap: Basis + 30 Minuten
            hard_cap_seconds = base_seconds + (30 * 60)
            
            vehicle_model = {
                "start_location": {
                    "latitude": v.lat,
                    "longitude": v.lon
                },
                "end_location": {
                    "latitude": v.lat,
                    "longitude": v.lon
                },
                "cost_per_hour": 1,
                "route_duration_limit": {
                    "max_duration": f"{hard_cap_seconds}s",
                    "soft_max_duration": f"{base_seconds}s",
                    "cost_per_hour_after_soft_max": 2  # Doppelte Kosten nach Überschreitung des Soft Caps
                }
            }
            vehicles_model.append(vehicle_model)
        return vehicles_model

    def _get_visit_duration(self, visit_type):
        # Gibt die Dauer in Sekunden für einen Besuchstyp zurück
        durations = {
            "HB": 1200,  # 20 min
            "NA": 7200  # 120 min
        }
        return durations.get(visit_type, 0)

    def process_optimization_result(self, response, available_vehicles, all_active_vehicles, non_tk_patients, tk_patients):
        # Verarbeitet die Optimierungsergebnisse und erstellt die Antwort
        optimized_routes = []
        
        # Erstellt leere Container für alle aktiven Fahrzeuge
        for vehicle in all_active_vehicles:
            max_hours = round((getattr(vehicle, 'stellenumfang', 100) / 100.0) * 7, 2)
            optimized_routes.append({
                "vehicle": vehicle.name,
                "funktion": vehicle.funktion,
                "duration_hrs": 0,
                "max_hours": max_hours,
                "vehicle_start": {"lat": vehicle.lat, "lng": vehicle.lon},
                "stops": []
            })
        
        # Verarbeitet die Optimierungsergebnisse
        for i, route in enumerate(response.routes):
            if route.vehicle_start_time and route.vehicle_end_time:
                duration_hrs = (route.vehicle_end_time - route.vehicle_start_time).total_seconds() / 3600.0
            else:
                duration_hrs = 0
                
            vehicle = available_vehicles[route.vehicle_index]
            route_container = next(r for r in optimized_routes if r["vehicle"] == vehicle.name)
            route_container["duration_hrs"] = round(duration_hrs, 2)
            
            # Fügt Besuche zur Route hinzu
            for visit in route.visits:
                if visit.shipment_index >= 0:
                    p = non_tk_patients[visit.shipment_index]
                    route_container["stops"].append({
                        "patient": p.name,
                        "address": p.address,
                        "visit_type": p.visit_type,
                        "time_info": p.time_info,
                        "phone_numbers": p.phone_numbers,
                        "location": {"lat": p.lat, "lng": p.lon}
                    })
        
        # Finde unzugewiesene Hausbesuche
        unassigned_regular_stops = self.get_unassigned_stops(non_tk_patients, optimized_routes)
        
        # Finde unzugewiesene Telefonkontakte
        unassigned_tk_stops = [{
            "patient": tk.name,
            "address": tk.address,
            "visit_type": tk.visit_type,
            "time_info": tk.time_info,
            "phone_numbers": tk.phone_numbers,
            "location": {"lat": tk.lat, "lng": tk.lon}
        } for tk in tk_patients]
        
        return optimized_routes, unassigned_regular_stops, unassigned_tk_stops

    def validate_optimization_input(self, vehicles, patients):
        # Validiert die Eingabedaten für die Optimierung
        has_active_nurses = any(v.is_active and v.funktion == 'Pflegekraft' for v in vehicles)
        if not has_active_nurses:
            return False, 'Es muss mindestens eine aktive Pflegekraft verfügbar sein.'
        
        if not patients:
            return False, 'Es muss mindestens ein Patient vorhanden sein.'
        
        return True, None 

    def get_unassigned_stops(self, non_tk_patients, optimized_routes):
        # Vergleicht die eingegebenen Patienten mit den zugewiesenen Patienten aus den optimierten Routen und gibt die nicht zugewiesenen Patienten zurück.

        # Sammle alle zugewiesenen Patienten
        assigned_patients = set()
        for route in optimized_routes:
            for stop in route['stops']:
                assigned_patients.add(stop['patient'])
        
        # Finde unzugewiesene Patienten
        input_patient_names = {p.name for p in non_tk_patients}
        unassigned_patient_names = input_patient_names - assigned_patients
        
        # Erstelle Liste der unzugewiesenen Patienten
        unassigned_regular_stops = [
            {
                "patient": p.name,
                "address": p.address,
                "visit_type": p.visit_type,
                "time_info": p.time_info,
                "phone_numbers": p.phone_numbers,
                "location": {"lat": p.lat, "lng": p.lon}
            }
            for p in non_tk_patients
            if p.name in unassigned_patient_names
        ]
        
        return unassigned_regular_stops 