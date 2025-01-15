import pandas as pd
import googlemaps
from flask import session
from config import GOOGLE_MAPS_API_KEY
from backend.models import Patient, Vehicle, patients, vehicles

class FileService:
    def __init__(self):
        self.gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        self.ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
        self.VALID_VISIT_TYPES = {'HB', 'TK', 'Neuaufnahme'}
        self.WEEKDAY_MAPPING = {
            0: 'Montag',
            1: 'Dienstag',
            2: 'Mittwoch',
            3: 'Donnerstag',
            4: 'Freitag'
        }

    def allowed_file(self, filename):
        """Überprüft, ob die Dateiendung erlaubt ist"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS

    def geocode_address(self, address):
        """Geocodiert eine Adresse zu Koordinaten"""
        try:
            result = self.gmaps.geocode(address)
            if result:
                location = result[0]['geometry']['location']
                return location['lat'], location['lng']
            return None, None
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None, None

    def process_patient_file(self, file, selected_weekday=None):
        """Verarbeitet die hochgeladene Patientendatei"""
        try:
            df = pd.read_excel(file, dtype=str)
            
            # Validiere Spalten
            if not self._validate_patient_columns(df):
                return {
                    'success': False,
                    'message': 'Excel-Datei hat nicht alle erforderlichen Spalten.'
                }

            # Validiere KW
            validation_result = self._validate_calendar_week(df)
            if not validation_result['success']:
                return validation_result

            weekday = selected_weekday or session.get('selected_weekday', 'Montag')
            week_number = int(df['KW'].iloc[0])
            session['selected_week'] = week_number

            # Verarbeite Patienten
            patients.clear()
            df_filtered = df[df[weekday].isin(self.VALID_VISIT_TYPES)].copy()
            
            for _, row in df_filtered.iterrows():
                self._create_patient_from_row(row, weekday)

            message = (f'Keine Patienten für {weekday} gefunden.' if len(patients) == 0 
                      else f'{len(patients)} Patienten für {weekday} erfolgreich importiert.')
            
            return {
                'success': True,
                'message': message
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Fehler beim Verarbeiten der Datei: {str(e)}'
            }

    def process_vehicle_file(self, file):
        """Verarbeitet die hochgeladene Fahrzeugdatei"""
        try:
            df = pd.read_excel(file, dtype=str)
            
            if not self._validate_vehicle_columns(df):
                return {
                    'success': False,
                    'message': 'Excel-Datei hat nicht alle erforderlichen Spalten.'
                }

            vehicles.clear()
            for _, row in df.iterrows():
                self._create_vehicle_from_row(row)

            message = (f'Keine Mitarbeiter importiert.' if len(vehicles) == 0 
                      else f'{len(vehicles)} Mitarbeiter erfolgreich importiert.')
            
            return {
                'success': True,
                'message': message
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Fehler beim Verarbeiten der Datei: {str(e)}'
            }

    def _validate_patient_columns(self, df):
        """Validiert die Spalten der Patientendatei"""
        required_columns = ['Nachname', 'Vorname', 'Strasse', 'Ort', 'PLZ', 'KW']
        required_columns += list(self.WEEKDAY_MAPPING.values())
        required_columns += [f"Uhrzeit/Info {day}" for day in self.WEEKDAY_MAPPING.values()]
        return all(col in df.columns for col in required_columns)

    def _validate_vehicle_columns(self, df):
        """Validiert die Spalten der Fahrzeugdatei"""
        required_columns = ['Nachname', 'Vorname', 'Strasse', 'Ort', 'PLZ', 'Stellenumfang', 'Funktion']
        return all(col in df.columns for col in required_columns)

    def _validate_calendar_week(self, df):
        """Validiert die Kalenderwoche in der Patientendatei"""
        try:
            df['KW'] = pd.to_numeric(df['KW'], errors='raise')
        except ValueError:
            return {
                'success': False,
                'message': 'Fehler: Die KW-Spalte enthält ungültige Werte. Bitte nur Zahlen eingeben.'
            }

        if not all((1 <= df['KW']) & (df['KW'] <= 53)):
            return {
                'success': False,
                'message': 'Fehler: KW-Werte müssen zwischen 1 und 53 liegen.'
            }

        if df['KW'].nunique() > 1:
            kw_values = df['KW'].unique()
            return {
                'success': False,
                'message': f'Fehler: Unterschiedliche Kalenderwochen in der Datei gefunden: {", ".join(map(str, kw_values))}.'
            }

        return {'success': True}

    def _create_patient_from_row(self, row, weekday):
        """Erstellt einen Patienten aus einer Excel-Zeile"""
        name = f"{row['Vorname']} {row['Nachname']}"
        address = f"{row['Strasse']}, {row['PLZ']} {row['Ort']}"
        visit_type = row[weekday]
        time_info = str(row.get(f"Uhrzeit/Info {weekday}", ""))
        time_info = "" if time_info.lower() == "nan" else time_info
        
        phone_numbers = self._process_phone_numbers(row)
        lat, lon = self.geocode_address(address)
        
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

    def _create_vehicle_from_row(self, row):
        """Erstellt ein Fahrzeug aus einer Excel-Zeile"""
        address = f"{row['Strasse']}, {row['PLZ']} {row['Ort']}"
        lat, lon = self.geocode_address(address)
        
        stellenumfang_val = self._process_stellenumfang(row)
        
        vehicle = Vehicle(
            name=f"{row['Vorname']} {row['Nachname']}",
            start_address=address,
            lat=lat,
            lon=lon,
            stellenumfang=stellenumfang_val,
            funktion=row.get('Funktion', '')
        )
        vehicles.append(vehicle)

    def _process_phone_numbers(self, row):
        """Verarbeitet Telefonnummern aus einer Excel-Zeile"""
        phone1 = str(row.get('Telefon', "")).strip()
        phone2 = str(row.get('Telefon2', "")).strip()
        phone1 = "" if phone1.lower() == "nan" else phone1
        phone2 = "" if phone2.lower() == "nan" else phone2
        
        if phone1 and phone2:
            return f"{phone1}\n{phone2}"
        return phone1 or phone2 or ""

    def _process_stellenumfang(self, row):
        """Verarbeitet den Stellenumfang aus einer Excel-Zeile"""
        try:
            stellenumfang_val = int(float(row['Stellenumfang']))
        except:
            stellenumfang_val = 100

        return max(0, min(100, stellenumfang_val)) 