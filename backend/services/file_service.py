from flask import flash, redirect, url_for
import pandas as pd
import os
from werkzeug.utils import secure_filename
import googlemaps
from backend.models import Patient, Vehicle, patients, vehicles
from config import GOOGLE_MAPS_API_KEY

ALLOWED_EXTENSIONS = {'xlsx'}

class FileHandlerService:
    def __init__(self):
        self.gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

    def handle_patient_upload(self, request, selected_weekday=None):
        """Verarbeitet den Upload einer Patientendatei"""
        try:
            file = request.files['file']
            if file and self.allowed_file(file.filename):
                # Excel-Datei einlesen
                df = pd.read_excel(file)
                
                # Patientenliste leeren
                patients.clear()
                
                # Neue Patienten hinzufügen
                for _, row in df.iterrows():
                    address = f"{row['Straße']}, {row['PLZ']} {row['Ort']}"
                    lat, lon = self.geocode_address(address)
                    
                    patient = Patient(
                        name=f"{row['Name']}, {row['Vorname']}",
                        address=address,
                        visit_type=row['Besuchsart'],
                        time_info=row.get('Uhrzeit/Info', ''),
                        phone_numbers=row.get('Telefon', ''),
                        lat=lat,
                        lon=lon
                    )
                    patients.append(patient)

                if len(patients) == 0:
                    flash('Keine Patienten importiert.')
                else:
                    flash(f'{len(patients)} Patienten erfolgreich importiert.')
                return redirect(url_for('show_patients'))

            flash('Ungültiges Dateiformat.')
            return redirect(request.url)

        except Exception as e:
            flash(f'Fehler beim Verarbeiten der Patientendatei: {str(e)}.')
            return redirect(request.url)

    def handle_vehicle_upload(self, request):
        """Verarbeitet den Upload einer Mitarbeiterdatei"""
        try:
            file = request.files['file']
            if file and self.allowed_file(file.filename):
                # Excel-Datei einlesen
                df = pd.read_excel(file)
                
                # Fahrzeugliste leeren
                vehicles.clear()
                
                # Neue Fahrzeuge hinzufügen
                for _, row in df.iterrows():
                    address = f"{row['Straße']}, {row['PLZ']} {row['Ort']}"
                    lat, lon = self.geocode_address(address)
                    
                    vehicle = Vehicle(
                        name=f"{row['Name']}, {row['Vorname']}",
                        start_address=address,
                        lat=lat,
                        lon=lon,
                        stellenumfang=row.get('Stellenumfang', 100),
                        funktion=row.get('Funktion', '')
                    )
                    vehicles.append(vehicle)

                if len(vehicles) == 0:
                    flash('Keine Mitarbeiter importiert.')
                else:
                    flash(f'{len(vehicles)} Mitarbeiter erfolgreich importiert.')
                return redirect(url_for('show_vehicles'))

            flash('Ungültiges Dateiformat.')
            return redirect(request.url)

        except Exception as e:
            flash(f'Fehler beim Verarbeiten der Mitarbeiterdatei: {str(e)}.')
            return redirect(request.url)

    def allowed_file(self, filename):
        """Überprüft, ob die Dateiendung erlaubt ist"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def geocode_address(self, address):
        """Geocodiert eine Adresse zu Koordinaten"""
        try:
            result = self.gmaps.geocode(address)
            if result:
                location = result[0]['geometry']['location']
                return location['lat'], location['lng']
            return None, None
        except Exception as e:
            print(f"Fehler beim Geocoding von {address}: {str(e)}")
            return None, None

    def reload_patients_for_weekday(self, weekday):
        """Lädt die Patienten für den angegebenen Wochentag neu"""
        # Hier könnte in Zukunft Logik zum Neuladen der Patienten implementiert werden
        pass 