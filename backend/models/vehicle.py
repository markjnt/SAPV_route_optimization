from .base import Entity

# Mitarbeiter = Fahrzeuge
# Liste für Fahrzeuge bzw. Mitarbeiter
vehicles = []

class Vehicle(Entity):
    # Fahrzeugklasse
    def __init__(self, name, start_address, lat=None, lon=None, stellenumfang=100, funktion=""):
        super().__init__(name, lat, lon)
        self.id = len(vehicles) + 1
        self.start_address = start_address
        self.stellenumfang = stellenumfang
        self.funktion = funktion
        self.is_active = True

    def __str__(self):
        return (f"Vehicle: {self.name}, {self.start_address} "
                f"({self.lat}, {self.lon}), Stellenumfang={self.stellenumfang}, "
                f"Funktion={self.funktion}, Active={self.is_active}") 