// ============================================
// Core Variables and Utilities
// ============================================

// Global state variables
var currentFilters = {
    search: '',
    transmission: '',
    fuel_type: '',
    seating_capacity: '',
    min_price: '',
    max_price: '',
    start_date: '',
    end_date: ''
};

var currentVehicleData = null;
var confirmModalCallback = null;

// ============================================
// Confirm Modal Functions
// ============================================

function openConfirmModal(options) {
    var modal = document.getElementById('confirmModal');
    var icon = document.getElementById('confirmModalIcon');
    var title = document.getElementById('confirmModalTitle');
    var message = document.getElementById('confirmModalMessage');
    var actionBtn = document.getElementById('confirmActionBtn');
    
    var defaults = {
        icon: 'danger',
        title: 'Confirm Action',
        message: 'Are you sure you want to proceed?',
        confirmText: 'Confirm',
        confirmClass: 'confirm-btn-danger',
        onConfirm: null
    };
    
    var opts = Object.assign({}, defaults, options);
    
    icon.className = 'confirm-modal-icon ' + opts.icon;
    title.textContent = opts.title;
    message.textContent = opts.message;
    actionBtn.textContent = opts.confirmText;
    actionBtn.className = opts.confirmClass;
    confirmModalCallback = opts.onConfirm;
    
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeConfirmModal() {
    var modal = document.getElementById('confirmModal');
    modal.classList.remove('active');
    document.body.style.overflow = '';
    confirmModalCallback = null;
}

function confirmModalAction() {
    if (confirmModalCallback) {
        confirmModalCallback();
    }
    closeConfirmModal();
}

// Close modal on cancel button or outside click
document.addEventListener('DOMContentLoaded', function() {
    var modal = document.getElementById('confirmModal');
    if (modal) {
        var cancelBtn = document.getElementById('confirmCancelBtn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', closeConfirmModal);
        }
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeConfirmModal();
            }
        });
    }
});

// ============================================
// Utility Functions
// ============================================

function showError(message) {
    alert(message);
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}