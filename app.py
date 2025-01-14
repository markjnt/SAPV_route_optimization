import os
from flask import Flask, render_template, request, jsonify, session, flash, send_file
from google.maps import routeoptimization_v1
from datetime import datetime
from backend.FileHandler import *
from backend.RouteHandler import get_start_time, get_end_time, get_date_from_week
from config import *
from io import BytesIO
import pandas as pd

# Google Cloud Service Account Authentifizierung
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = SERVICE_ACCOUNT_CREDENTIALS

app = Flask(__name__)
app.secret_key = '4c4bbaed949dc88d23335ca574e42aef00206906972c27a8015b2be0735033534'

# Globale Variable für optimierte Routen
optimized_routes = []
unassigned_tk_stops = []  # Speichert nicht zugeordnete TK-Fälle

def get_selected_weekday():
    return session.get('selected_weekday', 'Montag')

def set_selected_weekday(weekday):
    if 'selected_weekday' not in session:
        session['selected_weekday'] = 'Montag'
    else:
        session['selected_weekday'] = weekday

@app.route('/update-weekday', methods=['POST'])
def update_weekday():
    try:
        data = request.get_json()
        weekday = data.get('weekday')
        if weekday:
            set_selected_weekday(weekday)
            # Lade die Patienten für den neuen Wochentag neu
            reload_patients_for_weekday(weekday)
            return jsonify({
                'status': 'success', 
                'weekday': weekday,
                'patient_count': len(patients)
            })
        return jsonify({'status': 'error', 'message': 'No weekday provided'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

def reload_patients_for_weekday(weekday):
    """Lädt die Patienten für den angegebenen Wochentag neu"""
    global patients
    patients.clear()
    if hasattr(app, 'last_patient_upload'):
        handle_patient_upload(app.last_patient_upload, weekday)

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

@app.route('/get_markers')
def get_markers():
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
            } for v in vehicles
        ]
    })

@app.route('/patients', methods=['GET', 'POST'])
def show_patients():
    selected_weekday = get_selected_weekday()
    week_number = session.get('selected_week')
    date = get_date_from_week(week_number, selected_weekday)
    return render_template('show_patient.html',
                           patients=patients,
                           weekday=selected_weekday, week_number=week_number, date=date)

@app.route('/vehicles')
def show_vehicles():
    return render_template('show_vehicle.html', vehicles=vehicles)

@app.route('/optimize_route', methods=['POST'])
def optimize_route():
    """
    Routenoptimierung:
    - Berücksichtigt nur aktive Fahrzeuge
    - Trennung von TK und Nicht-TK Patienten
    - Flottenrouting nur für Nicht-TK
    - Berücksichtigung des Stellenumfangs als maximale Routenzeit
    - Separate Rückgabe der TK-Fälle
    """
    optimization_client = routeoptimization_v1.RouteOptimizationClient()

    # Prüfe ob Daten vorhanden
    active_vehicles = [v for v in vehicles if v.is_active]
    if not patients or not active_vehicles:
        flash('Mindestens ein Patient und ein aktives Fahrzeug benötigt.', 'error')
        return jsonify({'status': 'error'})

    # Patienten nach Besuchstyp trennen
    non_tk_patients = [p for p in patients if p.visit_type in ("Neuaufnahme", "HB")]
    tk_patients    = [p for p in patients if p.visit_type == "TK"]

    # Shipments für Nicht-TK erstellen
    shipments = []
    for patient in non_tk_patients:
        duration_seconds = 0
        if patient.visit_type == "HB":
            duration_seconds = 2100  # 35 min
        elif patient.visit_type == "Neuaufnahme":
            duration_seconds = 7200  # 120 min
        # sonst -> 0s

        pickups = [{
            "arrival_location": {
                "latitude": patient.lat,
                "longitude": patient.lon
            },
            "duration": f"{duration_seconds}s"
        }]
        shipments.append({"pickups": pickups})

    # 3) Fahrzeuge: Berücksichtige Stellenumfang
    vehicles_model = []
    for v in active_vehicles:
        stellenumfang = getattr(v, 'stellenumfang', 100)  
        
        # Berechne Sekunden (7 Stunden * Stellenumfang%)
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

    # Request zusammenstellen
    selected_weekday = get_selected_weekday()
    week_number = session.get('selected_week')
    
    fleet_routing_request = routeoptimization_v1.OptimizeToursRequest({
        "parent": "projects/routenplanung-sapv",
        "model": {
            "shipments": shipments,
            "vehicles": vehicles_model,
            "global_start_time": get_start_time(selected_weekday, week_number),
            "global_end_time": get_end_time(selected_weekday, week_number)
        }
    })

    # Aufruf der Optimierung
    try:
        response = optimization_client.optimize_tours(fleet_routing_request)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Optimierungsfehler: {str(e)}'
        })

    try:
        # Routen extrahieren
        global optimized_routes
        optimized_routes = []
        for i, route in enumerate(response.routes):
            start_dt = route.vehicle_start_time
            end_dt   = route.vehicle_end_time

            # Debug im Terminal
            if start_dt and end_dt:
                duration_sec = (end_dt - start_dt).total_seconds()
                duration_hrs = duration_sec / 3600.0
                print(f"Fahrzeug {i} => "
                      f"Start: {start_dt}, Ende: {end_dt}, "
                      f"Dauer: {duration_hrs:.2f} h, "
                      f"Name: {active_vehicles[route.vehicle_index].name}")
            else:
                duration_hrs = 0
                print(f"Fahrzeug {i} => None start/end (nicht genutzt?)")

            v_index = route.vehicle_index
            vehicle = active_vehicles[v_index]
            # Berechne max_hours basierend auf Stellenumfang (100% = 7h)
            max_hours = round((getattr(vehicle, 'stellenumfang', 100) / 100.0) * 7, 2)
            
            route_info = {
                "vehicle": vehicle.name,
                "funktion": vehicle.funktion,
                "duration_hrs": round(duration_hrs, 2),
                "max_hours": max_hours,
                "vehicle_start": {
                    "lat": vehicle.lat,
                    "lng": vehicle.lon
                },
                "stops": []
            }

            # Besuche => non_tk_patients
            for visit in route.visits:
                p_idx = visit.shipment_index
                if p_idx >= 0:
                    p = non_tk_patients[p_idx]
                    route_info["stops"].append({
                        "patient": p.name,
                        "address": p.address,
                        "visit_type": p.visit_type,
                        "time_info": p.time_info,
                        "phone_numbers": p.phone_numbers,
                        "location": {
                            "lat": p.lat,
                            "lng": p.lon
                        }
                    })

            optimized_routes.append(route_info)

        # 5) TK-Fälle als Liste
        global unassigned_tk_stops
        tk_list = [
            {
                "patient": tk.name,
                "address": tk.address,
                "visit_type": tk.visit_type,
                "time_info": tk.time_info,
                "phone_numbers": tk.phone_numbers,
                "location": {
                    "lat": tk.lat,
                    "lng": tk.lon
                }
            }
            for tk in tk_patients
        ]
        unassigned_tk_stops = tk_list

        return jsonify({
            'status': 'success',
            'routes': optimized_routes,
            'tk_patients': tk_list
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Serverfehler: {str(e)}'
        })

