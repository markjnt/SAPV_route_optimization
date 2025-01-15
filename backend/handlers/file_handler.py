from flask import flash, redirect
from backend.services.file_service import FileHandlerService

class FileHandler:
    def __init__(self):
        self.file_service = FileHandlerService()
    
    def handle_upload(self, request, upload_type):
        """
        Zentrale Methode für File-Upload-Handling
        """
        try:
            if 'file' not in request.files:
                flash('Keine Datei ausgewählt')
                return redirect(request.url)
                
            file = request.files['file']
            if file.filename == '':
                flash('Keine Datei ausgewählt')
                return redirect(request.url)
                
            if not self.file_service.allowed_file(file.filename):
                flash('Nicht unterstütztes Dateiformat')
                return redirect(request.url)
                
            if upload_type == 'patients':
                return self.handle_patient_upload(request)
            elif upload_type == 'vehicles':
                return self.handle_vehicle_upload(request)
                
        except Exception as e:
            flash(f'Fehler beim Upload: {str(e)}')
            return redirect(request.url)
    
    def handle_patient_upload(self, request):
        """
        Spezielle Logik für Patienten-Upload
        """
        selected_weekday = request.form.get('weekday')
        return self.file_service.handle_patient_upload(request, selected_weekday)
    
    def handle_vehicle_upload(self, request):
        """
        Spezielle Logik für Fahrzeug-Upload
        """
        return self.file_service.handle_vehicle_upload(request) 