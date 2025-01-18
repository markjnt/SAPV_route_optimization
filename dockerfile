# Base Image
FROM python:3.12-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# Erstelle notwendige Ordner mit korrekten Berechtigungen
RUN mkdir -p /app/data/uploads /app/data/flask_session && \
    chmod -R 777 /app/data

# Kopiere zuerst die requirements.txt und installiere Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere dann den restlichen Projektcode
COPY . .

# Umgebungsvariablen setzen
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
ENV FLASK_DEBUG=1

# Port freigeben
EXPOSE 49200

# Start Command mit Flask Development Server
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=49200"]