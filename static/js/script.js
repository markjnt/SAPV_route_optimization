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

// Initialisiere die Map beim Laden der Seite
document.addEventListener('DOMContentLoaded', async () => {
    // Warte bis das Google Maps API verfügbar ist
    if (typeof google === 'undefined') {
        await new Promise(resolve => {
            const checkGoogle = setInterval(() => {
                if (typeof google !== 'undefined') {
                    clearInterval(checkGoogle);
                    resolve();
                }
            }, 100);
        });
    }
    await initMap();
});

// Initialisiere die Map
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

            // Click-Event für Info-Window
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
            marker.customData = {
                type: 'vehicle',
                name: v.name
            };
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

// ==========================================
// Buttons, Flash Messages, DOM-Events und Wochentags-Funktionalität
// ==========================================

// Button "Route optimieren"
document.getElementById('optimizeButton').addEventListener('click', async () => {
    clearRoutes(); // Alte Routen entfernen
    
    // Animation starten
    const button = document.getElementById('optimizeButton');
    const icon = button.querySelector('i');
    icon.classList.add('spinning');
    button.disabled = true;
    
    try {
        // Sende eine POST-Anfrage an den Server, um die Routen zu optimieren
        const response = await fetch('/optimize_route', { method: 'POST' });
        const data = await response.json();

        // Wenn die Optimierung erfolgreich war, zeige die Routen an
        if (data.status === 'success') {
            displayRoutes(data);
            document.getElementById('resultsSection').style.display = 'block';
        } else {
            console.error("Optimierungsfehler:", data.message);
            window.location.reload();
        }
    } catch (error) {
        console.error("Fetch-Fehler bei /optimize_route:", error);
    } finally {
        // Animation stoppen
        icon.classList.remove('spinning');
        button.disabled = false;
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
        console.error("Fehler beim Abrufen des aktuellen Wochentags:", err);
    }
}

// DOM-Events für Wochentags-Funktionalität, Button "Morgen" und Flash Message
document.addEventListener('DOMContentLoaded', async function() {

    // Initialisiere den aktuellen Wochentag
    updateWeekdayDisplay();

    // Initialisiere die Map und lade die Routen
    await initMap();

    const weekdaySelect = document.getElementById('weekdaySelect');
    const tomorrowBtn = document.getElementById('tomorrowBtn');

    // Array der Wochentage
    const weekdays = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];

    // Wochentag-Dropdown ändern, Server-Anfrage senden und Wochentag anzeigen
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
            console.error("Fehler beim Aktualisieren des Wochentags:", err);
        }
    });

    // Button "Morgen"
    tomorrowBtn.addEventListener('click', async function() {
        const today = new Date();
        const todayIndex = today.getDay();
        let tomorrowIndex;

        // Wenn heute Freitag (5), Samstag (6) oder Sonntag (0) ist, dann setze auf Montag (1)
        if (todayIndex === 5 || todayIndex === 6 || todayIndex === 0) {
            tomorrowIndex = 1; // Montag
        } else {
            tomorrowIndex = (todayIndex + 1) % 7;
        }

        // Wochentag-Dropdown ändern und Trigger 'change'
        weekdaySelect.value = weekdays[tomorrowIndex];
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

// Routen anzeigen
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
    
    // Container für alle Routen
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

        // Fahrzeug-Header mit Name, Funktion und Duration
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

        // Container für alle Stopps
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
            
            // Drag & Drop-Events für Stopps
            stopCard.addEventListener('dragstart', handleDragStart);
            stopCard.addEventListener('dragend', handleDragEnd);
            
            stopsContainer.appendChild(stopCard);
        });
        
        routeCard.appendChild(stopsContainer);
        routesContainer.appendChild(routeCard);
        routeCard.dataset.vehicleStartLat = route.vehicle_start.lat;
        routeCard.dataset.vehicleStartLng = route.vehicle_start.lng;
    });
    
    // Container für unzugeordnete Telefonkontakte
    const tkCard = document.createElement('div');
    tkCard.className = 'route-card tk-card';
    
    const tkHeader = document.createElement('h3');
    tkHeader.textContent = 'Unzugewiesene Telefonkontakte';
    tkCard.appendChild(tkHeader);
    
    const tkContainer = document.createElement('div');
    tkContainer.className = 'stops-container';
    tkContainer.setAttribute('data-vehicle', 'tk');
    
    // Telefonkontakte erstellen
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
        
        // Drag & Drop-Events für Telefonkontakte
        tkStop.addEventListener('dragstart', handleDragStart);
        tkStop.addEventListener('dragend', handleDragEnd);
        
        tkContainer.appendChild(tkStop);
    });
    
    tkCard.appendChild(tkContainer);
    routesContainer.appendChild(tkCard);
    
    // Container für unzugewiesene Hausbesuche
    const regularCard = document.createElement('div');
    regularCard.className = 'route-card regular-card';
    
    const regularHeader = document.createElement('h3');
    regularHeader.textContent = 'Unzugewiesene Hausbesuche';
    regularCard.appendChild(regularHeader);
    
    const regularContainer = document.createElement('div');
    regularContainer.className = 'stops-container';
    regularContainer.setAttribute('data-vehicle', 'regular');
    
    // Hausbesuche erstellen
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
        
        // Drag & Drop-Events für Hausbesuche
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

    // Effekte für Routen-Hover anzeigen
    setupRouteHoverEffects();
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
    const directionsService = new google.maps.DirectionsService();
    
    return new Promise((resolve, reject) => {
        directionsService.route(request, (result, status) => {
            if (status === 'OK') {
                const renderer = new google.maps.DirectionsRenderer({
                    map: map,
                    directions: result,
                    suppressMarkers: true,
                    preserveViewport: true,
                    polylineOptions: {
                        strokeColor: routeColor,
                        strokeOpacity: 0.8,
                        strokeWeight: 4
                    }
                });

                // Setze den Namen der Route in customData
                const vehicleName = routeCard.querySelector('.stops-container').getAttribute('data-vehicle');
                renderer.customData = {
                    vehicleName: vehicleName
                };

                directionsRenderers.push(renderer);

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

                resolve(result);
            } else {
                reject(status);
            }
        });
    });
}

