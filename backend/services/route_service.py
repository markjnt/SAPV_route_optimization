from google.maps import routeoptimization_v1
from datetime import datetime
from backend.handlers.date_time_handler import get_start_time, get_end_time
from backend.models import patients, vehicles

class RouteOptimizationService:
    def __init__(self, project_id="routenplanung-sapv"):
        self.project_id = project_id
        self.client = routeoptimization_v1.RouteOptimizationClient()

    def optimize_routes(self, non_tk_patients, available_vehicles, selected_weekday, week_number):
        """Optimiert die Routen für die gegebenen Patienten und Fahrzeuge"""
        
        # Create shipments for non-TK patients
        shipments = self._create_shipments(non_tk_patients)
        
        # Create vehicle models
        vehicles_model = self._create_vehicle_models(available_vehicles)
        
        # Create and send optimization request
        request = routeoptimization_v1.OptimizeToursRequest({
            "parent": f"projects/{self.project_id}",
            "model": {
                "shipments": shipments,
                "vehicles": vehicles_model,
                "global_start_time": get_start_time(selected_weekday, week_number),
                "global_end_time": get_end_time(selected_weekday, week_number)
            }
        })
        
        return self.client.optimize_tours(request)

    def _create_shipments(self, patients):
        """Creates shipment models for patients"""
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
        """Creates vehicle models for the optimization"""
        vehicles_model = []
        for v in vehicles:
            stellenumfang = getattr(v, 'stellenumfang', 100)
            seconds = int((stellenumfang / 100.0) * 7 * 3600)
            
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
                    "max_duration": f"{seconds}s"
                }
            }
            vehicles_model.append(vehicle_model)
        return vehicles_model

    def _get_visit_duration(self, visit_type):
        """Returns the duration in seconds for a visit type"""
        durations = {
            "HB": 2100,  # 35 min
            "Neuaufnahme": 7200  # 120 min
        }
        return durations.get(visit_type, 0)

    def process_optimization_result(self, response, available_vehicles, all_active_vehicles, non_tk_patients, tk_patients):
        """Processes the optimization result and creates the response"""
        optimized_routes = []
        
        # Create empty containers for all active vehicles
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
        
        # Process optimization response
        for i, route in enumerate(response.routes):
            if route.vehicle_start_time and route.vehicle_end_time:
                duration_hrs = (route.vehicle_end_time - route.vehicle_start_time).total_seconds() / 3600.0
            else:
                duration_hrs = 0
                
            vehicle = available_vehicles[route.vehicle_index]
            route_container = next(r for r in optimized_routes if r["vehicle"] == vehicle.name)
            route_container["duration_hrs"] = round(duration_hrs, 2)
            
            # Add visits to route
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
        
        # Process TK patients
        unassigned_tk_stops = [{
            "patient": tk.name,
            "address": tk.address,
            "visit_type": tk.visit_type,
            "time_info": tk.time_info,
            "phone_numbers": tk.phone_numbers,
            "location": {"lat": tk.lat, "lng": tk.lon}
        } for tk in tk_patients]
        
        return optimized_routes, unassigned_tk_stops

    def validate_optimization_input(self, vehicles, patients):
        """Validates the input data for optimization"""
        has_active_nurses = any(v.is_active and v.funktion == 'Pflegekraft' for v in vehicles)
        if not has_active_nurses:
            return False, 'Es muss mindestens eine aktive Pflegekraft verfügbar sein.'
        
        if not patients:
            return False, 'Es muss mindestens ein Patient vorhanden sein.'
        
        return True, None 