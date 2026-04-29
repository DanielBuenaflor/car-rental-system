// ============================================
// Vehicle Modal Functions
// ============================================

window.isLoggedIn = window.isLoggedIn || false;
window.userRole = window.userRole || '';

function openVehicleModal(vehicleId) {
    var modal = document.getElementById('vehicleModal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    fetch('/api/vehicle/' + vehicleId)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                currentVehicleData = data.vehicle;
                displayVehicleModal(data.vehicle, data.images, data.similar_vehicles);
            } else {
                showError('Failed to load vehicle details');
            }
        })
        .catch(function(error) {
            console.error('Error:', error);
            showError('Error loading vehicle details');
        });
}

function displayVehicleModal(vehicle, images, similarVehicles) {
    var container = document.getElementById('modalBody');
    
    var imagesHtml = '';
    var mainImage = vehicle.primary_image || '/static/images/placeholder-car.jpg';
    
    // Check if we have images from the API
    if (images && images.length > 0) {
        var primaryImg = images.find(function(img) { return img.is_primary === 1 || img.is_primary === true; });
        if (primaryImg) {
            mainImage = primaryImg.image_path;
        } else {
            mainImage = images[0].image_path;
        }
        
        imagesHtml = '<div class="thumbnail-list">' +
            images.map(function(img, idx) {
                return '<div class="thumbnail-item ' + (img.image_path === mainImage ? 'active' : '') + '" onclick="changeModalImage(\'' + img.image_path + '\', this)"><img src="' + img.image_path + '" alt="Thumbnail ' + (idx + 1) + '"></div>';
            }).join('') +
            '</div>';
    } else if (vehicle.primary_image) {
        mainImage = vehicle.primary_image;
        imagesHtml = '<div class="thumbnail-list"><div class="thumbnail-item active" onclick="changeModalImage(\'' + mainImage + '\', this)"><img src="' + mainImage + '" alt="Vehicle"></div></div>';
    } else {
        imagesHtml = '<div class="thumbnail-list"><div class="thumbnail-item active" onclick="changeModalImage(\'/static/images/placeholder-car.jpg\', this)"><img src="/static/images/placeholder-car.jpg" alt="Vehicle"></div></div>';
    }
    
    // Build specs HTML with conditional visibility
    var specsHtml = '';
    if (vehicle.year || vehicle.transmission || vehicle.fuel_type || vehicle.seating_capacity || vehicle.vehicle_type || vehicle.color) {
        specsHtml = '<div class="specs-grid">';
        
        if (vehicle.year) {
            specsHtml += '<div class="spec-item"><i class="fas fa-calendar-alt"></i><strong>Year</strong><span>' + vehicle.year + '</span></div>';
        }
        if (vehicle.transmission) {
            specsHtml += '<div class="spec-item"><i class="fas fa-cog"></i><strong>Transmission</strong><span>' + vehicle.transmission + '</span></div>';
        }
        if (vehicle.fuel_type) {
            specsHtml += '<div class="spec-item"><i class="fas fa-gas-pump"></i><strong>Fuel Type</strong><span>' + vehicle.fuel_type + '</span></div>';
        }
        if (vehicle.seating_capacity) {
            specsHtml += '<div class="spec-item"><i class="fas fa-users"></i><strong>Seating</strong><span>' + vehicle.seating_capacity + ' seats</span></div>';
        }
        if (vehicle.vehicle_type) {
            specsHtml += '<div class="spec-item"><i class="fas fa-car"></i><strong>Body Type</strong><span>' + vehicle.vehicle_type + '</span></div>';
        }
        if (vehicle.color) {
            specsHtml += '<div class="spec-item"><i class="fas fa-palette"></i><strong>Color</strong><span>' + vehicle.color + '</span></div>';
        }
        
        specsHtml += '</div>';
    }
    
    // Build vehicle title HTML
    var vehicleTitleHtml = '';
    if (vehicle) {
        vehicleTitleHtml = '<h2 style="margin: 24px 0; color: #0f3b6f; font-size: 28px;">' + 
            escapeHtml(vehicle.brand_name || '') + ' ' + 
            escapeHtml(vehicle.model || '') + '</h2>';
    }
    
    // Build vehicle details HTML
    var vehicleDetailsHtml = '';
    var hourlyRate = Math.floor(vehicle.daily_rate / 5);
    
    if (vehicle) {
        vehicleDetailsHtml = 
            '<div class="vehicle-info-grid">' +
                '<div class="vehicle-specs">' +
                    '<h3><i class="fas fa-list"></i> Vehicle Specifications</h3>' +
                    specsHtml +
                '</div>' +
                '<div class="booking-card">' +
                    '<div class="modal-price">₱' + parseFloat(vehicle.daily_rate || 0).toLocaleString() + '<small>/day + tax</small></div>' +
                    '<div style="margin-bottom: 8px; text-align: center; color: #64748b; font-size: 14px;">' +
                        '<i class="fas fa-clock" style="color: #0f3b6f;"></i> ₱' + hourlyRate.toLocaleString() + '/hour' +
                    '</div>' +
                    '<div style="margin-bottom: 16px; text-align: center; color: #64748b; font-size: 14px;">' +
                        '<i class="fas fa-check-circle" style="color: #10b981;"></i> Free cancellation' +
                    '</div>' +
                    '<div style="margin-bottom: 16px;">' +
                        '<label style="display: block; margin-bottom: 8px; font-weight: 600; color: #1f3a5f; font-size: 14px;">Availability Calendar</label>' +
                        '<div id="modalCalendar" data-vehicle-id="' + vehicle.id + '" style="margin-bottom: 12px;"></div>' +
                    '</div>';
        
        var isLoggedIn = window.isLoggedIn === true || window.isLoggedIn === 'true';
        var isAdmin = window.userRole === 'admin';
        
        if (isLoggedIn && !isAdmin) {
            vehicleDetailsHtml += '<a href="/user/book/' + vehicle.id + '" class="book-now-btn"><i class="fas fa-calendar-check"></i> Book Now</a>';
        } else if (!isLoggedIn) {
            vehicleDetailsHtml += '<a href="/login?next=/user/book/' + vehicle.id + '" class="book-now-btn"><i class="fas fa-sign-in-alt"></i> Login to Book</a>';
        }
        
        vehicleDetailsHtml += '</div></div>';
        
        // Add description only if it exists
        if (vehicle.description && vehicle.description.trim()) {
            vehicleDetailsHtml += 
                '<div class="description-section">' +
                    '<h3><i class="fas fa-info-circle"></i> Description</h3>' +
                    '<p>' + escapeHtml(vehicle.description) + '</p>' +
                '</div>';
        }
    }
    
    var html = 
        '<div class="vehicle-gallery">' +
            '<div class="main-image">' +
                '<img id="modalMainImage" src="' + mainImage + '" alt="' + escapeHtml(vehicle.brand_name) + ' ' + escapeHtml(vehicle.model) + '" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';">' +
                '<i class="fas fa-car no-image" style="display: none;"></i>' +
            '</div>' +
            imagesHtml +
        '</div>' +
        vehicleTitleHtml +
        vehicleDetailsHtml;
    
    // Similar vehicles section
    if (similarVehicles && similarVehicles.length > 0) {
        html += '<div class="similar-vehicles-modal">' +
            '<h3><i class="fas fa-car"></i> Similar Vehicles</h3>' +
            '<div class="similar-grid-modal">' +
            similarVehicles.map(function(sv) {
                return '<div class="similar-card-modal" onclick="openVehicleModal(' + sv.id + '); closeVehicleModal();">' +
                    '<img src="' + (sv.primary_image || '/static/images/placeholder-car.jpg') + '" alt="' + escapeHtml(sv.brand_name) + ' ' + escapeHtml(sv.model) + '">' +
                    '<div class="info">' +
                        '<h4>' + escapeHtml(sv.brand_name) + ' ' + escapeHtml(sv.model) + '</h4>' +
                        '<div class="price">₱' + sv.daily_rate + '/day</div>' +
                    '</div>' +
                '</div>';
            }).join('') +
            '</div></div>';
    }
    
    container.innerHTML = html;
    
    // Load calendar with booked dates
    if (vehicle && vehicle.id) {
        loadVehicleCalendar(vehicle.id);
    }
}

