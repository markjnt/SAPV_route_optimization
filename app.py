import os
from flask import Flask, render_template, request, jsonify, session, flash, send_file
from google.maps import routeoptimization_v1
from datetime import datetime
from backend.FileHandler import *
from backend.RouteHandler import get_start_time, get_end_time, get_date_from_week
from config import *
from io import BytesIO
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm

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
    try:
        # Nur aktive Pflegekräfte für die initiale Optimierung verwenden
        available_vehicles = [v for v in vehicles if v.is_active and v.funktion == 'Pflegekraft']
        
        # Alle aktiven Mitarbeiter für die Container-Erstellung
        all_active_vehicles = [v for v in vehicles if v.is_active]
        
        if not available_vehicles:
            return jsonify({
                'status': 'error',
                'message': 'Keine aktiven Pflegekräfte verfügbar.'
            })

        optimization_client = routeoptimization_v1.RouteOptimizationClient()

        # Prüfe ob Daten vorhanden
        if not patients or not available_vehicles:
            flash('Mindestens ein Patient und eine aktive Pflegekraft benötigt.', 'error')
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
        for v in available_vehicles:
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
            
            # Zuerst leere Container für alle aktiven Mitarbeiter erstellen
            for vehicle in all_active_vehicles:
                max_hours = round((getattr(vehicle, 'stellenumfang', 100) / 100.0) * 7, 2)
                route_info = {
                    "vehicle": vehicle.name,
                    "funktion": vehicle.funktion,
                    "duration_hrs": 0,
                    "max_hours": max_hours,
                    "vehicle_start": {
                        "lat": vehicle.lat,
                        "lng": vehicle.lon
                    },
                    "stops": []
                }
                optimized_routes.append(route_info)
            
            # Dann die optimierten Routen den entsprechenden Pflegekräften zuweisen
            for i, route in enumerate(response.routes):
                start_dt = route.vehicle_start_time
                end_dt = route.vehicle_end_time

                if start_dt and end_dt:
                    duration_sec = (end_dt - start_dt).total_seconds()
                    duration_hrs = duration_sec / 3600.0
                    print(f"Fahrzeug {i} => "
                          f"Start: {start_dt}, Ende: {end_dt}, "
                          f"Dauer: {duration_hrs:.2f} h, "
                          f"Name: {available_vehicles[route.vehicle_index].name}")
                else:
                    duration_hrs = 0
                    print(f"Fahrzeug {i} => None start/end (nicht genutzt?)")

                v_index = route.vehicle_index
                vehicle = available_vehicles[v_index]
                
                # Finde den entsprechenden Container in optimized_routes
                route_container = next(r for r in optimized_routes if r["vehicle"] == vehicle.name)
                route_container["duration_hrs"] = round(duration_hrs, 2)

                # Besuche => non_tk_patients
                for visit in route.visits:
                    p_idx = visit.shipment_index
                    if p_idx >= 0:
                        p = non_tk_patients[p_idx]
                        route_container["stops"].append({
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

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/update_routes', methods=['POST'])
def update_routes():
    try:
        global optimized_routes
        global unassigned_tk_stops
        data = request.get_json()
        optimized_routes = []
        
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

def create_maps_url(address):
    """Create Google Maps URL for direct navigation"""
    base_url = "https://www.google.com/maps/dir/?api=1&destination="
    # Return link format for PDF instead of Excel
    return f'<link href="{base_url}{address.replace(" ", "+")}">{address}</link>'

@app.route('/export_routes', methods=['GET'])
def export_routes():
    """Export routes to PDF file"""
    global optimized_routes
    global unassigned_tk_stops
    
    # Get date information
    selected_weekday = get_selected_weekday()
    week_number = session.get('selected_week')
    target_date = get_date_from_week(week_number, selected_weekday)
    formatted_date = target_date.strftime("%d_%m_%Y")
    
    # Create PDF in memory
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm,
        title="SAPV Routenplanung",
        author="SAPV Oberberg",
        subject=f"Routen für {selected_weekday}, {formatted_date}",
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=20,
        alignment=1  # Center alignment
    )
    
    # Container for PDF elements
    elements = []
    
    # Create tables for each route
    for i, route in enumerate(optimized_routes):
        # Add PageBreak if not first route
        if i > 0:
            elements.append(PageBreak())
            
        vehicle_name = route['vehicle']
        
        # Add vehicle name and duration info
        elements.append(Paragraph(f"{vehicle_name}", title_style))
        elements.append(Paragraph(
            f"Gesamtdauer: {route['duration_hrs']} / {route['max_hours']} Stunden - {route['funktion']}",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))
        
        # Regular stops
        regular_stops = [stop for stop in route['stops'] if stop['visit_type'] != 'TK']
        if regular_stops:
            elements.append(Paragraph("Hausbesuche", title_style))
            
            # Table header
            data = [['Nr.', 'Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']]
            
            # Add stops to table
            for i, stop in enumerate(regular_stops, 1):
                data.append([
                    str(i),
                    stop['patient'],
                    stop['visit_type'],
                    Paragraph(create_maps_url(stop['address']), styles['Normal']),
                    stop.get('time_info', ''),
                    stop.get('phone_numbers', '').replace(',', '\n')
                ])
            
            # Create and style table
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 20))
        
        # TK stops
        tk_stops = [stop for stop in route['stops'] if stop['visit_type'] == 'TK']
        if tk_stops:
            elements.append(Paragraph("Telefonkontakte", title_style))
            
            # Table header
            data = [['Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']]
            
            # Add TK stops to table
            for stop in tk_stops:
                data.append([
                    stop['patient'],
                    'TK',
                    Paragraph(create_maps_url(stop['address']), styles['Normal']),
                    stop.get('time_info', ''),
                    stop.get('phone_numbers', '').replace(',', '\n')
                ])
            
            # Create and style table
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(table)
    
    # Add unassigned TK cases if any
    if unassigned_tk_stops:
        # Add PageBreak before unassigned TK cases
        elements.append(PageBreak())
        
        elements.append(Paragraph("Nicht zugeordnete Telefonkontakte", title_style))
        
        # Table header
        data = [['Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']]
        
        # Add unassigned TK stops
        for stop in unassigned_tk_stops:
            data.append([
                stop['patient'],
                'TK',
                Paragraph(create_maps_url(stop['address']), styles['Normal']),
                stop.get('time_info', ''),
                stop.get('phone_numbers', '').replace(',', '\n')
            ])
        
        # Create and style table
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(table)
    
    # Build PDF
    doc.build(elements)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Optimierte_Routen_{formatted_date}_{selected_weekday}.pdf'
    )

if __name__ == '__main__':
    app.run(debug=True)
