# PalliRoute

PalliRoute ist ein Projekt zur automatischen Optimierung von Fahrtrouten im Gesundheitswesen. Es verwendet die Google Maps API zur Visualisierung und Berechnung von optimalen Routen zwischen Patientenstandorten. Das Projekt entstand im Rahmen vom Modul Digitilisierung im Master Maschinenbau an der TH Köln.

## 1. Google Authentifizierung

- Erstellen Sie ein [Google Cloud Project](https://console.cloud.google.com/) und kopieren Sie die Project ID.
- Aktivieren Sie die folgende APIs in der [Google Maps Platform](https://console.cloud.google.com/google/maps-apis) für das Projekt:
  - Directions API
  - Geocoding API
  - Maps JavaScript API
  - Routes Optimization API
- Erstellen Sie ein Google Maps API Key für die aktivierten APIs und speichern Sie diesen.
- Erstellen Sie einen Service Account und laden Sie einen Schlüssel im JSON Format herunter.

## 2. .env Datei

Erstellen Sie eine `.env` Datei mit folgenden Variablen:
```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
GOOGLE_PROJECT_ID=your_google_project_id
FLASK_SECRET_KEY=your_secret_key
GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json
```

- Ersetzen Sie `your_google_maps_api_key` mit Ihrem Google Maps API Key.
- Ersetzen Sie `your_google_project_id` mit Ihrer Google Project ID.
- Ersetzen Sie `your_secret_key` mit einem sicheren Schlüssel für die Flask Session.
- Der Pfad `/app/google-credentials.json` ist der fixe Pfad im Docker Container für die Service Account Credentials.

## 3. Docker Ausführung

Das Image ist auf [Docker Hub](https://hub.docker.com/r/markjnt/palliroute) verfügbar.

### 1. Docker Image von Docker Hub laden:
```bash
docker pull markjnt/palliroute
```

### 2. Container starten:

Vergeben Sie ein Volume mit der zuvor heruntergeladenen Service Account JSON Datei:
```bash
docker run -d --name my-palliroute -p 8000:8000 --env-file .env -v /path/to/your/service-account-key.json:/app/google-credentials.json markjnt/palliroute
```

Die Anwendung ist unter `http://localhost:8000` sowie im Netzwerk unter der IP-Adresse des Hosts (z. B. `192.168.1.100:8000`) erreichbar

## Lizenz

Dieses Projekt ist unter der MIT Lizenz veröffentlicht. Siehe [LICENSE](LICENSE) für Details.