function loadVehicleCalendar(vehicleId) {
    var calendarDiv = document.getElementById('modalCalendar');
    if (!calendarDiv) return;
    
    calendarDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: #64748b;"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
    
    fetch('/api/vehicle/' + vehicleId + '/bookings?months=1')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            renderCalendar(vehicleId, data.booked_dates || [], data.available_dates || []);
        })
        .catch(function(error) {
            console.error('Error loading calendar:', error);
            if (calendarDiv) calendarDiv.innerHTML = '<div style="text-align: center; color: #ef4444;">Failed to load calendar</div>';
        });
}

function renderCalendar(vehicleId, bookedDates, availableDates) {
    var calendarDiv = document.getElementById('modalCalendar');
    if (!calendarDiv) return;
    
    var today = new Date();
    var currentMonth = today.getMonth();
    var currentYear = today.getFullYear();
    
    var html = '';
    
    // Generate calendar for current month and next month
    for (var m = 0; m < 2; m++) {
        var monthDate = new Date(currentYear, currentMonth + m, 1);
        var monthName = monthDate.toLocaleString('default', { month: 'long', year: 'numeric' });
        var daysInMonth = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0).getDate();
        var firstDayOfWeek = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1).getDay();
        
        html += '<div style="margin-bottom: 16px;">';
        html += '<div style="text-align: center; font-weight: 600; color: #0f3b6f; margin-bottom: 8px;">' + monthName + '</div>';
        html += '<div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; text-align: center; font-size: 11px;">';
        
        // Day headers
        var dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
        for (var d = 0; d < 7; d++) {
            html += '<div style="color: #64748b; font-weight: 600; padding: 4px;">' + dayNames[d] + '</div>';
        }
        
        // Empty cells for days before month starts
        for (var e = 0; e < firstDayOfWeek; e++) {
            html += '<div></div>';
        }
        
        // Days of month
        for (var day = 1; day <= daysInMonth; day++) {
            var date = new Date(monthDate.getFullYear(), monthDate.getMonth(), day);
            var dateStr = date.toISOString().split('T')[0];
            
            var isBooked = bookedDates.indexOf(dateStr) !== -1;
            var isPast = date < today;
            
            var cellStyle = 'padding: 6px; border-radius: 6px; font-size: 12px;';
            
            if (isPast) {
                html += '<div style="' + cellStyle + 'color: #e2e8f0;">' + day + '</div>';
            } else if (isBooked) {
                html += '<div style="' + cellStyle + 'background: #fee2e2; color: #991b1b;" title="Booked">' + day + '</div>';
            } else {
                html += '<div style="' + cellStyle + 'background: #d1fae5; color: #065f46;">' + day + '</div>';
            }
        }
        
        html += '</div></div>';
    }
    
    html += '<div style="display: flex; justify-content: center; gap: 20px; margin-top: 8px; font-size: 11px; color: #64748b;">' +
        '<div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background: #d1fae5; border-radius: 3px;"></div> Available</div>' +
        '<div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background: #fee2e2; border-radius: 3px;"></div> Booked</div>' +
        '</div>';
    
    calendarDiv.innerHTML = html;
}

