from .base import Entity

# Liste für Fahrzeuge
vehicles = []

class Vehicle(Entity):
    def __init__(self, name, start_address, lat=None, lon=None, stellenumfang=100, funktion=""):
        super().__init__(name, lat, lon)
        self.id = len(vehicles) + 1  # Eindeutige ID basierend auf Mitarbeiterliste
        self.start_address = start_address
        self.stellenumfang = stellenumfang  # Arbeitszeit in Prozent (0-100%)
        self.funktion = funktion
        self.is_active = True  # Standardmäßig aktiv

    def __str__(self):
        return (f"Vehicle: {self.name}, {self.start_address} "
                f"({self.lat}, {self.lon}), Stellenumfang={self.stellenumfang}, "
                f"Funktion={self.funktion}, Active={self.is_active}") 