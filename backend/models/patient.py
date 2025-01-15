from .base import Entity

# Liste für Patienten
patients = []

class Patient(Entity):
    def __init__(self, name, address, visit_type, time_info="", phone_numbers="", lat=None, lon=None):
        super().__init__(name, lat, lon)
        self.id = len(patients) + 1  # Eindeutige ID basierend auf Patientenliste
        self.address = address
        self.visit_type = visit_type
        self.time_info = time_info
        self.phone_numbers = phone_numbers

    def __str__(self):
        return f"Patient: {self.name}, {self.address} ({self.lat}, {self.lon})" 