// ==========================================
// Drag & Drop Funktionalität
// ==========================================

// Drag-Start-Event für Stopps
function handleDragStart(e) {
    e.target.classList.add('dragging');
    e.dataTransfer.setData('text/plain', e.target.innerHTML);
    e.dataTransfer.setData('type', e.target.classList.contains('tk-stop') ? 'tk' : 'regular');
}

// Drag-End-Event für Stopps
function handleDragEnd(e) {
    e.target.classList.remove('dragging');
}

// Drag-Over-Event für Stopps
function handleDragOver(e) {
    e.preventDefault();
    
    // Entferne alle existierenden Drop-Indikatoren
    document.querySelectorAll('.drop-indicator').forEach(el => el.remove());

    // Hole das Drop-Container
    const dropContainer = e.target.closest('.stops-container');
    if (!dropContainer) return;

    // Hole das Dragging-Element
    const draggingElement = document.querySelector('.dragging');
    if (!draggingElement) return;

    // Hole den Container-Typ
    const containerType = dropContainer.getAttribute('data-vehicle');
    const isTKStop = draggingElement.classList.contains('tk-stop');
    
    // Verhindere Drag & Drop, wenn das falsche Element in den falschen Container gedroppt wird
    if ((containerType === 'tk' && !isTKStop) || 
        (containerType === 'regular' && isTKStop)) {
        e.dataTransfer.dropEffect = 'none';
        return;
    }

    // Erstelle neuen Drop-Indikator
    const indicator = document.createElement('div');
    indicator.className = 'drop-indicator';
    
    // Wenn es ein TK-Stop ist, zeige den Indikator immer am Ende
    if (isTKStop) {
        dropContainer.appendChild(indicator);
    } else {
        // Für normale Stops, zeige den Indikator an der Drop-Position
        const afterElement = getDropPosition(dropContainer, e.clientY);
        if (afterElement) {
            afterElement.before(indicator);
        } else {
            dropContainer.appendChild(indicator);
        }
    }
}

