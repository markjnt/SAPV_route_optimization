from flask import Blueprint, render_template, request, jsonify, flash, send_file
from backend.services.pdf_service import create_route_pdf
from backend.services.date_time_service import DateTimeService
from backend.handlers import handle_patient_upload, handle_vehicle_upload
from backend.models import patients, vehicles
from config import GOOGLE_MAPS_API_KEY
from backend.services.route_service import RouteOptimizationService
from backend.services.session_service import SessionService
import logging

logger = logging.getLogger(__name__)

# Blueprint erstellen
routes = Blueprint('main', __name__)

# Services initialisieren
route_optimization_service = RouteOptimizationService()
session_service = SessionService()

# Globale Variablen für optimierte Routen
optimized_routes = []
unassigned_tk_stops = []
unassigned_regular_stops = []

@routes.route('/', methods=['GET', 'POST'])
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

@routes.route('/update-weekday', methods=['POST'])
def update_weekday():
    try:
        data = request.get_json()
        weekday = data.get('weekday')
        if weekday:
            session_service.set_selected_weekday(weekday)
            return jsonify({
                'status': 'success', 
                'weekday': weekday,
                'patient_count': len(patients)
            })
        return jsonify({'status': 'error', 'message': 'No weekday provided'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@routes.route('/optimize_route', methods=['POST'])
def optimize_route():
    try:
        logger.info("Starting route optimization")
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

        # Optimierung durchführen mit nur Pflegekräften
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
        logger.error(f"Error during optimization: {e}")
        raise

@routes.route('/get_markers')
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

@routes.route('/patients', methods=['GET', 'POST'])
def show_patients():
    selected_weekday = session_service.get_selected_weekday()
    week_number = session_service.get_selected_week()
    date = DateTimeService.get_date_from_week(week_number, selected_weekday)
    return render_template('show_patient.html',
                         patients=patients,
                         weekday=selected_weekday, week_number=week_number, date=date)

@routes.route('/vehicles')
def show_vehicles():
    return render_template('show_vehicle.html', vehicles=vehicles)

@routes.route('/update_routes', methods=['POST'])
def update_routes():
    try:
        data = request.get_json()
        optimized_routes, unassigned_tk_stops, unassigned_regular_stops = route_optimization_service.process_optimization_result(
            data.get('optimized_routes', []),
            data.get('unassigned_tk_stops', []),
            data.get('unassigned_regular_stops', [])
        )
        
        return jsonify({
            'status': 'success',
            'routes': optimized_routes,
            'tk_patients': unassigned_tk_stops,
            'regular_stops': unassigned_regular_stops
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@routes.route('/get-current-weekday')
def get_current_weekday():
    return jsonify({'weekday': session_service.get_selected_weekday()})

@routes.route('/get_saved_routes')
def get_saved_routes():
    return jsonify({
        'status': 'success',
        'routes': optimized_routes,
        'tk_patients': unassigned_tk_stops,
        'regular_stops': unassigned_regular_stops
    })

@routes.route('/update_vehicle_selection', methods=['POST'])
def update_vehicle_selection():
    try:
        data = request.get_json()
        vehicle_updates = data.get('vehicles', [])
        
        for update in vehicle_updates:
            vehicle_id = update.get('id')
            is_active = update.get('active')
            
            for vehicle in vehicles:
                if vehicle.id == vehicle_id:
                    vehicle.is_active = is_active
                    break
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@routes.route('/export_routes', methods=['GET'])
def export_routes():
    selected_weekday = session_service.get_selected_weekday()
    week_number = session_service.get_selected_week()
    target_date = DateTimeService.get_date_from_week(week_number, selected_weekday)
    formatted_date = target_date.strftime("%d_%m_%Y")
    
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

@routes.errorhandler(Exception)
def handle_error(error):
    return jsonify({'status': 'error', 'message': str(error)}), 500 