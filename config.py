import os
from dotenv import load_dotenv

# Laden der Umgebungsvariablen aus der .env Datei
load_dotenv()

class Config:
    # API Keys und Secrets
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    GOOGLE_PROJECT_ID = os.getenv('GOOGLE_PROJECT_ID')
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    
    # Upload und Session Konfiguration
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'data', 'uploads')
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(os.getcwd(), 'data', 'flask_session')
    
    # Environment
    ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = ENV == 'development' 