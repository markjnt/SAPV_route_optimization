from flask import flash, redirect, url_for, current_app as app
from services.file_service import FileService

file_service = FileService()

def handle_patient_upload(request, selected_weekday=None):
    # Handler für den Upload von Patientendaten
    if request.method != 'POST':
        flash('Keine Patientendatei ausgewählt.')
        return redirect(url_for('main.upload_file'))

    if 'patient_file' not in request.files:
        flash('Keine Patientendatei ausgewählt.')
        return redirect(url_for('main.upload_file'))

    file = request.files['patient_file']
    if file.filename == '':
        flash('Keine Patientendatei ausgewählt.')
        return redirect(url_for('main.upload_file'))

    if not file_service.allowed_file(file.filename):
        flash('Nur Excel-Dateien sind erlaubt.')
        return redirect(url_for('main.upload_file'))

    try:
        result = file_service.process_patient_file(file, selected_weekday)
        flash(result['message'])
        if result['success']:
            return redirect(url_for('main.show_patients'))
    except Exception as e:
        flash(f'Fehler beim Verarbeiten der Patientendatei: {str(e)}')
    
    return redirect(url_for('main.upload_file'))

def handle_vehicle_upload(request):
    # Handler für den Upload von Fahrzeugdaten
    if request.method != 'POST':
        flash('Keine Mitarbeiterdatei ausgewählt.')
        return redirect(url_for('main.upload_file'))

    if 'vehicle_file' not in request.files:
        flash('Keine Mitarbeiterdatei ausgewählt.')
        return redirect(url_for('main.upload_file'))

    file = request.files['vehicle_file']
    if file.filename == '':
        flash('Keine Mitarbeiterdatei ausgewählt.')
        return redirect(url_for('main.upload_file'))

    if not file_service.allowed_file(file.filename):
        flash('Nur Excel-Dateien sind erlaubt.')
        return redirect(url_for('main.upload_file'))

    try:
        result = file_service.process_vehicle_file(file)
        flash(result['message'])
        if result['success']:
            return redirect(url_for('main.show_vehicles'))
    except Exception as e:
        flash(f'Fehler beim Verarbeiten der Mitarbeiterdatei: {str(e)}')
    
    return redirect(url_for('main.upload_file'))

def geocode_address(address):
    # Handler für die Geocodierung einer Adresse
    return file_service.geocode_address(address)

def allowed_file(filename):
    # Handler für die Überprüfung der Dateiendung
    return file_service.allowed_file(filename) 