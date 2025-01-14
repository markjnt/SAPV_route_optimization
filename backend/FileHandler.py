import io
import pandas as pd
from flask import flash, redirect, url_for, session, current_app as app
import googlemaps
import os
from werkzeug.utils import secure_filename

from config import GOOGLE_MAPS_API_KEY
from backend.entities import Patient, Vehicle, patients, vehicles

# Google Maps Client initialisieren
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def get_selected_weekday():
    """Gibt den ausgewählten Wochentag zurück, standardmäßig 'Montag'"""
    return session.get('selected_weekday', 'Montag')

def geocode_address(address):
    try:
        result = gmaps.geocode(address)
        if result:
            location = result[0]['geometry']['location']
            return location['lat'], location['lng']
        return None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None

# Konfiguration für File Upload
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Definition der erlaubten Besuchsarten
VALID_VISIT_TYPES = {'HB', 'TK', 'Neuaufnahme'}

# Mapping von Wochentagen
WEEKDAY_MAPPING = {
    0: 'Montag',
    1: 'Dienstag',
    2: 'Mittwoch',
    3: 'Donnerstag',
    4: 'Freitag'
}

def handle_patient_upload(request, selected_weekday=None):
    if request.method == 'POST' and 'patient_file' in request.files:
        file = request.files['patient_file']
        if file and file.filename != '' and allowed_file(file.filename):
            try:
                app.last_patient_upload = request
                
                df = pd.read_excel(file, dtype=str)
                required_columns = ['Nachname', 'Vorname', 'Strasse', 'Ort', 'PLZ', 'KW']
                required_columns += list(WEEKDAY_MAPPING.values())
                required_columns += [f"Uhrzeit/Info {day}" for day in WEEKDAY_MAPPING.values()]
                
                # Add phone columns to required columns
                phone_columns = ['Telefon', 'Telefon2']
                
                if not all(col in df.columns for col in required_columns):
                    flash('Excel-Datei hat nicht alle erforderlichen Spalten.')
                    return redirect(request.url)

                weekday = selected_weekday or get_selected_weekday()
                time_info_column = f"Uhrzeit/Info {weekday}"
                
                # Prüfe ob KW-Spalte numerische Werte enthält
                try:
                    df['KW'] = pd.to_numeric(df['KW'], errors='raise')
                except ValueError:
                    flash('Fehler: Die KW-Spalte enthält ungültige Werte. Bitte nur Zahlen eingeben.')
                    return redirect(request.url)
                
                # Prüfe ob KW im gültigen Bereich liegt
                if not all((1 <= df['KW']) & (df['KW'] <= 53)):
                    flash('Fehler: KW-Werte müssen zwischen 1 und 53 liegen.')
                    return redirect(request.url)
                
                # Prüfe ob alle Zeilen die gleiche KW haben
                if df['KW'].nunique() > 1:
                    kw_values = df['KW'].unique()
                    flash(f'Fehler: Unterschiedliche Kalenderwochen in der Datei gefunden: {", ".join(map(str, kw_values))}.')
                    return redirect(request.url)
                
                # Hole die Kalenderwoche
                week_number = int(df['KW'].iloc[0])
                
                # Speichere KW in der Session
                session['selected_week'] = week_number
                
                df_filtered = df[df[weekday].isin(VALID_VISIT_TYPES)].copy()

                patients.clear()
                for _, row in df_filtered.iterrows():
                    name = f"{row['Vorname']} {row['Nachname']}"
                    address = f"{row['Strasse']}, {row['PLZ']} {row['Ort']}"
                    visit_type = row[weekday]
                    time_info = str(row.get(time_info_column, ""))
                    time_info = "" if time_info.lower() == "nan" else time_info
                    
                    # Handle phone numbers
                    phone1 = str(row.get('Telefon', "")).strip()
                    phone2 = str(row.get('Telefon2', "")).strip()
                    phone1 = "" if phone1.lower() == "nan" else phone1
                    phone2 = "" if phone2.lower() == "nan" else phone2
                    
                    # Combine phone numbers with line break if both exist
                    phone_numbers = ""
                    if phone1 and phone2:
                        phone_numbers = f"{phone1}\n{phone2}"
                    elif phone1:
                        phone_numbers = phone1
                    elif phone2:
                        phone_numbers = phone2
                    
                    lat, lon = geocode_address(address)
                    patient = Patient(
                        name=name, 
                        address=address, 
                        visit_type=visit_type, 
                        time_info=time_info,
                        phone_numbers=phone_numbers,
                        lat=lat, 
                        lon=lon
                    )
                    patients.append(patient)

                if len(patients) == 0:
                    flash(f'Keine Patienten für {weekday} gefunden.')
                else:
                    flash(f'{len(patients)} Patienten für {weekday} erfolgreich importiert.')
                return redirect(url_for('show_patients'))

            except Exception as e:
                flash(f'Fehler beim Verarbeiten der Patientendatei: {str(e)}.')
                return redirect(request.url)
        else:
            flash('Keine Patientendatei ausgewählt.')
            return redirect(request.url)

    flash('Keine Patientendatei ausgewählt.')
    return redirect(request.url)

def handle_vehicle_upload(request):
    if 'vehicle_file' not in request.files:
        flash('Keine Mitarbeiterdatei ausgewählt.')
        return redirect(request.url)

    file = request.files['vehicle_file']
    if file.filename == '':
        flash('Keine Mitarbeiterdatei ausgewählt.')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        try:
            df = pd.read_excel(file, dtype=str)

            required_columns = ['Nachname', 'Vorname', 'Strasse', 'Ort', 'PLZ', 'Stellenumfang', 'Funktion']
            if not all(col in df.columns for col in required_columns):
                flash('Excel-Datei hat nicht alle erforderlichen Spalten.')
                return redirect(request.url)

            vehicles.clear()
            for _, row in df.iterrows():
                lat, lon = geocode_address(f"{row['Strasse']}, {row['PLZ']} {row['Ort']}")
                
                try:
                    stellenumfang_val = int(float(row['Stellenumfang']))
                except:
                    stellenumfang_val = 100

                if stellenumfang_val < 0:  
                    stellenumfang_val = 0
                elif stellenumfang_val > 100:
                    stellenumfang_val = 100

                vehicle = Vehicle(
                    name=f"{row['Vorname']} {row['Nachname']}",
                    start_address=f"{row['Strasse']}, {row['PLZ']} {row['Ort']}",
                    lat=lat,
                    lon=lon,
                    stellenumfang=stellenumfang_val,
                    funktion=row.get('Funktion', '')
                )
                vehicles.append(vehicle)

            if len(vehicles) == 0:
                flash('Keine Mitarbeiter importiert.')
            else:
                flash(f'{len(vehicles)} Mitarbeiter erfolgreich importiert.')
            return redirect(url_for('show_vehicles'))

        except Exception as e:
            flash(f'Fehler beim Verarbeiten der Mitarbeiterdatei: {str(e)}.')
            return redirect(request.url)