// Funktion zum Ermitteln der Drop-Position
function getDropPosition(container, y) {
    const draggableElements = [...container.querySelectorAll('.stop-card:not(.dragging)')];
    
    // Finde den nächsten Stop, der über der Drop-Position liegt
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        
        // Wenn der aktuelle Stop näher zur Drop-Position ist als der vorherige, aktualisiere die nächste Position
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// Drop-Event für Stopps
async function handleDrop(e) {
    e.preventDefault();
    const draggingElement = document.querySelector('.dragging');
    
    if (draggingElement) {
        // Hole das Drop-Container
        const targetContainer = e.target.closest('.stops-container');
        if (!targetContainer) return;

        // Hole das Source-Container
        const sourceContainer = draggingElement.closest('.stops-container');
        if (!sourceContainer) return;

        // Überprüfe, ob das Ziel ein TK-Container ist
        const isTKContainer = targetContainer.getAttribute('data-vehicle') === 'tk';
        // Überprüfe, ob das Dragging-Element ein TK-Stop ist
        const isTKStop = draggingElement.classList.contains('tk-stop');
        
        // Erlaube nur TK-Stops in TK-Container und Regular-Stops in Regular/Mitarbeiter-Container
        if ((isTKContainer && !isTKStop) || 
            (!isTKContainer && isTKStop && targetContainer.getAttribute('data-vehicle') === 'regular')) {
            return;
        }

        // Entferne Drop-Indikatoren
        targetContainer.querySelectorAll('.drop-indicator').forEach(el => el.remove());
        
        // Wenn es ein TK-Stop ist, füge ihn ans Ende an
        if (isTKStop) {
            targetContainer.appendChild(draggingElement);
        } else {
            // Für normale Stops, füge sie an der Drop-Position ein
            const afterElement = getDropPosition(targetContainer, e.clientY);
            if (afterElement) {
                afterElement.before(draggingElement);
            } else {
                targetContainer.appendChild(draggingElement);
            }
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
            
            // Wenn keine Hausbesuche in der Route sind, setze die Dauer auf 0
            if (regularStops.length === 0) {
                updateRouteDuration(routeCard, 0);
            } else {
                // Hole den Startpunkt der Route
                const origin = new google.maps.LatLng(
                    routeCard.dataset.vehicleStartLat, 
                    routeCard.dataset.vehicleStartLng
                );
                
                // Erstelle Waypoints für die Route
                const waypoints = regularStops.map(stop => ({
                    location: new google.maps.LatLng(
                        parseFloat(stop.querySelector('[data-lat]').dataset.lat),
                        parseFloat(stop.querySelector('[data-lat]').dataset.lng)
                    ),
                    stopover: true
                }));

                // Erstelle die DirectionsRequest
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
            await Promise.all(routePromises);
            
            // Hole den Namen direkt vom targetContainer
            const vehicleName = targetContainer.getAttribute('data-vehicle');
            
            // Warte auf das Update der optimierten Routen
            await new Promise(resolve => {
                updateOptimizedRoutes();
                // Gib dem System Zeit, die Routen zu aktualisieren
                setTimeout(resolve, 100);
            });

            // Setze Zoom zurück
            map.setZoom(9);
            
            // Blende alle Routen aus
            directionsRenderers.forEach(renderer => {
                renderer.setMap(null);
            });

            // Blende die Route des Mitarbeiters wieder ein, wo der Drop stattgefunden hat
            directionsRenderers.forEach(renderer => {
                if (renderer.customData?.vehicleName === vehicleName) {
                    renderer.setMap(map);
                }
            });
            
        } catch (error) {
            console.error('Fehler bei der Routenberechnung:', error);
        }
    }
}

// Stoppnummern aktualisieren, wenn ein Stop gezogen wurde
function updateStopNumbers() {
    // Nur Container, die keine unzugewiesenen Container sind
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

// Optimierte Routen aktualisieren für Backend, wenn ein Stop gezogen wurde
function updateOptimizedRoutes() {
    const optimized_routes = [];
    const assigned_tk_stops = new Set();
    const assigned_regular_stops = new Set();

    // Sammle alle zugewiesenen Routen
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
            
            // Füge den Stop zu der Route hinzu
            routeInfo.stops.push(stopInfo);
            
            // Füge den Stop zu den zugewiesenen Stops hinzu
            if (isTKStop) {
                assigned_tk_stops.add(stopInfo.patient);
            } else {
                assigned_regular_stops.add(stopInfo.patient);
            }
        });
        
        optimized_routes.push(routeInfo);
    });
    
    // Sammle alle unzugewiesenen Stops
    const unassigned_tk_stops = [];
    const unassigned_regular_stops = [];
    
    // Sammle alle unzugewiesenen TK-Stops
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
    
    // Sammle alle unzugewiesenen Regular-Stops
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

    // Sende die Routen und unzugewiesenen Stops an das Backend
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
}

// ==========================================
// Routen-Export
// ==========================================

// Event-Listener für den Export-Button
document.getElementById('exportButton')?.addEventListener('click', async () => {
    const tkContainer = document.querySelector('.stops-container[data-vehicle="tk"]');
    const regularContainer = document.querySelector('.stops-container[data-vehicle="regular"]');
    
    // Überprüfe, ob es unzugewiesene TK- oder Regular-Stops gibt
    const hasTKStops = tkContainer && tkContainer.querySelectorAll('.stop-card').length > 0;
    const hasRegularStops = regularContainer && regularContainer.querySelectorAll('.stop-card').length > 0;
    
    // Wenn es Stops gibt, zeige ein Popup an
    if (hasTKStops || hasRegularStops) {
        // Erstelle den passenden Text basierend auf den unzugewiesenen Stops
        let warningText = '';
        if (hasTKStops && hasRegularStops) {
            warningText = 'Es gibt noch unzugewiesene Telefonkontakte und Hausbesuche.';
        } else if (hasTKStops) {
            warningText = 'Es gibt noch unzugewiesene Telefonkontakte.';
        } else {
            warningText = 'Es gibt noch unzugewiesene Hausbesuche.';
        }
        warningText += ' Möchten Sie trotzdem fortfahren?';
        
        // Setze den Text und zeige das Popup
        document.getElementById('export-confirmation-text').textContent = warningText;
        document.getElementById('export-confirmation').style.display = 'block';
    } else {
        // Wenn keine unzugewiesenen Stops, direkt exportieren
        window.location.href = '/export_routes';
    }
});

