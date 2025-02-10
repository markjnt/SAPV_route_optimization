from flask import Flask
from routes import routes
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')  # Lädt bereits alle Konfigurationen
    
    # Erstelle die notwendigen Ordner
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

    # Blueprint registrieren
    app.register_blueprint(routes)
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)