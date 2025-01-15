from backend.services.file_service import FileHandlerService
from backend.models import patients, vehicles
from flask import current_app as app

file_handler_service = FileHandlerService()

def handle_patient_upload(request, selected_weekday=None):
    return file_handler_service.handle_patient_upload(request, selected_weekday)

def handle_vehicle_upload(request):
    return file_handler_service.handle_vehicle_upload(request)

def geocode_address(address):
    return file_handler_service.geocode_address(address)

def allowed_file(filename):
    return file_handler_service.allowed_file(filename)

def reload_patients_for_weekday(weekday):
    """Lädt die Patienten für den angegebenen Wochentag neu"""
    return file_handler_service.reload_patients_for_weekday(app, weekday) 