// Globale Variablen
let map;                        // Google Maps Objekt
let markers = [];               // Alle aktuellen Marker
let directionsRenderers = [];   // DirectionsRenderer für Routen
let optimized_routes = [];      // Optimierte Routen

// Feste Farbpalette (30 gut unterscheidbare Farben)
const COLORS = [
    "#FF0000", "#0000FF", "#00FF00", "#FFA500", "#800080",
    "#FFD700", "#FF1493", "#00CED1", "#32CD32", "#FF4500",
    "#4169E1", "#8B4513", "#FF69B4", "#4B0082", "#00FF7F",
    "#CD853F", "#00BFFF", "#FF6347", "#7B68EE", "#2E8B57",
    "#DAA520", "#9370DB", "#3CB371", "#FF8C00", "#BA55D3",
    "#20B2AA", "#CD5C5C", "#6B8E23", "#C71585", "#87CEEB"
];

// Mapping der Besuchstypen zu Verweilzeiten in Sekunden
const VISIT_DWELL_TIMES = {
    'HB': 35 * 60,          // 35 Minuten in Sekunden
    'Neuaufnahme': 120 * 60 // 120 Minuten in Sekunden
};

window.onload = initMap();

// Google Maps initialisieren und Marker laden
function initMap() {
  map = new google.maps.Map(document.getElementById('map'), {
    center: { lat: 51.0237509, lng: 7.535209399 },
    zoom: 9,
    streetViewControl: false,
    mapTypeControl: false
  });
  loadMarkers();
}

// Marker vom Server laden
async function loadMarkers() {
  clearMarkers();
  try {
    const response = await fetch('/get_markers');
    const data = await response.json();

    // Patienten: rote Marker
    data.patients.forEach(p => {
      const marker = new google.maps.Marker({
        position: { lat: p.lat, lng: p.lng },
        map: map,
        title: p.name,
        icon: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png'
      });
      markers.push(marker);
    });

    // Fahrzeuge: grüne Marker
    data.vehicles.forEach(v => {
      const marker = new google.maps.Marker({
        position: { lat: v.lat, lng: v.lng },
        map: map,
        title: v.name,
        icon: 'http://maps.google.com/mapfiles/ms/icons/green-dot.png'
      });
      markers.push(marker);
    });
  } catch (error) {
    console.error("Fehler beim Laden der Marker:", error);
  }
}

// Alle Marker löschen
function clearMarkers() {
  markers.forEach(marker => marker.setMap(null));
  markers = [];
}

// Alle Routen löschen
function clearRoutes() {
  directionsRenderers.forEach(renderer => renderer.setMap(null));
  directionsRenderers = [];
}

// Route berechnen mit DirectionsService
function calculateRoute(request, routeColor, routeCard) {
    return new Promise((resolve, reject) => {
        const directionsService = new google.maps.DirectionsService();
        
        // Erstelle DirectionsRenderer hier
        const directionsRenderer = new google.maps.DirectionsRenderer({
            map: map,
            suppressMarkers: true,
            preserveViewport: true,
            polylineOptions: {
                strokeColor: routeColor,
                strokeOpacity: 0.8,
                strokeWeight: 4
            }
        });
        directionsRenderers.push(directionsRenderer);

        directionsService.route(request, (result, status) => {
            if (status === "OK") {
                directionsRenderer.setDirections(result);
                
                // Berechne Gesamtzeit (Fahrt + Besuche)
                let totalDuration = 0;
                result.routes[0].legs.forEach(leg => {
                    totalDuration += leg.duration.value;
                });
                
                const stops = routeCard.querySelector('.stops-container').querySelectorAll('.stop-card:not(.tk-stop)');
                stops.forEach(stop => {
                    const visitType = stop.querySelector('.visit-type').textContent;
                    totalDuration += VISIT_DWELL_TIMES[visitType] || 0;
                });
                
                const durationHrs = Math.round((totalDuration / 3600) * 100) / 100;
                // Speichere die berechnete Duration im Dataset
                routeCard.dataset.durationHrs = durationHrs;
                
                resolve(result);
            } else {
                console.error("Fehler bei der Routenberechnung:", status);
                reject(status);
            }
        });
    });
}

