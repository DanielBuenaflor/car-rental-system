// ============================================
// Filter Functions
// ============================================

function openFilterModal() {
    var modal = document.getElementById('filterModal');
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeFilterModal() {
    var modal = document.getElementById('filterModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function applyFiltersFromModal() {
    currentFilters.transmission = document.getElementById('filterTransmission') ? document.getElementById('filterTransmission').value : '';
    currentFilters.fuel_type = document.getElementById('filterFuelType') ? document.getElementById('filterFuelType').value : '';
    currentFilters.seating_capacity = document.getElementById('filterSeats') ? document.getElementById('filterSeats').value : '';
    currentFilters.min_price = document.getElementById('filterMinPrice') ? document.getElementById('filterMinPrice').value : '';
    currentFilters.max_price = document.getElementById('filterMaxPrice') ? document.getElementById('filterMaxPrice').value : '';
    
    applyFilters();
    closeFilterModal();
}

function resetAllFilters() {
    var elements = ['filterTransmission', 'filterFuelType', 'filterSeats', 'filterMinPrice', 'filterMaxPrice', 'filterPickupDate', 'filterReturnDate', 'searchInput'];
    elements.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) {
            el.value = '';
        }
    });
    
    currentFilters = {
        search: '',
        transmission: '',
        fuel_type: '',
        seating_capacity: '',
        min_price: '',
        max_price: '',
        start_date: '',
        end_date: ''
    };
    
    applyFilters();
}

function updateActiveFiltersDisplay() {
    var container = document.getElementById('activeFiltersContainer');
    if (!container) return;
    
    var filtersHtml = '';
    
    if (currentFilters.search) {
        filtersHtml += '<div class="filter-tag">Search: ' + currentFilters.search + ' <i class="fas fa-times" onclick="removeFilter(\'search\')"></i></div>';
    }
    if (currentFilters.transmission) {
        filtersHtml += '<div class="filter-tag">Transmission: ' + currentFilters.transmission + ' <i class="fas fa-times" onclick="removeFilter(\'transmission\')"></i></div>';
    }
    if (currentFilters.fuel_type) {
        filtersHtml += '<div class="filter-tag">Fuel: ' + currentFilters.fuel_type + ' <i class="fas fa-times" onclick="removeFilter(\'fuel_type\')"></i></div>';
    }
    if (currentFilters.seating_capacity) {
        filtersHtml += '<div class="filter-tag">Seats: ' + currentFilters.seating_capacity + ' <i class="fas fa-times" onclick="removeFilter(\'seating_capacity\')"></i></div>';
    }
    if (currentFilters.min_price) {
        filtersHtml += '<div class="filter-tag">Min: ₱' + currentFilters.min_price + ' <i class="fas fa-times" onclick="removeFilter(\'min_price\')"></i></div>';
    }
    if (currentFilters.max_price) {
        filtersHtml += '<div class="filter-tag">Max: ₱' + currentFilters.max_price + ' <i class="fas fa-times" onclick="removeFilter(\'max_price\')"></i></div>';
    }
    
    container.innerHTML = filtersHtml;
}

function removeFilter(filterKey) {
    if (filterKey === 'search') {
        currentFilters.search = '';
        var searchInput = document.getElementById('searchInput');
        if (searchInput) searchInput.value = '';
    } else {
        currentFilters[filterKey] = '';
    }
    
    updateActiveFiltersDisplay();
    applyFilters();
}

function applyFilters() {
    // Update the display first
    currentFilters.search = document.getElementById('searchInput') ? document.getElementById('searchInput').value : '';
    
    var filters = {
        search: currentFilters.search,
        transmission: currentFilters.transmission,
        fuel_type: currentFilters.fuel_type,
        seating_capacity: currentFilters.seating_capacity,
        min_price: currentFilters.min_price,
        max_price: currentFilters.max_price,
        start_date: currentFilters.start_date,
        end_date: currentFilters.end_date
    };
    
    updateActiveFiltersDisplay();
    
    var loadingSpinner = document.getElementById('loadingSpinner');
    var vehiclesContainer = document.getElementById('vehiclesContainer');
    
    if (loadingSpinner) loadingSpinner.style.display = 'block';
    if (vehiclesContainer) vehiclesContainer.innerHTML = '';
    
    fetch('/api/vehicles/filter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filters)
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        displayVehicles(data.vehicles);
        if (loadingSpinner) loadingSpinner.style.display = 'none';
    })
    .catch(function(error) {
        console.error('Error:', error);
        if (loadingSpinner) loadingSpinner.style.display = 'none';
        if (vehiclesContainer) {
            vehiclesContainer.innerHTML = '<div class="no-results"><i class="fas fa-exclamation-circle fa-3x"></i><h3>Error Loading Vehicles</h3><p>Please try again later.</p></div>';
        }
    });
}

// Search debounce
var searchTimeout;
var searchInputEl = document.getElementById('searchInput');
if (searchInputEl) {
    searchInputEl.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(function() {
            applyFilters();
        }, 500);
    });
}

// ============================================
// Display Vehicles Function
// ============================================

function displayVehicles(vehicles) {
    var container = document.getElementById('vehiclesContainer');
    if (!container) return;
    
    if (!vehicles || vehicles.length === 0) {
        container.innerHTML = '<div class="no-results">' +
            '<i class="fas fa-search fa-3x" style="color: #cbd5e1;"></i>' +
            '<h3>No vehicles found</h3>' +
            '<p>Try adjusting your search filters to find more vehicles.</p>' +
            '<button class="btn-secondary" onclick="resetAllFilters()">Reset Filters</button>' +
        '</div>';
        return;
    }
    
    var html = '<div class="fleet-grid">';
    vehicles.forEach(function(vehicle) {
        html += '<div class="fleet-card" onclick="openVehicleModal(' + vehicle.id + ')">' +
            '<div class="fleet-image">' +
                (vehicle.primary_image ? 
                    '<img src="' + vehicle.primary_image + '" alt="' + vehicle.brand_name + ' ' + vehicle.model + '">' : 
                    '<i class="fas fa-car"></i>') +
            '</div>' +
            '<div class="fleet-info">' +
                '<h3>' + vehicle.brand_name + ' ' + vehicle.model + '</h3>' +
                '<div class="fleet-price">₱' + vehicle.daily_rate + '/day <small>+ tax</small></div>' +
                '<ul class="fleet-features">' +
                    '<li><i class="fas fa-calendar-alt"></i> ' + vehicle.year + '</li>' +
                    '<li><i class="fas fa-cog"></i> ' + vehicle.transmission + '</li>' +
                    '<li><i class="fas fa-gas-pump"></i> ' + vehicle.fuel_type + '</li>' +
                    '<li><i class="fas fa-users"></i> ' + vehicle.seating_capacity + ' seats</li>' +
                '</ul>' +
                '<button class="btn-primary" style="width:100%; text-align:center;" onclick="event.stopPropagation(); openVehicleModal(' + vehicle.id + ')">View Details</button>' +
            '</div>' +
        '</div>';
    });
    html += '</div>';
    container.innerHTML = html;
}