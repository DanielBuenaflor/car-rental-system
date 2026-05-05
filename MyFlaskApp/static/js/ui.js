// ============================================
// UI Functions
// ============================================

function logoutUser() {
    openConfirmModal({
        title: 'Logout',
        message: 'Are you sure you want to log out of your account?',
        confirmText: 'Logout',
        confirmClass: 'confirm-btn-danger',
        onConfirm: function() {
            window.location.href = '/logout';
        }
    });
}

function toggleMobileMenu() {
    var navLinks = document.querySelector('.nav-links');
    if (navLinks) {
        navLinks.classList.toggle('active');
    }
    
    var hamburger = document.querySelector('.hamburger');
    if (hamburger) {
        hamburger.classList.toggle('active');
    }
}

function toggleUserMenu() {
    var userMenu = document.querySelector('.user-menu');
    if (userMenu) {
        userMenu.classList.toggle('active');
    }
}


function adjustFooterForMobile() {
    var footer = document.querySelector('footer');
    var main = document.querySelector('main');
    
    if (window.innerWidth <= 768 && main && footer) {
        var mainHeight = main.offsetHeight;
        var windowHeight = window.innerHeight;
        var footerHeight = footer.offsetHeight;
        
        if (mainHeight + footerHeight < windowHeight) {
            footer.style.position = 'fixed';
            footer.style.bottom = '0';
            footer.style.width = '100%';
        } else {
            footer.style.position = 'relative';
        }
    }
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    var hamburger = document.querySelector('.hamburger');
    if (hamburger) {
        hamburger.addEventListener('click', toggleMobileMenu);
    }
    
    // User menu dropdown toggle
    var userName = document.querySelector('.user-name');
    if (userName) {
        userName.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleUserMenu();
        });
    }
    
    // Footer adjustment
    if (window.addEventListener) {
        window.addEventListener('resize', adjustFooterForMobile);
        adjustFooterForMobile();
    }
});

// Close modal on outside click
window.onclick = function(event) {
    var filterModal = document.getElementById('filterModal');
    if (filterModal && event.target === filterModal) {
        closeFilterModal();
    }
    
    var vehicleModal = document.getElementById('vehicleModal');
    if (vehicleModal && event.target === vehicleModal) {
        closeVehicleModal();
    }
    
    // Close user menu when clicking outside
    var userMenu = document.querySelector('.user-menu');
    if (userMenu && !userMenu.contains(event.target)) {
        userMenu.classList.remove('active');
    }
};