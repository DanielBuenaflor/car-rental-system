// ============================================
// Fleet-specific Display (with availability badge)
// ============================================

var fleetDisplayVehicles = function(vehicles) {
    var container = document.getElementById('vehiclesContainer');
    if (!container) return;
    
    if (!vehicles || vehicles.length === 0) {
        container.innerHTML = '<div class="no-results">' +
            '<i class="fas fa-search fa-3x"></i>' +
            '<h3>No Vehicles Found</h3>' +
            '<p>Try adjusting your search filters to find more vehicles.</p>' +
            '<button class="btn-secondary" onclick="resetAllFilters()" style="margin-top: 20px;">' +
                '<i class="fas fa-undo"></i> Reset Filters' +
            '</button>' +
        '</div>';
        return;
    }
    
    var isLoggedIn = window.isLoggedIn || false;
    var isAdmin = window.userRole === 'admin';
    
    var html = '<div class="fleet-grid">';
    vehicles.forEach(function(vehicle) {
        html += '<div class="fleet-card" data-vehicle-id="' + vehicle.id + '">' +
            '<div class="fleet-image">' +
                (vehicle.primary_image ? 
                    '<img src="' + vehicle.primary_image + '" alt="' + escapeHtml(vehicle.brand_name) + ' ' + escapeHtml(vehicle.model) + '">' : 
                    '<i class="fas fa-car"></i>') +
            '</div>' +
            '<div class="availability-badge-container" id="badge-' + vehicle.id + '"></div>' +
            '<div class="fleet-info">' +
                '<h3>' + escapeHtml(vehicle.brand_name) + ' ' + escapeHtml(vehicle.model) + '</h3>' +
                '<div class="fleet-price">₱' + vehicle.daily_rate + '/day <small>+ tax</small></div>' +
                '<ul class="fleet-features">' +
                    '<li><i class="fas fa-calendar-alt"></i> ' + vehicle.year + '</li>' +
                    '<li><i class="fas fa-cog"></i> ' + vehicle.transmission + '</li>' +
                    '<li><i class="fas fa-gas-pump"></i> ' + vehicle.fuel_type + '</li>' +
                    '<li><i class="fas fa-users"></i> ' + vehicle.seating_capacity + ' seats</li>' +
                '</ul>' +
                '<div class="vehicle-gallery"></div>';
        
        if (isLoggedIn) {
            if (isAdmin) {
                html += '<div class="admin-message"><i class="fas fa-lock"></i> Admin accounts cannot book vehicles</div>';
            } else {
                html += '<button onclick="openVehicleModal(' + vehicle.id + ')" class="btn-primary" style="width: 100%; text-align: center;">' +
                    '<i class="fas fa-eye"></i> View Details</button>';
            }
        } else {
            html += '<a href="{{ url_for('auth_bp.login') }}" class="btn-primary" style="width: 100%; text-align: center; display: inline-block;">' +
                '<i class="fas fa-sign-in-alt"></i> Login to Book</a>';
        }
        
        html += '</div></div>';
    });
    html += '</div>';
    container.innerHTML = html;
    
    // Load images for each card
    document.querySelectorAll('.fleet-card').forEach(function(card) {
        var vehicleId = card.dataset.vehicleId;
        if (vehicleId) {
            fleetLoadVehicleImages(vehicleId, card);
        }
    });
    
    // Load availability after vehicles are rendered
    setTimeout(fleetLoadAvailability, 100);
};

// ============================================
// Load Vehicle Images
// ============================================

function fleetLoadVehicleImages(vehicleId, element) {
    fetch('/admin/api/vehicles/' + vehicleId + '/images')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            var galleryDiv = element.querySelector('.vehicle-gallery');
            if (!galleryDiv) return;
            
            var images = [];
            if (data.primary_image) images.push(data.primary_image);
            if (data.images) {
                data.images.forEach(function(img) {
                    images.push(img.image_path);
                });
            }
            
            if (images.length > 0) {
                var html = images.slice(0, 4).map(function(img) {
                    return '<a href="' + img + '" data-lightbox="vehicle-' + vehicleId + '" data-title="' + element.querySelector('h3').innerText + '">' +
                        '<img src="' + img + '" class="gallery-thumb">' +
                    '</a>';
                }).join('');
                
                if (images.length > 4) {
                    html += '<div class="gallery-thumb" style="background: linear-gradient(135deg, #0f3b6f, #1e4a7a); color:white; display:flex; align-items:center; justify-content:center; font-weight:bold;">+' + (images.length - 4) + '</div>';
                }
                galleryDiv.innerHTML = html;
            }
        })
        .catch(function(error) { console.error('Error loading images:', error); });
}

// ============================================
// Load Availability Badge
// ============================================

function fleetLoadAvailability() {
    console.log('Loading availability...');
    fetch('/user/api/vehicles/availability')
        .then(function(response) {
            console.log('Availability response status:', response.status);
            return response.json();
        })
        .then(function(data) {
            console.log('Availability data:', data);
            if (Object.keys(data).length === 0) {
                console.log('No availability data returned');
                return;
            }
            Object.entries(data).forEach(function(entry) {
                var vehicleId = entry[0];
                var count = entry[1];
                var badgeContainer = document.getElementById('badge-' + vehicleId);
                if (badgeContainer) {
                    var badgeClass = 'badge-red';
                    var icon = 'fa-times-circle';
                    var text = 'Not available';
                    
                    if (count >= 3) {
                        badgeClass = 'badge-green';
                        icon = 'fa-check-circle';
                        text = count + ' available today';
                    } else if (count >= 1) {
                        badgeClass = 'badge-yellow';
                        icon = 'fa-exclamation-circle';
                        text = count + ' available today';
                    }
                    
                    badgeContainer.innerHTML = '<div class="availability-badge ' + badgeClass + '">' +
                        '<i class="fas ' + icon + '"></i> ' + text +
                    '</div>';
                }
            });
        })
        .catch(function(error) { console.error('Error loading availability:', error); });
}

// Override the original displayVehicles
displayVehicles = fleetDisplayVehicles;

// Initialize lightbox
document.addEventListener('DOMContentLoaded', function() {
    if (typeof lightbox !== 'undefined') {
        lightbox.option({
            'resizeDuration': 200,
            'wrapAround': true,
            'albumLabel': 'Image %1 of %2'
        });
    }
});