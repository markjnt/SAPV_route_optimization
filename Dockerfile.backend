# Base Image
FROM python:3.12-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# Erstelle notwendige Ordner mit korrekten Berechtigungen
RUN mkdir -p /app/data/uploads /app/data/flask_session && \
    chmod -R 777 /app/data

# Kopiere zuerst die requirements.txt und installiere Abhängigkeiten
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere dann den Backend-Code
COPY backend/ .

# Umgebungsvariablen setzen
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json

# Port freigeben
EXPOSE 8000

# Start Command mit Gunicorn (single worker)
CMD ["gunicorn", "--workers=1", "--bind=0.0.0.0:8000", "--timeout=120", "--access-logfile=-", "app:app"]