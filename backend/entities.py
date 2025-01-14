# Listen für Patienten und Fahrzeuge
patients = []
vehicles = []

class Entity:
    def __init__(self, name, lat=None, lon=None):
        self.id = None  # Wird später gesetzt
        self.name = name
        self.lat = lat
        self.lon = lon

    def __str__(self):
        return f"{self.name} ({self.lat}, {self.lon})"


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


class Vehicle(Entity):
    def __init__(self, name, start_address, lat=None, lon=None, stellenumfang=100, funktion=""):
        super().__init__(name, lat, lon)
        self.id = len(vehicles) + 1  # Eindeutige ID basierend auf Mitarbeiterliste
        self.start_address = start_address
        self.stellenumfang = stellenumfang  # Arbeitszeit in Prozent (0-100%)
        self.funktion = funktion

    def __str__(self):
        return (f"Vehicle: {self.name}, {self.start_address} "
                f"({self.lat}, {self.lon}), Stellenumfang={self.stellenumfang}, "
                f"Funktion={self.funktion}")
