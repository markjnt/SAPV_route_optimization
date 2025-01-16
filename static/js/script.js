// ==========================================
// Konfiguration und Globale Variablen
// ==========================================
let map;                        // Google Maps Objekt
let markers = [];               // Alle aktuellen Marker
let directionsRenderers = [];   // DirectionsRenderer für Routen
let optimized_routes = [];      // Optimierte Routen

// Konstanten für Verweilzeiten
const VISIT_DWELL_TIMES = {
    'HB': 35 * 60,          // 35 Minuten in Sekunden
    'Neuaufnahme': 120 * 60 // 120 Minuten in Sekunden
};

// Feste Farbpalette (30 gut unterscheidbare Farben)
const COLORS = [
    "#FF0000", "#0000FF", "#E91E63", "#FFA500", "#800080",
    "#2196F3", "#673AB7", "#00CED1", "#009688", "#795548",
    "#4169E1", "#8B4513", "#FF69B4", "#4B0082", "#00FF7F",
    "#CD853F", "#00BFFF", "#FF6347", "#7B68EE", "#2E8B57",
    "#DAA520", "#9370DB", "#3CB371", "#FF8C00", "#BA55D3",
    "#20B2AA", "#CD5C5C", "#6B8E23", "#C71585", "#87CEEB"
];

// ==========================================
// Google Maps Funktionen
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    await initMap();
});

async function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 51.0237509, lng: 7.535209399 },
        zoom: 9,
        streetViewControl: false,
        mapTypeControl: false,
        fullscreenControl: false
    });
    
    // Lade zuerst die gespeicherten Routen
    try {
        const routesResponse = await fetch('/get_saved_routes');
        const routesData = await routesResponse.json();
        
        // Wenn es gespeicherte Routen gibt, zeige sie an
        if (routesData.status === 'success' && routesData.routes.length > 0) {
            displayRoutes(routesData);
            document.getElementById('resultsSection').style.display = 'block';
        }
        
        // Dann lade die Marker mit den bereits geladenen Routen
        await loadMarkers(routesData);
    } catch (error) {
        console.error("Fehler beim Laden der Daten:", error);
        // Lade Marker auch wenn keine Routen geladen werden konnten
        await loadMarkers();
    }
}