// Event-Listener für den Popup-Confirm-Button
document.getElementById('confirmExport')?.addEventListener('click', () => {
    // Verstecke das Popup und starte den Download
    document.getElementById('export-confirmation').style.display = 'none';
    window.location.href = '/export_routes';
});


// ==========================================
// UI Event Handler
// ==========================================

// Funktion zum Toggle der Info-Popups
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


// ==========================================
// Route-Card Hover-Effekte
// ==========================================

// Event-Listener für Route-Card Hover
function setupRouteHoverEffects() {
    document.querySelectorAll('.route-card').forEach(card => {
        // Hover-Effekt für die Route
        card.addEventListener('mouseenter', () => highlightRoute(card, true));
        card.addEventListener('mouseleave', () => highlightRoute(card, false));
        
        // Hover-Effekt für einzelne Stops
        card.querySelectorAll('.stop-card').forEach(stop => {
            stop.addEventListener('mouseenter', () => highlightStop(stop, true));
            stop.addEventListener('mouseleave', () => highlightStop(stop, false));
        });
    });
}

// Funktion zum Highlight der Route
function highlightRoute(card, highlight) {
    const container = card.querySelector('.stops-container');
    const vehicleName = container ? container.getAttribute('data-vehicle') : null;
    
    // Hole alle Patienten-Namen dieser Route
    const stopNames = [...card.querySelectorAll('.stop-card strong')].map(strong => strong.textContent);
    
    // Blende alle Routen aus/ein
    directionsRenderers.forEach(renderer => {
        // Prüfe ob es die Route des Mitarbeiters ist
        const isRelevantRoute = renderer.customData?.vehicleName === vehicleName;
        
        // Setze die Map auf null, wenn die Route nicht relevant ist
        if (isRelevantRoute) {
            renderer.setMap(map);
        } else {
            renderer.setMap(highlight ? null : map);
        }
    });

    // Blende alle Marker aus/ein
    markers.forEach(marker => {
        const isRelevantPatient = marker.customData?.type === 'patient' && stopNames.includes(marker.customData.name);
        const isRelevantVehicle = marker.customData?.type === 'vehicle' && 
                                 marker.customData.name === vehicleName;
        
        // Setze die Map auf null, wenn der Marker nicht relevant ist
        marker.setMap(
            (isRelevantPatient || isRelevantVehicle) ? 
            map : 
            (highlight ? null : map)
        );
    });
}

// Funktion zum Highlight des Patienten
function highlightStop(stop, highlight) {
    const patientName = stop.querySelector('strong').textContent;
    
    // Alle Marker Highlight zurücksetzen
    markers.forEach(marker => {
        marker.setZIndex(undefined);
                
        if (marker.animationInterval) {
            clearInterval(marker.animationInterval);
            marker.animationInterval = null;
        }
        
        const icon = marker.getIcon();
        marker.setIcon({
            ...icon,
            scale: 10
        });
        
        // Zoom zurück auf Übersicht
        map.setZoom(9);  // Ursprünglicher Zoom-Level
    });

    // Highlight des Patienten
    markers.forEach(marker => {
        if (marker.customData?.name === patientName) {
            if (highlight) {
                let scale = 10;
                let growing = true;
                
                // Setze den Marker in den Vordergrund
                marker.setZIndex(google.maps.Marker.MAX_ZINDEX + 1);
                
                // Animation des Markers
                marker.animationInterval = setInterval(() => {
                    if (growing) {
                        scale += 1;
                        if (scale >= 14) growing = false;
                    } else {
                        scale -= 1;
                        if (scale <= 10) growing = true;
                    }
                    
                    const icon = marker.getIcon();
                    marker.setIcon({
                        ...icon,
                        scale: scale
                    });
                }, 100);
                
                // Zoome zur Position des Markers
                map.setZoom(10);  // Höherer Zoom-Level
                map.panTo(marker.getPosition());
                
            }
        }
    });
}

