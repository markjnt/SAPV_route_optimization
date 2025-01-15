import os
from flask import Flask, render_template, request, jsonify, flash, send_file
from backend.handlers import (
    handle_patient_upload, 
    handle_vehicle_upload,
    reload_patients_for_weekday
)
from backend.services.pdf_service import create_route_pdf
from backend.services.route_service import RouteOptimizationService
from backend.services.session_service import SessionService
from backend.models import patients, vehicles
from config import *
from backend.services.date_time_service import DateTimeService

# Google Cloud Service Account Authentifizierung
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = SERVICE_ACCOUNT_CREDENTIALS

app = Flask(__name__)
app.secret_key = '4c4bbaed949dc88d23335ca574e42aef00206906972c27a8015b2be0735033534'

# Services initialisieren
route_optimization_service = RouteOptimizationService()
session_service = SessionService()

# Globale Variablen für optimierte Routen
optimized_routes = []
unassigned_tk_stops = []
unassigned_regular_stops = []

@app.route('/update-weekday', methods=['POST'])
def update_weekday():
    try:
        data = request.get_json()
        weekday = data.get('weekday')
        if weekday:
            session_service.set_selected_weekday(weekday)
            reload_patients_for_weekday(weekday)
            return jsonify({
                'status': 'success', 
                'weekday': weekday,
                'patient_count': len(patients)
            })
        return jsonify({'status': 'error', 'message': 'No weekday provided'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        upload_type = request.form.get('upload_type')
        if upload_type == 'patients':
            return handle_patient_upload(request)
        elif upload_type == 'vehicles':
            return handle_vehicle_upload(request)

    return render_template(
        'index.html',
        patients=patients,
        vehicles=vehicles,
        google_maps_api_key=GOOGLE_MAPS_API_KEY,
        saved_routes=optimized_routes
    )

@app.route('/optimize_route', methods=['POST'])
def optimize_route():
    try:
        # Validierung
        is_valid, error_message = route_optimization_service.validate_optimization_input(vehicles, patients)
        if not is_valid:
            flash(error_message, 'error')
            return jsonify({'status': 'error', 'message': error_message})

        # Fahrzeuge und Patienten filtern
        available_vehicles = [v for v in vehicles if v.is_active and v.funktion == 'Pflegekraft']
        all_active_vehicles = [v for v in vehicles if v.is_active]
        non_tk_patients = [p for p in patients if p.visit_type in ("Neuaufnahme", "HB")]
        tk_patients = [p for p in patients if p.visit_type == "TK"]

        # Optimierung durchführen
        response = route_optimization_service.optimize_routes(
            non_tk_patients,
            available_vehicles,
            session_service.get_selected_weekday(),
            session_service.get_selected_week()
        )

        # Ergebnis verarbeiten
        global optimized_routes, unassigned_tk_stops, unassigned_regular_stops
        optimized_routes, unassigned_regular_stops, unassigned_tk_stops = route_optimization_service.process_optimization_result(
            response,
            available_vehicles,
            all_active_vehicles,
            non_tk_patients,
            tk_patients
        )

        return jsonify({
            'status': 'success',
            'routes': optimized_routes,
            'tk_patients': unassigned_tk_stops,
            'regular_stops': unassigned_regular_stops
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get_markers')
def get_markers():
    # Hole aktive Vehicles
    all_active_vehicles = [v for v in vehicles if v.is_active]
    
    return jsonify({
        'patients': [
            {
                'name': p.name,
                'address': p.address,
                'lat': p.lat,
                'lng': p.lon,
                'visit_type': p.visit_type
            } for p in patients
        ],
        'vehicles': [
            {
                'name': v.name,
                'start_address': v.start_address,
                'lat': v.lat,
                'lng': v.lon,
                'funktion': v.funktion
            } for v in all_active_vehicles
        ]
    })

@app.route('/patients', methods=['GET', 'POST'])
def show_patients():
    selected_weekday = session_service.get_selected_weekday()
    week_number = session_service.get_selected_week()
    date = DateTimeService.get_date_from_week(week_number, selected_weekday)
    return render_template('show_patient.html',
                           patients=patients,
                           weekday=selected_weekday, week_number=week_number, date=date)

@app.route('/vehicles')
def show_vehicles():
    return render_template('show_vehicle.html', vehicles=vehicles)

@app.route('/update_routes', methods=['POST'])
def update_routes():
    try:
        global optimized_routes, unassigned_tk_stops, unassigned_regular_stops
        data = request.get_json()
        optimized_routes = []
        unassigned_tk_stops = data.get('unassigned_tk_stops', [])
        unassigned_regular_stops = data.get('unassigned_regular_stops', [])
        
        # Alle aktiven Mitarbeiter berücksichtigen
        active_vehicles = [v for v in vehicles if v.is_active]
        
        # Reguläre Routen verarbeiten
        for route in data.get('optimized_routes', []):
            if route['vehicle'] != 'tk':
                vehicle = next((v for v in active_vehicles if v.name == route['vehicle']), None)
                if vehicle:
                    route_info = {
                        'vehicle': route['vehicle'],
                        'duration_hrs': route['duration_hrs'],
                        'max_hours': route['max_hours'],
                        'funktion': route['funktion'],
                        'vehicle_start': {
                            'lat': vehicle.lat,
                            'lng': vehicle.lon
                        },
                        'stops': route['stops']
                    }
                    optimized_routes.append(route_info)
        
        return jsonify({
            'status': 'success',
            'routes': optimized_routes,
            'tk_patients': unassigned_tk_stops,
            'regular_stops': unassigned_regular_stops
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get-current-weekday')
def get_current_weekday():
    return jsonify({'weekday': session_service.get_selected_weekday()})

@app.route('/get_saved_routes')
def get_saved_routes():
    return jsonify({
        'status': 'success',
        'routes': optimized_routes,
        'tk_patients': unassigned_tk_stops,
        'regular_stops': unassigned_regular_stops
    })

@app.route('/update_vehicle_selection', methods=['POST'])
def update_vehicle_selection():
    try:
        data = request.get_json()
        vehicle_updates = data.get('vehicles', [])
        
        # Update vehicle active status
        for update in vehicle_updates:
            vehicle_id = update.get('id')
            is_active = update.get('active')
            
            # Finde das entsprechende Fahrzeug und aktualisiere den Status
            for vehicle in vehicles:
                if vehicle.id == vehicle_id:
                    vehicle.is_active = is_active
                    break
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/export_routes', methods=['GET'])
def export_routes():
    """Export routes to PDF file"""
    selected_weekday = session_service.get_selected_weekday()
    week_number = session_service.get_selected_week()
    target_date = DateTimeService.get_date_from_week(week_number, selected_weekday)
    formatted_date = target_date.strftime("%d_%m_%Y")
    
    # Create PDF using the service
    output = create_route_pdf(
        optimized_routes,
        unassigned_tk_stops,
        unassigned_regular_stops,
        selected_weekday,
        formatted_date
    )
    
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Optimierte_Routen_{formatted_date}_{selected_weekday}.pdf'
    )

if __name__ == '__main__':
    app.run(debug=True)