// Marker vom Server laden
async function loadMarkers(existingRoutesData = null) {
    clearMarkers();
    try {
        const response = await fetch('/get_markers');
        const data = await response.json();
        
        // Erstelle Map von Patient zu Stopp-Nummer
        const stopNumbers = new Map();
        if (existingRoutesData?.status === 'success') {
            existingRoutesData.routes.forEach(route => {
                route.stops.forEach((stop, index) => {
                    if (stop.visit_type !== 'TK') {
                        stopNumbers.set(stop.patient, (index + 1).toString());
                    }
                });
            });
        }

        // Info-Window Inhalt für Patienten
        data.patients.forEach(p => {
            const infoContent = `
                <div class="marker-info">
                    <strong>${p.name}</strong>
                    <div class="marker-visit-type ${
                        p.visit_type === 'HB' ? 'hb' : 
                        p.visit_type === 'TK' ? 'tk' : 
                        p.visit_type === 'Neuaufnahme' ? 'neuaufnahme' : ''
                    }">${p.visit_type}</div>
                    <div class="marker-address">${p.start_address || p.address}</div>
                </div>
            `;

            const infoWindow = new google.maps.InfoWindow({
                content: infoContent,
                maxWidth: 200
            });

            const marker = new google.maps.Marker({
                position: { lat: p.lat, lng: p.lng },
                map: map,
                label: p.visit_type !== 'TK' ? {
                    text: stopNumbers.get(p.name) || ' ',
                    color: '#FFFFFF',
                    fontSize: '10px',
                    fontWeight: 'bold'
                } : null,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 10,
                    fillColor: p.visit_type === 'HB' ? '#00ff00' :
                               p.visit_type === 'TK' ? '#007efc' :
                               p.visit_type === 'Neuaufnahme' ? '#ff4400' :
                               '#FFFFFF',
                    fillOpacity: 1,
                    strokeWeight: 2,
                    strokeColor: "#FFFFFF",
                    labelOrigin: new google.maps.Point(0, 0)
                }
            });

            marker.addListener('click', () => {
                infoWindow.open(map, marker);
            });

            markers.push(marker);
            marker.customData = {
                type: 'patient',
                name: p.name,
                isTK: p.visit_type === 'TK'
            };
        });

        // Info-Window Inhalt für Mitarbeiter
        data.vehicles.forEach(v => {
            const infoContent = `
                <div class="marker-info">
                    <strong>${v.name}</strong>
                    <div class="marker-function ${
                        v.funktion === 'Arzt' ? 'arzt' : 
                        v.funktion === 'Pflegekraft' ? 'pflege' : 
                        v.funktion?.toLowerCase().includes('honorararzt') ? 'honorar' : ''
                    }">${v.funktion || ''}</div>
                    <div class="marker-address">${v.start_address || v.address}</div>
                </div>
            `;

            const infoWindow = new google.maps.InfoWindow({
                content: infoContent,
                maxWidth: 200
            });

            const marker = new google.maps.Marker({
                position: { lat: v.lat, lng: v.lng },
                map: map,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 10,
                    fillColor: v.funktion === 'Arzt' ? '#FF0000' :
                               v.funktion === 'Pflegekraft' ? '#be00fe' :
                               v.funktion?.toLowerCase().includes('honorararzt') ? '#FF0000' :
                               '#666666',
                    fillOpacity: 1,
                    strokeWeight: 2,
                    strokeColor: "#FFFFFF"
                }
            });

            // Click-Event für Info-Window
            marker.addListener('click', () => {
                infoWindow.open(map, marker);
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

// Funktion zum Aktualisieren der Routendauer
function updateRouteDuration(routeCard, durationHrs = 0) {
    const header = routeCard.querySelector('h3');
    const durationSpan = header.querySelector('.duration');
    if (!durationSpan) return;

    const maxHours = parseFloat(durationSpan.textContent.split('/')[1].replace('h)', ''));
    
    // Setze die Textfarbe basierend auf dem Vergleich
    if (parseFloat(durationHrs) <= maxHours) {
        durationSpan.style.color = 'green';
    } else {
        durationSpan.style.color = 'red';
    }
    
    durationSpan.textContent = `${durationHrs} / ${maxHours}h`;
    routeCard.dataset.durationHrs = durationHrs;
}

// Route berechnen mit DirectionsService
async function calculateRoute(request, routeColor, routeCard) {
    return new Promise((resolve, reject) => {
        const directionsService = new google.maps.DirectionsService();
        
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
            if (status === 'OK') {
                directionsRenderer.setDirections(result);

                // Berechne Gesamtdauer (Fahrzeit)
                let totalDuration = 0;
                result.routes[0].legs.forEach(leg => {
                    totalDuration += leg.duration.value;
                });

                // Füge Verweilzeiten für jeden Stop hinzu
                const stops = routeCard.querySelector('.stops-container').querySelectorAll('.stop-card:not(.tk-stop)');
                stops.forEach(stop => {
                    const visitType = stop.querySelector('.visit-type').textContent;
                    totalDuration += VISIT_DWELL_TIMES[visitType] || 0;
                });
                
                // Konvertiere zu Stunden und aktualisiere die Anzeige
                const durationHrs = (totalDuration / 3600).toFixed(2);
                updateRouteDuration(routeCard, durationHrs);
                
                resolve();
            } else {
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
            displayRoutes(data);
            document.getElementById('resultsSection').style.display = 'block';
        } else {
            console.error("Optimierungsfehler:", data.message);
            window.location.reload();
        }
    } catch (error) {
        console.error("Fetch-Fehler bei /optimize_route:", error);
        alert("Netzwerkfehler bei der Routenoptimierung. Details in der Konsole.");
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
document.addEventListener('DOMContentLoaded', async function() {
    // Initialisiere den aktuellen Wochentag
    updateWeekdayDisplay();

    // Initialisiere die Map und lade die Routen
    await initMap();

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
        let tomorrowIndex;

        // Wenn heute Freitag (5), Samstag (6) oder Sonntag (0) ist,
        // dann setze auf Montag (1)
        if (todayIndex === 5 || todayIndex === 6 || todayIndex === 0) {
            tomorrowIndex = 1; // Montag
        } else {
            tomorrowIndex = (todayIndex + 1) % 7;
        }

        weekdaySelect.value = weekdays[tomorrowIndex];
        // Trigger 'change'
        weekdaySelect.dispatchEvent(new Event('change'));
    });

    // Flash Message mit Timeout
    const flashMessage = document.getElementById('flash-message');
    if (flashMessage) {
        setTimeout(() => {
            flashMessage.style.opacity = '0';
            flashMessage.style.transition = 'opacity 0.5s ease';
            setTimeout(() => {
                flashMessage.remove();
            }, 500);
        }, 10000);
    }
});

// ==========================================
// Routen-Management
// ==========================================
function displayRoutes(data) {
    clearRoutes();
    // Aktualisiere die Marker-Labels für die neuen Routen
    markers.forEach(marker => {
        if (marker.customData?.type === 'patient' && !marker.customData?.isTK) {
            // Suche die Route und Position des Patienten
            let found = false;
            data.routes.some(route => {
                const stopIndex = route.stops.findIndex(stop => stop.patient === marker.customData.name);
                if (stopIndex !== -1) {
                    marker.setLabel({
                        text: (stopIndex + 1).toString(),
                        color: '#FFFFFF',
                        fontSize: '10px',
                        fontWeight: 'bold'
                    });
                    found = true;
                    return true;
                }
                return false;
            });
            // Wenn der Patient in keiner Route ist, kein Label anzeigen
            if (!found) {
                marker.setLabel(null);
            }
        }
    });
    
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
            <div class="name-function-line">
                <span>${route.vehicle}</span>
                <span class="funktion-line ${
                    route.funktion === 'Arzt' ? 'arzt' : 
                    route.funktion === 'Pflegekraft' ? 'pflege' : 
                    route.funktion?.toLowerCase().includes('honorararzt') ? 'honorar' : ''
                }">${route.funktion || ''}</span>
            </div>
            <div class="duration" style="color: ${durationColor}">${route.duration_hrs || 0} / ${route.max_hours}h</div>
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
                    <div class="name-line ${
                        stop.visit_type === 'HB' ? 'hb' : 
                        stop.visit_type === 'TK' ? 'tk' : 
                        stop.visit_type === 'Neuaufnahme' ? 'neuaufnahme' : ''
                    }">
                        <strong>${stop.patient}</strong>
                        <span class="visit-type">${stop.visit_type || ''}</span>
                    </div>
                    <div class="address">${stop.address}</div>
                    <div class="time-info">${stop.time_info || ''}</div>
                    <div style="display:none" data-lat="${stop.location.lat}" data-lng="${stop.location.lng}"></div>
                    <div style="display:none" data-phone="${stop.phone_numbers || ''}"></div>
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
    const tkCard = document.createElement('div');
    tkCard.className = 'route-card tk-card';
    
    const tkHeader = document.createElement('h3');
    tkHeader.textContent = 'Nicht zugeordnete Telefonkontakte';
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
                <div class="name-line tk">
                    <strong>${tk.patient}</strong>
                    <span class="visit-type">TK</span>
                </div>
                <div class="address">${tk.address}</div>
                <div class="time-info">${tk.time_info || ''}</div>
                <div style="display:none" data-lat="${tk.location?.lat}" data-lng="${tk.location?.lng}"></div>
                <div style="display:none" data-phone="${tk.phone_numbers || ''}"></div>
            </div>
        `;
        
        tkStop.addEventListener('dragstart', handleDragStart);
        tkStop.addEventListener('dragend', handleDragEnd);
        
        tkContainer.appendChild(tkStop);
    });
    
    tkCard.appendChild(tkContainer);
    routesContainer.appendChild(tkCard);
    
    // Nicht zugeordnete reguläre Patienten anzeigen
    const regularCard = document.createElement('div');
    regularCard.className = 'route-card regular-card';
    
    const regularHeader = document.createElement('h3');
    regularHeader.textContent = 'Nicht zugeordnete reguläre Patienten';
    regularCard.appendChild(regularHeader);
    
    const regularContainer = document.createElement('div');
    regularContainer.className = 'stops-container';
    regularContainer.setAttribute('data-vehicle', 'regular');
    
    data.regular_stops.forEach(stop => {
        const regularStop = document.createElement('div');
        regularStop.className = 'stop-card regular-stop';
        regularStop.draggable = true;
        regularStop.innerHTML = `
            <div class="patient-info">
                <div class="name-line ${stop.visit_type.toLowerCase()}">
                    <strong>${stop.patient}</strong>
                    <span class="visit-type">${stop.visit_type}</span>
                </div>
                <div class="address">${stop.address}</div>
                <div class="time-info">${stop.time_info || ''}</div>
                <div style="display:none" data-lat="${stop.location?.lat}" data-lng="${stop.location?.lng}"></div>
                <div style="display:none" data-phone="${stop.phone_numbers || ''}"></div>
            </div>
        `;
        
        regularStop.addEventListener('dragstart', handleDragStart);
        regularStop.addEventListener('dragend', handleDragEnd);
        
        regularContainer.appendChild(regularStop);
    });
    
    regularCard.appendChild(regularContainer);
    routesContainer.appendChild(regularCard);
    
    routeResults.appendChild(routesContainer);

    
    document.querySelectorAll('.stops-container').forEach(container => {
        container.addEventListener('dragover', handleDragOver);
        container.addEventListener('drop', handleDrop);
    });
}

// ==========================================
// Drag & Drop Funktionalität
// ==========================================
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
    
    // Entferne ALLE existierenden Drop-Indikatoren
    document.querySelectorAll('.drop-indicator').forEach(el => el.remove());

    const dropContainer = e.target.closest('.stops-container');
    if (!dropContainer) return;

    const draggingElement = document.querySelector('.dragging');
    if (!draggingElement) return;

    const containerType = dropContainer.getAttribute('data-vehicle');
    const isTKStop = draggingElement.classList.contains('tk-stop');
    
    if ((containerType === 'tk' && !isTKStop) || 
        (containerType === 'regular' && isTKStop)) {
        e.dataTransfer.dropEffect = 'none';
        return;
    }

    // Erstelle neuen Drop-Indikator
    const indicator = document.createElement('div');
    indicator.className = 'drop-indicator';
    
    const afterElement = getDropPosition(dropContainer, e.clientY);
    if (afterElement) {
        afterElement.before(indicator);
    } else {
        dropContainer.appendChild(indicator);
    }
}

function getDropPosition(container, y) {
    const draggableElements = [...container.querySelectorAll('.stop-card:not(.dragging)')];
    
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

async function handleDrop(e) {
    e.preventDefault();
    const draggingElement = document.querySelector('.dragging');
    
    if (draggingElement) {
        const targetContainer = e.target.closest('.stops-container');
        if (!targetContainer) return;

        const sourceContainer = draggingElement.closest('.stops-container');
        if (!sourceContainer) return;

        const isTKContainer = targetContainer.getAttribute('data-vehicle') === 'tk';
        const isTKStop = draggingElement.classList.contains('tk-stop');
        
        // Erlaube nur TK-Stops in TK-Container und Regular-Stops in Regular/Mitarbeiter-Container
        if ((isTKContainer && !isTKStop) || 
            (!isTKContainer && isTKStop && targetContainer.getAttribute('data-vehicle') === 'regular')) {
            return;
        }

        // Entferne Drop-Indikatoren
        targetContainer.querySelectorAll('.drop-indicator').forEach(el => el.remove());
        
        // Füge das Element hinzu
        const afterElement = getDropPosition(targetContainer, e.clientY);
        if (afterElement) {
            afterElement.before(draggingElement);
        } else {
            targetContainer.appendChild(draggingElement);
        }
        
        // Aktualisiere die Stoppnummern
        updateStopNumbers();

        const routePromises = [];
        
        // Aktualisiere ALLE Mitarbeiter-Container
        document.querySelectorAll('.stops-container:not([data-vehicle="tk"]):not([data-vehicle="regular"])').forEach(container => {
            const routeCard = container.closest('.route-card');
            if (!routeCard) return;

            const routeColor = routeCard.style.borderColor;
            const regularStops = [...container.querySelectorAll('.stop-card:not(.tk-stop)')];
            
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

                routePromises.push(calculateRoute(request, routeColor, routeCard));
            }
        });

        try {
            // Warte auf die Routenberechnungen
            await Promise.all(routePromises);
            
            // Aktualisiere die optimierten Routen
            updateOptimizedRoutes();
        } catch (error) {
            console.error('Fehler bei der Routenberechnung:', error);
        }
    }
}

// Stoppnummern aktualisieren
function updateStopNumbers() {
    // Nur Container, die keine unassigned Container sind
    document.querySelectorAll('.stops-container:not([data-vehicle="tk"]):not([data-vehicle="regular"])').forEach(container => {
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
            
            // Aktualisiere auch das entsprechende Marker-Label
            const patientName = stop.querySelector('strong').textContent;
            markers.forEach(marker => {
                if (marker.customData?.name === patientName) {
                    marker.setLabel({
                        text: (index + 1).toString(),
                        color: '#FFFFFF',
                        fontSize: '10px',
                        fontWeight: 'bold'
                    });
                }
            });
        });
        
        // Entferne Labels von Markern, die nicht mehr in einer Route sind
        markers.forEach(marker => {
            if (marker.customData?.type === 'patient' && !marker.customData?.isTK) {
                const isInRoute = [...document.querySelectorAll('.stop-card:not(.tk-stop) strong')]
                    .some(strong => strong.textContent === marker.customData.name);
                if (!isInRoute) {
                    marker.setLabel(null);
                }
            }
        });
    });
}

// Optimierte Routen aktualisieren
function updateOptimizedRoutes() {
    const optimized_routes = [];
    const assigned_tk_stops = new Set();
    const assigned_regular_stops = new Set();
    
    document.querySelectorAll('.stops-container:not([data-vehicle="tk"]):not([data-vehicle="regular"])').forEach((container) => {
        const routeCard = container.closest('.route-card');
        const vehicleName = container.getAttribute('data-vehicle');

        const routeInfo = {
            vehicle: vehicleName,
            vehicle_start: null,
            duration_hrs: parseFloat(routeCard.dataset.durationHrs || 0),
            max_hours: parseFloat(routeCard.querySelector('.duration').textContent.split('/')[1].replace('h)', '')),
            funktion: routeCard.querySelector('.funktion-line')?.textContent || '',
            stops: []
        };
        
        // Sammle alle zugewiesenen Stops
        container.querySelectorAll('.stop-card').forEach(stop => {
            const isTKStop = stop.classList.contains('tk-stop');
            const locationDiv = stop.querySelector('[data-lat]');
            const stopInfo = {
                patient: stop.querySelector('strong').textContent,
                address: stop.querySelector('.address').textContent,
                visit_type: isTKStop ? "TK" : stop.querySelector('.visit-type').textContent,
                time_info: stop.querySelector('.time-info')?.textContent || "",
                phone_numbers: stop.querySelector('[data-phone]')?.dataset.phone || "",
                location: locationDiv ? {
                    lat: parseFloat(locationDiv.dataset.lat),
                    lng: parseFloat(locationDiv.dataset.lng)
                } : null
            };
            
            routeInfo.stops.push(stopInfo);
            
            if (isTKStop) {
                assigned_tk_stops.add(stopInfo.patient);
            } else {
                assigned_regular_stops.add(stopInfo.patient);
            }
        });
        
        optimized_routes.push(routeInfo);
    });
    
    // Sammle nicht zugewiesene Stops
    const unassigned_tk_stops = [];
    const unassigned_regular_stops = [];
    
    document.querySelector('.stops-container[data-vehicle="tk"]')?.querySelectorAll('.stop-card').forEach(stop => {
        const patient = stop.querySelector('strong').textContent;
        if (!assigned_tk_stops.has(patient)) {
            const locationDiv = stop.querySelector('[data-lat]');
            const stopInfo = {
                patient: patient,
                address: stop.querySelector('.address').textContent,
                visit_type: "TK",
                time_info: stop.querySelector('.time-info')?.textContent || "",
                phone_numbers: stop.querySelector('[data-phone]')?.dataset.phone || "",
                location: locationDiv ? {
                    lat: parseFloat(locationDiv.dataset.lat),
                    lng: parseFloat(locationDiv.dataset.lng)
                } : null
            };
            unassigned_tk_stops.push(stopInfo);
        }
    });
    
    document.querySelector('.stops-container[data-vehicle="regular"]')?.querySelectorAll('.stop-card').forEach(stop => {
        const patient = stop.querySelector('strong').textContent;
        if (!assigned_regular_stops.has(patient)) {
            const locationDiv = stop.querySelector('[data-lat]');
            const stopInfo = {
                patient: patient,
                address: stop.querySelector('.address').textContent,
                visit_type: stop.querySelector('.visit-type').textContent,
                time_info: stop.querySelector('.time-info')?.textContent || "",
                phone_numbers: stop.querySelector('[data-phone]')?.dataset.phone || "",
                location: locationDiv ? {
                    lat: parseFloat(locationDiv.dataset.lat),
                    lng: parseFloat(locationDiv.dataset.lng)
                } : null
            };
            unassigned_regular_stops.push(stopInfo);
        }
    });

    fetch('/update_routes', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            optimized_routes: optimized_routes,
            unassigned_tk_stops: unassigned_tk_stops,
            unassigned_regular_stops: unassigned_regular_stops
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
// Fügen Sie ein Event-Listener für das Drag-Ende hinzu
document.querySelectorAll('.stop-card').forEach(stopCard => {
    stopCard.addEventListener('dragend', () => {
        // Aktualisieren Sie die Routen nach dem Drag-Ende
        updateOptimizedRoutes();
    });
});
}

// ==========================================
// Routen-Export
// ==========================================
document.getElementById('exportButton')?.addEventListener('click', async () => {
    const tkContainer = document.querySelector('.stops-container[data-vehicle="tk"]');
    const regularContainer = document.querySelector('.stops-container[data-vehicle="regular"]');
    
    const hasTKStops = tkContainer && tkContainer.querySelectorAll('.stop-card').length > 0;
    const hasRegularStops = regularContainer && regularContainer.querySelectorAll('.stop-card').length > 0;
    
    if (hasTKStops || hasRegularStops) {
        // Erstelle den passenden Text basierend auf den nicht zugewiesenen Stops
        let warningText = '';
        if (hasTKStops && hasRegularStops) {
            warningText = 'Es gibt noch nicht zugeordnete TK-Fälle und reguläre Patienten.';
        } else if (hasTKStops) {
            warningText = 'Es gibt noch nicht zugeordnete TK-Fälle.';
        } else {
            warningText = 'Es gibt noch nicht zugeordnete reguläre Patienten.';
        }
        warningText += ' Möchten Sie trotzdem fortfahren?';
        
        // Setze den Text und zeige das Popup
        document.getElementById('export-confirmation-text').textContent = warningText;
        document.getElementById('export-confirmation').style.display = 'block';
    } else {
        // Wenn keine unassigned stops, direkt exportieren
        window.location.href = '/export_routes';
    }
});

document.getElementById('confirmExport')?.addEventListener('click', () => {
    // Hide popup and trigger download
    document.getElementById('export-confirmation').style.display = 'none';
    window.location.href = '/export_routes';
});


// ==========================================
// UI Event Handler
// ==========================================
function toggleInfo(id) {
    // Schließe zuerst alle Popups
    document.querySelectorAll('.info-popup').forEach(popup => {
        if (popup.id !== id) {
            popup.style.display = 'none';
        }
    });

    // Toggle das gewählte Popup
    const popup = document.getElementById(id);
    if (popup) {
        popup.style.display = popup.style.display === 'block' ? 'none' : 'block';
    }
}

// Schließe Popups auch beim Klick außerhalb
document.addEventListener('click', function(event) {
    if (!event.target.closest('.info-popup') && 
        !event.target.closest('.info-icon') && 
        !event.target.closest('#exportButton')) {
        document.querySelectorAll('.info-popup').forEach(popup => {
            popup.style.display = 'none';
        });
    }
});

