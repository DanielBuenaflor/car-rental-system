// Location Map for Booking Page
// Guard against double execution
if (!window._locationMapInitialized) {
window._locationMapInitialized = true;

// Initialize map when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initLocationMaps();
});

let pickupMap, returnMap, customPickupMap, customReturnMap;
let pickupLocations = [];
let pickupMarkers = [], returnMarkers = [];
let currentOneWayFee = 0;
let currentDeliveryFee = 0;

async function initLocationMaps() {
    try {
        const response = await fetch('/api/locations');
        const data = await response.json();
        pickupLocations = data.locations || [];
        
        if (typeof L === 'undefined') {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(link);
            
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            script.onload = () => initMaps();
            document.head.appendChild(script);
        } else {
            initMaps();
        }
    } catch (e) {
        console.error('Error loading locations:', e);
    }
}

function initMaps() {
    const pickupContainer = document.getElementById('pickupLocationMap');
    const returnContainer = document.getElementById('returnLocationMap');
    
    if (pickupContainer) {
        pickupMap = L.map('pickupLocationMap').setView([12.8797, 121.7740], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(pickupMap);
    }
    
    if (returnContainer) {
        returnMap = L.map('returnLocationMap').setView([12.8797, 121.7740], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(returnMap);
    }

    if (document.getElementById('customPickupMap')) {
        customPickupMap = L.map('customPickupMap').setView([12.8797, 121.7740], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(customPickupMap);
    }

    if (document.getElementById('customReturnMap')) {
        customReturnMap = L.map('customReturnMap').setView([12.8797, 121.7740], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(customReturnMap);
    }
    
    renderLocationCards(pickupLocations, 'pickup');
    renderLocationCards(pickupLocations, 'return');
    
    setupLocationTabs();
    
    // Trigger map resize after tab switch
    setTimeout(() => {
        if (pickupMap) pickupMap.invalidateSize();
        if (returnMap) returnMap.invalidateSize();
    }, 200);
}

function renderLocationCards(locations, type) {
    const container = document.getElementById(type + 'LocationCards');
    if (!container || !locations.length) return;
    
    container.innerHTML = locations.map(loc => `
        <div class="location-card" data-id="${loc.id}" data-name="${loc.name}" data-type="${type}" data-lat="${loc.latitude}" data-lng="${loc.longitude}">
            <div class="branch-type">${loc.branch_type}</div>
            <div class="name">${loc.name}</div>
            <div class="address">${loc.address}</div>
        </div>
    `).join('');
    
    container.querySelectorAll('.location-card').forEach(card => {
        card.addEventListener('click', () => selectLocation(card, type));
    });
    
    // Add marker for first location
    if (locations.length > 0) {
        const map = type === 'pickup' ? pickupMap : returnMap;
        if (map) {
            const marker = L.marker([locations[0].latitude, locations[0].longitude])
                .addTo(map)
                .bindPopup(locations[0].name);
            if (type === 'pickup') pickupMarkers.push(marker);
            else returnMarkers.push(marker);
            map.setView([locations[0].latitude, locations[0].longitude], 10);
        }
    }
}

function selectLocation(card, type) {
    const id = card.dataset.id;
    const name = card.dataset.name;
    const lat = parseFloat(card.dataset.lat);
    const lng = parseFloat(card.dataset.lng);
    const loc = pickupLocations.find(l => l.id == id);
    
    document.querySelectorAll(`#${type}LocationCards .location-card`).forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    
    const idField = document.getElementById(type + '_location_id');
    const nameField = document.getElementById(type + '_location_name');
    if (idField) idField.value = id;
    if (nameField) nameField.value = name;
    
    const selectedDiv = document.getElementById(type + 'SelectedLocation');
    const nameDiv = document.getElementById(type + 'SelectedName');
    if (selectedDiv && nameDiv) {
        selectedDiv.style.display = 'block';
        nameDiv.textContent = name;
    }
    
    const map = type === 'pickup' ? pickupMap : returnMap;
    if (map && lat && lng) {
        map.setView([lat, lng], 12);
    }
    
    calculateLocationFee();
}

function setupLocationTabs() {
    document.querySelectorAll('.location-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            const parent = tab.closest('.form-group');
            if (!parent) return;
            
            parent.querySelectorAll('.location-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            parent.querySelectorAll('.location-section').forEach(s => s.classList.remove('active'));
            const section = document.getElementById(tabId);
            if (section) section.classList.add('active');
            
            // Invalidate map size after tab switch
            setTimeout(() => {
                if (tabId === 'pickup-map' && pickupMap) pickupMap.invalidateSize();
                if (tabId === 'return-map' && returnMap) returnMap.invalidateSize();
            }, 150);
        });
    });
}

async function calculateLocationFee() {
    const pickupIdField = document.getElementById('pickup_location_id');
    const returnIdField = document.getElementById('return_location_id');
    const customPickupAddress = document.getElementById('custom_pickup_address');
    const customReturnAddress = document.getElementById('custom_return_address');
    
    if (!pickupIdField || !returnIdField) return;
    
    const pickupId = pickupIdField.value;
    const returnId = returnIdField.value;
    
    const isCustomPickup = customPickupAddress && customPickupAddress.value.trim().length > 0;
    const isCustomReturn = customReturnAddress && customReturnAddress.value.trim().length > 0;
    
    currentOneWayFee = 0;
    currentDeliveryFee = 0;
    
    if (isCustomPickup || isCustomReturn) {
        currentDeliveryFee = 500;
    }
    
    if (pickupId && returnId && !isCustomPickup && !isCustomReturn) {
        try {
            const response = await fetch('/api/locations/pricing', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({from_location_id: parseInt(pickupId), to_location_id: parseInt(returnId)})
            });
            const data = await response.json();
            currentOneWayFee = data.one_way_fee || 0;
        } catch (e) {
            console.error('Error calculating location fee:', e);
        }
    }
    
    // Update summary if function exists
    if (typeof calculateSummary === 'function') {
        calculateSummary();
    }
}

// Export for use in booking form
window.calculateLocationFee = calculateLocationFee;
window.currentOneWayFee = currentOneWayFee;
window.currentDeliveryFee = currentDeliveryFee;

let geocodeTimeout;
async function geocodeAddress(address, type = 'pickup') {
    if (!address || address.length < 3) return;

    try {
        const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}`, {
            headers: {
                'User-Agent': 'CarRentalPro/1.0'
            }
        });
        const data = await response.json();
        
        if (data.length > 0) {
            const lat = parseFloat(data[0].lat);
            const lng = parseFloat(data[0].lon);
            
            const map = type === 'pickup' ? customPickupMap : customReturnMap;
            if (map) {
                map.setView([lat, lng], 15);
                map.eachLayer(layer => {
                    if (layer instanceof L.Marker) map.removeLayer(layer);
                });
                L.marker([lat, lng]).addTo(map);
            }
            
            const latField = document.getElementById(`custom_${type}_lat`);
            const lngField = document.getElementById(`custom_${type}_lng`);
            if (latField) latField.value = lat;
            if (lngField) lngField.value = lng;
        }
    } catch (e) {
        console.error('Geocoding error:', e);
    }
}

function setupCustomAddressInput() {
    const customAddressInput = document.getElementById('custom_pickup_address');
    if (customAddressInput) {
        customAddressInput.addEventListener('input', (e) => {
            clearTimeout(geocodeTimeout);
            geocodeTimeout = setTimeout(() => geocodeAddress(e.target.value, 'pickup'), 1000);
        });
    }
    
    const customReturnInput = document.getElementById('custom_return_address');
    if (customReturnInput) {
        customReturnInput.addEventListener('input', (e) => {
            clearTimeout(geocodeTimeout);
            geocodeTimeout = setTimeout(() => geocodeAddress(e.target.value, 'return'), 1000);
        });
    }
}

setupCustomAddressInput();
}