// Handle optimize button click
document.getElementById('optimizeButton').addEventListener('click', async () => {
  clearRoutes(); // Alte Routen entfernen
  try {
    const response = await fetch('/optimize_route', { method: 'POST' });
    const data = await response.json();

    if (data.status === 'success') {
      // Wir haben 'data.routes' (nur HB/Neuaufnahme) und 'data.tk_patients' (nur TK)
      displayRoutes(data);
      document.getElementById('resultsSection').style.display = 'block';
    } else {
      alert(data.message || "Fehler bei der Routenoptimierung");
    }
  } catch (error) {
    console.error("Fehler bei /optimize_route:", error);
    alert("Fehler bei /optimize_route. Siehe Konsole.");
  }
});

// Funktion zum Aktualisieren des Wochentags
async function updateWeekdayDisplay() {
    try {
        const response = await fetch('/get-current-weekday');
        const data = await response.json();
        const weekdaySelect = document.getElementById('weekdaySelect');
        weekdaySelect.value = data.weekday;
    } catch (err) {
        console.error("Error getting current weekday:", err);
    }
}

// Handle DOM events (weekday selection etc.)
document.addEventListener('DOMContentLoaded', function() {
    // Initialisiere den aktuellen Wochentag
    updateWeekdayDisplay();

    // Falls du initMap() hier manuell aufrufen willst (keine callback=initMap)
    initMap();

    const weekdaySelect = document.getElementById('weekdaySelect');
    const tomorrowBtn = document.getElementById('tomorrowBtn');

    // Array der Wochentage
    const weekdays = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];

    // Dropdown -> Server
    weekdaySelect.addEventListener('change', async function() {
        try {
            const response = await fetch('/update-weekday', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ weekday: this.value })
            });
            const data = await response.json();
            console.log("Server Response:", data);
            
            // Aktualisiere den angezeigten Wochentag
            await updateWeekdayDisplay();
        } catch (err) {
            console.error("Error updating weekday:", err);
        }
    });

    // Button "Morgen"
    tomorrowBtn.addEventListener('click', async function() {
        const today = new Date();
        const todayIndex = today.getDay();
        const tomorrowIndex = (todayIndex + 1) % 7;
        weekdaySelect.value = weekdays[tomorrowIndex];
        // Trigger 'change'
        weekdaySelect.dispatchEvent(new Event('change'));
    });
});

