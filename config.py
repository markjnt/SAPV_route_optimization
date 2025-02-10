import os
from dotenv import load_dotenv

# Laden der Umgebungsvariablen aus der .env Datei
load_dotenv()

# Globale Variablen für die Umgebungsvariablen
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
GOOGLE_PROJECT_ID = os.getenv('GOOGLE_PROJECT_ID')
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

class Config:
    SECRET_KEY = FLASK_SECRET_KEY
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'data', 'uploads')
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(os.getcwd(), 'data', 'flask_session')
    ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = ENV == 'development' 