@app.route('/update_routes', methods=['POST'])
def update_routes():
    try:
        global optimized_routes
        global unassigned_tk_stops
        data = request.get_json()
        optimized_routes = []
        
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
        
        # Speichere die nicht zugewiesenen TK-Stopps
        unassigned_tk_stops = data.get('unassigned_tk_stops', [])
        
        return jsonify({
            'status': 'success',
            'routes': optimized_routes,
            'tk_patients': unassigned_tk_stops
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get-current-weekday')
def get_current_weekday():
    return jsonify({'weekday': get_selected_weekday()})

@app.route('/get_saved_routes')
def get_saved_routes():
    return jsonify({
        'status': 'success',
        'routes': optimized_routes,
        'tk_patients': unassigned_tk_stops
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
    """Export routes to Excel file with multiple sheets"""
    global optimized_routes
    global unassigned_tk_stops
    
    # Get selected weekday and corresponding date
    selected_weekday = get_selected_weekday()
    week_number = session.get('selected_week')
    target_date = get_date_from_week(week_number, selected_weekday)
    formatted_date = target_date.strftime("%d_%m_%Y")
    
    # Create Excel writer object
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Get workbook for formatting
        workbook = writer.book
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'border': 1,  # Add border to all sides
            'bg_color': '#f2f2f2'  # Light gray background
        })
        cell_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top'
        })
        
        # Create a sheet for each route
        for route in optimized_routes:
            vehicle_name = route['vehicle']
            
            # Separate regular stops and TK stops
            regular_stops = [stop for stop in route['stops'] if stop['visit_type'] != 'TK']
            tk_stops = [stop for stop in route['stops'] if stop['visit_type'] == 'TK']
            
            # Create DataFrame for regular stops
            regular_data = []
            for i, stop in enumerate(regular_stops, 1):
                regular_data.append({
                    'Stop-Nr': i,
                    'Patient': stop['patient'],
                    'Besuchsart': stop['visit_type'],
                    'Adresse': stop['address'],
                    'Uhrzeit/Info': stop.get('time_info', ''),
                    'Telefon': stop.get('phone_numbers', '').replace(',', '\n')
                })
            
            if regular_data or tk_stops:  # Only create sheet if there are any stops
                # Add route duration information at the top
                duration_info = pd.DataFrame([{
                    'Gesamtdauer': f"{route['duration_hrs']} / {route['max_hours']} Stunden",
                    'Funktion': route['funktion']
                }])
                
                # Write duration info
                duration_info.to_excel(writer, sheet_name=vehicle_name, index=False, startrow=0)
                
                # Get worksheet object right after creating the sheet
                worksheet = writer.sheets[vehicle_name]
                
                current_row = 3  # Start after duration info
                
                # Set column widths and formats
                column_widths = {
                    'Stop-Nr': 15,
                    'Patient': 25,
                    'Besuchsart': 25,
                    'Adresse': 35,
                    'Uhrzeit/Info': 20,
                    'Telefon': 20
                }
                
                # Write regular stops if any
                if regular_data:
                    regular_df = pd.DataFrame(regular_data)
                    
                    # Write "Hausbesuche" header with format
                    hb_section_header = workbook.add_format({
                        'bold': True,
                        'font_size': 14,
                        'align': 'center',
                        'valign': 'vcenter'
                    })
                    # Merge cells for the section header
                    worksheet.merge_range(current_row, 0, current_row, 5, 'Hausbesuche', hb_section_header)
                    current_row += 1
                    
                    # Write column headers
                    for idx, (col, width) in enumerate(column_widths.items()):
                        worksheet.write(current_row, idx, col, header_format)
                    current_row += 1
                    
                    # Write regular data without headers
                    for row_idx, row_data in enumerate(regular_data):
                        for col_idx, (key, value) in enumerate(row_data.items()):
                            worksheet.write(current_row + row_idx, 
                                         col_idx, 
                                         value, 
                                         cell_format)
                    current_row += len(regular_data) + 2  # Add 2 for spacing
                
                # Write TK stops if any
                if tk_stops:
                    # Create DataFrame for TK stops with correct column order
                    tk_data = []
                    for stop in tk_stops:
                        tk_data.append({
                            'Patient': stop['patient'],
                            'Besuchsart': 'TK',
                            'Adresse': stop['address'],
                            'Uhrzeit/Info': stop.get('time_info', ''),
                            'Telefon': stop.get('phone_numbers', '').replace(',', '\n')
                        })
                    
                    # Write "Telefonkontakte" header with format
                    tk_section_header = workbook.add_format({
                        'bold': True,
                        'font_size': 14,
                        'align': 'center',
                        'valign': 'vcenter'
                    })
                    # Merge cells for the section header
                    worksheet.merge_range(current_row, 0, current_row, 4, 'Telefonkontakte', tk_section_header)
                    current_row += 1
                    
                    # Define TK columns and their order
                    tk_columns = ['Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']
                    
                    # Write column headers
                    for idx, col in enumerate(tk_columns):
                        worksheet.write(current_row, idx, col, header_format)
                    current_row += 1
                    
                    # Write TK data in correct order
                    for row_idx, data in enumerate(tk_data):
                        for col_idx, col in enumerate(tk_columns):
                            worksheet.write(current_row + row_idx, 
                                         col_idx, 
                                         data[col], 
                                         cell_format)
                
                # Format all columns
                for idx, (col, width) in enumerate(column_widths.items()):
                    worksheet.set_column(idx, idx, width, cell_format)
                
                # Set row height for all rows to accommodate wrapped text
                max_row = current_row + (len(tk_data) if tk_stops else 0)
                for row in range(4, max_row + 2):
                    worksheet.set_row(row, 30)

        # Add unassigned TK cases to separate sheet if any exist
        if unassigned_tk_stops:
            tk_data = [{
                'Patient': stop['patient'],
                'Besuchsart': 'TK',
                'Adresse': stop['address'],
                'Uhrzeit/Info': stop.get('time_info', ''),
                'Telefon': stop.get('phone_numbers', '').replace(',', '\n')
            } for stop in unassigned_tk_stops]
            
            # Create empty sheet
            worksheet = workbook.add_worksheet('Nicht zugeordnete TK')
            current_row = 0  # Start from top
            
            # Write "Telefonkontakte" header with format
            tk_section_header = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'center',
                'valign': 'vcenter'
            })
            # Merge cells for the section header
            worksheet.merge_range(current_row, 0, current_row, 4, 'Nicht zugeordnete Telefonkontakte', tk_section_header)
            current_row += 1
            
            # Define TK columns and their order
            tk_columns = ['Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']
            
            # Write column headers
            for idx, col in enumerate(tk_columns):
                worksheet.write(current_row, idx, col, header_format)
            current_row += 1
            
            # Write TK data in correct order
            for row_idx, data in enumerate(tk_data):
                for col_idx, col in enumerate(tk_columns):
                    worksheet.write(current_row + row_idx, 
                                 col_idx, 
                                 data[col], 
                                 cell_format)
            
            # Set column widths
            column_widths = {
                'Patient': 25,
                'Besuchsart': 12,
                'Adresse': 35,
                'Uhrzeit/Info': 20,
                'Telefon': 20
            }
            
            # Format columns
            for idx, (col, width) in enumerate(column_widths.items()):
                worksheet.set_column(idx, idx, width, cell_format)
            
            # Set row height for all rows
            max_row = current_row + len(tk_data)
            for row in range(1, max_row + 1):
                worksheet.set_row(row, 30)

    # Prepare the file for sending
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'Optimierte_Routen_{formatted_date}_{selected_weekday}.xlsx'
    )

if __name__ == '__main__':
    app.run(debug=True)