// Optimierte Routen anzeigen
function displayRoutes(data) {
    clearRoutes();
    const routeResults = document.getElementById('routeResults');
    routeResults.innerHTML = '';
    
    const routesContainer = document.createElement('div');
    routesContainer.className = 'routes-container';
    
    // Routen erstellen
    data.routes.forEach((route, index) => {
        const routeColor = COLORS[index % COLORS.length];
        const routeCard = document.createElement('div');
        routeCard.className = 'route-card';
        routeCard.style.borderColor = routeColor;
        
        // Fahrzeug-Header mit Duration aus dem Backend
        const vehicleHeader = document.createElement('h3');
        const durationColor = (route.duration_hrs || 0) <= route.max_hours ? 'green' : 'red';
        vehicleHeader.innerHTML = `
            ${route.vehicle}
            <div style="font-size: 0.8em; color: #666; margin: 2px 0;">${route.funktion || ''}</div>
            <span class="duration" style="color: ${durationColor}">(${route.duration_hrs || 0} / ${route.max_hours}h)</span>
        `;
        routeCard.appendChild(vehicleHeader);
        
        // Speichere die aktuelle Duration im Dataset
        routeCard.dataset.durationHrs = route.duration_hrs || 0;
        
        // Container für verschiebbare Stopps
        const stopsContainer = document.createElement('div');
        stopsContainer.className = 'stops-container';
        stopsContainer.setAttribute('data-vehicle', route.vehicle);
        
        // Filtere TK-Stopps für die Route aus
        const regularStops = route.stops.filter(stop => stop.visit_type !== 'TK');
        
        // Nur reguläre Stopps für die Wegpunkte und Route verwenden
        if (regularStops.length > 0) {
            const waypoints = regularStops.map(s => ({
                location: new google.maps.LatLng(s.location.lat, s.location.lng),
                stopover: true
            }));

            // Route berechnen und anzeigen
            const origin = new google.maps.LatLng(route.vehicle_start.lat, route.vehicle_start.lng);
            const destination = origin;

            const directionsRenderer = new google.maps.DirectionsRenderer({
                map: map,
                suppressMarkers: true,
                preserveViewport: true,
                polylineOptions: {
                    strokeColor: routeColor,
                    strokeOpacity: 0.8,
                    strokeWeight: 4
                }
            });
            directionsRenderers.push(directionsRenderer);

            const request = {
                origin: origin,
                destination: destination,
                waypoints: waypoints,
                travelMode: google.maps.TravelMode.DRIVING,
                optimizeWaypoints: false
            };

            calculateRoute(request, routeColor, routeCard).catch(err => {
                console.error("Fehler bei der Routenberechnung:", err);
            });
        }

        // Alle Stopps anzeigen
        route.stops.forEach((stop, stopIndex) => {
            const stopCard = document.createElement('div');
            stopCard.className = `stop-card${stop.visit_type === 'TK' ? ' tk-stop' : ''}`;
            stopCard.draggable = true;
            stopCard.innerHTML = `
                ${stop.visit_type !== 'TK' ? `<div class="stop-number">${stopIndex + 1}</div>` : ''}
                <div class="patient-info">
                    <strong>${stop.patient}</strong>
                    <div>${stop.address}</div>
                    <div class="visit-type">${stop.visit_type || ''}</div>
                    <div style="display:none" data-lat="${stop.location.lat}" data-lng="${stop.location.lng}"></div>
                </div>
            `;
            
            stopCard.addEventListener('dragstart', handleDragStart);
            stopCard.addEventListener('dragend', handleDragEnd);
            
            stopsContainer.appendChild(stopCard);
        });
        
        routeCard.appendChild(stopsContainer);
        routesContainer.appendChild(routeCard);
        routeCard.dataset.vehicleStartLat = route.vehicle_start.lat;
        routeCard.dataset.vehicleStartLng = route.vehicle_start.lng;
    });
    
    // Nicht zugeordnete TK-Patienten separat anzeigen
    if (data.tk_patients && data.tk_patients.length > 0) {
        const tkCard = document.createElement('div');
        tkCard.className = 'route-card tk-card';
        
        const tkHeader = document.createElement('h3');
        tkHeader.textContent = 'Nicht zugeordnete TK-Fälle';
        tkCard.appendChild(tkHeader);
        
        const tkContainer = document.createElement('div');
        tkContainer.className = 'stops-container';
        tkContainer.setAttribute('data-vehicle', 'tk');
        
        data.tk_patients.forEach(tk => {
            const tkStop = document.createElement('div');
            tkStop.className = 'stop-card tk-stop';
            tkStop.draggable = true;
            tkStop.innerHTML = `
                <div class="patient-info">
                    <strong>${tk.patient}</strong>
                    <div>${tk.address}</div>
                    <div class="visit-type">TK</div>
                    <div style="display:none" data-lat="${tk.location?.lat}" data-lng="${tk.location?.lng}"></div>
                </div>
            `;
            
            tkStop.addEventListener('dragstart', handleDragStart);
            tkStop.addEventListener('dragend', handleDragEnd);
            
            tkContainer.appendChild(tkStop);
        });
        
        tkCard.appendChild(tkContainer);
        routesContainer.appendChild(tkCard);
    }
    
    routeResults.appendChild(routesContainer);
    
    document.querySelectorAll('.stops-container').forEach(container => {
        container.addEventListener('dragover', handleDragOver);
        container.addEventListener('drop', handleDrop);
    });
}

// Drag & Drop functions
function handleDragStart(e) {
    e.target.classList.add('dragging');
    e.dataTransfer.setData('text/plain', e.target.innerHTML);
    // Speichere den Typ des gezogenen Elements
    e.dataTransfer.setData('type', e.target.classList.contains('tk-stop') ? 'tk' : 'regular');
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
}

