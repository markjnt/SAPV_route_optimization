class Entity:
    # Basisklasse für alle Entitäten
    def __init__(self, name, lat=None, lon=None):
        self.id = None
        self.name = name
        self.lat = lat
        self.lon = lon

    def __str__(self):
        return f"{self.name} ({self.lat}, {self.lon})" 