function loadSimilarVehicle(vehicleId) {
    fetch('/api/vehicle/' + vehicleId)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success && data.similar_vehicles && data.similar_vehicles.length > 0) {
                var container = document.getElementById('similarVehiclesContainer');
                if (container) {
                    container.innerHTML = data.similar_vehicles.map(function(sv) {
                        return '<div class="similar-card" onclick="openVehicleModal(' + sv.id + ');">' +
                            '<img src="' + (sv.primary_image || '/static/images/placeholder-car.jpg') + '" alt="' + escapeHtml(sv.brand_name) + ' ' + escapeHtml(sv.model) + '">' +
                            '<div class="info">' +
                                '<h4>' + escapeHtml(sv.brand_name) + ' ' + escapeHtml(sv.model) + '</h4>' +
                                '<div class="price">₱' + sv.daily_rate + '/day</div>' +
                            '</div>' +
                        '</div>';
                    }).join('');
                }
            }
        });
}

function changeModalImage(imagePath, element) {
    var mainImage = document.getElementById('modalMainImage');
    if (mainImage) {
        mainImage.src = imagePath;
    }
    
    // Update active thumbnail
    var thumbnails = document.querySelectorAll('.thumbnail-item');
    thumbnails.forEach(function(thumb) {
        thumb.classList.remove('active');
    });
    if (element) {
        element.classList.add('active');
    }
}

function calculateModalTotal(dailyRate) {
    var startDateInput = document.getElementById('bookingStartDate');
    var endDateInput = document.getElementById('bookingEndDate');
    var totalElement = document.getElementById('modalTotalPrice');
    
    if (!startDateInput || !endDateInput || !totalElement) return;
    
    var startDate = new Date(startDateInput.value);
    var endDate = new Date(endDateInput.value);
    
    if (startDate && endDate && !isNaN(startDate) && !isNaN(endDate)) {
        var days = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));
        if (days > 0) {
            var total = days * dailyRate;
            totalElement.textContent = '₱' + total.toLocaleString();
        } else {
            totalElement.textContent = '₱0';
        }
    }
}

function closeVehicleModal() {
    var modal = document.getElementById('vehicleModal');
    if (modal) {
        modal.style.display = 'none';
    }
    document.body.style.overflow = '';
    currentVehicleData = null;
}

// Close modal on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeVehicleModal();
    }
});

// Close modal when clicking on backdrop
document.addEventListener('DOMContentLoaded', function() {
    var modal = document.getElementById('vehicleModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeVehicleModal();
            }
        });
    }
});