function handleDragOver(e) {
    e.preventDefault();
    const container = e.target.closest('.stops-container');
    if (!container) return;

    const draggingElement = document.querySelector('.dragging');
    if (!draggingElement) return;

    const isTKContainer = container.getAttribute('data-vehicle') === 'tk';
    const isTKStop = draggingElement.classList.contains('tk-stop');
    
    // TK-Container akzeptiert nur TK-Stopps
    if (isTKContainer && !isTKStop) {
        e.dataTransfer.dropEffect = 'none';
        return;
    }
    
    e.dataTransfer.dropEffect = 'move';

    // Entferne vorhandene Drop-Indikatoren
    container.querySelectorAll('.drop-indicator').forEach(el => el.remove());

    const stops = [...container.querySelectorAll('.stop-card:not(.dragging)')];
    const afterElement = getDropPosition(container, e.clientY, isTKStop);
    
    if (afterElement) {
        // Füge Drop-Indikator ein
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        afterElement.before(indicator);
    } else if (!isTKStop) {
        // Am Ende einfügen (nur für nicht-TK-Stopps)
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        container.appendChild(indicator);
    }
}

function getDropPosition(container, y, isTKStop) {
    const draggableElements = [...container.querySelectorAll('.stop-card:not(.dragging)')];
    
    if (isTKStop) {
        // TK-Stopps immer ans Ende
        return null;
    }

    // Finde das erste TK-Element
    const firstTKStop = draggableElements.find(el => el.classList.contains('tk-stop'));
    if (firstTKStop) {
        // Filtere TK-Stopps aus
        draggableElements.splice(draggableElements.indexOf(firstTKStop));
    }

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function handleDrop(e) {
    e.preventDefault();
    const draggingElement = document.querySelector('.dragging');
    
    if (draggingElement) {
        const container = e.target.closest('.stops-container');
        if (container) {
            const isTKContainer = container.getAttribute('data-vehicle') === 'tk';
            const isTKStop = draggingElement.classList.contains('tk-stop');
            
            if (isTKContainer && !isTKStop) {
                return;
            }

            // Entferne Drop-Indikatoren
            container.querySelectorAll('.drop-indicator').forEach(el => el.remove());
            
            // Füge das Element hinzu
            if (isTKStop) {
                container.appendChild(draggingElement);
            } else {
                const afterElement = getDropPosition(container, e.clientY, isTKStop);
                if (afterElement) {
                    afterElement.before(draggingElement);
                } else {
                    const tkStops = container.querySelectorAll('.tk-stop');
                    if (tkStops.length > 0) {
                        tkStops[0].before(draggingElement);
                    } else {
                        container.appendChild(draggingElement);
                    }
                }
            }
            
            updateStopNumbers();

            // Aktualisiere die Routen für alle Container
            document.querySelectorAll('.stops-container:not([data-vehicle="tk"])').forEach(cont => {
                const routeCard = cont.closest('.route-card');
                const routeColor = routeCard.style.borderColor;
                const regularStops = [...cont.querySelectorAll('.stop-card:not(.tk-stop)')];
                
                if (regularStops.length === 0) {
                    updateRouteDuration(routeCard, 0);
                } else {
                    const origin = new google.maps.LatLng(
                        routeCard.dataset.vehicleStartLat, 
                        routeCard.dataset.vehicleStartLng
                    );
                    
                    const waypoints = regularStops.map(stop => ({
                        location: new google.maps.LatLng(
                            parseFloat(stop.querySelector('[data-lat]').dataset.lat),
                            parseFloat(stop.querySelector('[data-lat]').dataset.lng)
                        ),
                        stopover: true
                    }));

                    const request = {
                        origin: origin,
                        destination: origin,
                        waypoints: waypoints,
                        travelMode: google.maps.TravelMode.DRIVING,
                        optimizeWaypoints: false
                    };

                    calculateRoute(request, routeColor, routeCard);
                }
            });

            // Warte kurz, bis alle Routen berechnet wurden
            setTimeout(() => {
                updateOptimizedRoutes();
            }, 100);
        }
    }
}

// Stoppnummern aktualisieren
function updateStopNumbers() {
    document.querySelectorAll('.stops-container').forEach(container => {
        // Nur Nicht-TK-Stopps nummerieren
        const regularStops = container.querySelectorAll('.stop-card:not(.tk-stop)');
        regularStops.forEach((stop, index) => {
            let numberDiv = stop.querySelector('.stop-number');
            if (!numberDiv) {
                numberDiv = document.createElement('div');
                numberDiv.className = 'stop-number';
                stop.insertBefore(numberDiv, stop.firstChild);
            }
            numberDiv.textContent = index + 1;
        });
    });
}

// Optimierte Routen aktualisieren
function updateOptimizedRoutes() {
    const optimized_routes = [];
    const assigned_tk_stops = new Set();
    
    document.querySelectorAll('.stops-container:not([data-vehicle="tk"])').forEach((container) => {
        const routeCard = container.closest('.route-card');
        const vehicleName = container.getAttribute('data-vehicle');

        const routeInfo = {
            vehicle: vehicleName,
            vehicle_start: null,
            duration_hrs: parseFloat(routeCard.dataset.durationHrs || 0),
            max_hours: parseFloat(routeCard.querySelector('.duration').textContent.split('/')[1].replace('h)', '')),
            stops: []
        };
        
        // Sammle alle Stopps
        container.querySelectorAll('.stop-card').forEach(stop => {
            const locationDiv = stop.querySelector('[data-lat]');
            const isTKStop = stop.classList.contains('tk-stop');
            
            const stopInfo = {
                patient: stop.querySelector('strong').textContent,
                address: stop.querySelector('.patient-info div').textContent,
                visit_type: isTKStop ? "TK" : stop.querySelector('.visit-type').textContent,
                location: locationDiv ? {
                    lat: parseFloat(locationDiv.dataset.lat),
                    lng: parseFloat(locationDiv.dataset.lng)
                } : null
            };
            
            routeInfo.stops.push(stopInfo);
            
            if (isTKStop) {
                assigned_tk_stops.add(stopInfo.patient);
            }
        });
        
        optimized_routes.push(routeInfo);
    });
    
    // Sammle nicht zugewiesene TK-Stopps
    const unassigned_tk_stops = [];
    document.querySelector('.stops-container[data-vehicle="tk"]')?.querySelectorAll('.stop-card').forEach(stop => {
        const patient = stop.querySelector('strong').textContent;
        if (!assigned_tk_stops.has(patient)) {
            const locationDiv = stop.querySelector('[data-lat]');
            unassigned_tk_stops.push({
                patient: patient,
                address: stop.querySelector('.patient-info div').textContent,
                visit_type: "TK",
                location: locationDiv ? {
                    lat: parseFloat(locationDiv.dataset.lat),
                    lng: parseFloat(locationDiv.dataset.lng)
                } : null
            });
        }
    });

    fetch('/update_routes', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            optimized_routes: optimized_routes,
            unassigned_tk_stops: unassigned_tk_stops
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            clearRoutes();
            // Zeige die Routen mit den aktualisierten Werten aus dem Backend an
            displayRoutes(data);
        }
    })
    .catch(error => console.error('Error updating routes:', error));
}

// Fügen Sie ein Event-Listener für das Drag-Ende hinzu
document.querySelectorAll('.stop-card').forEach(stopCard => {
    stopCard.addEventListener('dragend', () => {
        // Aktualisieren Sie die Routen nach dem Drag-Ende
        updateOptimizedRoutes();
    });
});

// Funktion zum Aktualisieren der Routendauer
function updateRouteDuration(routeCard, durationHrs = 0) {
    const header = routeCard.querySelector('h3');
    const durationSpan = header.querySelector('.duration');
    const maxHours = parseFloat(durationSpan.textContent.split('/')[1].replace('h)', ''));
    
    // Setze die Textfarbe basierend auf dem Vergleich
    if (durationHrs <= maxHours) {
        durationSpan.style.color = 'green';
    } else {
        durationSpan.style.color = 'red';
    }
    
    durationSpan.textContent = `(${durationHrs} / ${maxHours}h)`;
    routeCard.dataset.durationHrs = durationHrs;
}
