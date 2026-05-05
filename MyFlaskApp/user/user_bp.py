# ============================================================================
# IMPORTS
# ============================================================================
import os
import json
import base64
import re
import math
from urllib.parse import urlparse
from functools import wraps
from datetime import datetime, timedelta

from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify, request, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from MyFlaskApp import get_db_connection
from MyFlaskApp.payment.invoice_service import InvoiceService
from MyFlaskApp.utils.ocr_service import LicenseOCRService
from MyFlaskApp.utils.secure_upload import save_upload, save_base64_upload, ALLOWED_IMAGE_EXTENSIONS
from MyFlaskApp.utils.secure_db import fetch_one, execute_query, DatabaseError
from MyFlaskApp.utils.csrf import generate_csrf_token, validate_csrf_token, clear_csrf_token, require_csrf


# ============================================================================
# NOTIFICATION HELPER
# ============================================================================
def create_notification(user_id, title, message, notif_type, link=None):
    """Create a notification for a user."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, link, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (user_id, title, message, notif_type, link))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def create_booking_notification(booking_id, title, message, notif_type, link=None):
    """Create a notification for the user who owns the booking."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM bookings WHERE id = %s", (booking_id,))
        result = cursor.fetchone()
        if result:
            user_id = result[0]
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, link, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (user_id, title, message, notif_type, link))
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error creating booking notification: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# CONFIGURATION
# ============================================================================
MAX_FILE_SIZE_MB = 5
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    'base', 'uploads', 'verifications'
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def save_base64_image(base64_data, filepath):
    """
    Decode base64 image data and save to file.
    
    Input:
        base64_data (str): Base64 encoded image string (with or without data URI prefix)
        filepath (str): Full path where image should be saved
        
    Output:
        str: Filename of saved image, or None if save failed
    """
    try:
        # Remove data URI prefix if present (e.g., "data:image/jpeg;base64,")
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)
        
        # Write to file
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        return os.path.basename(filepath)
    except Exception as e:
        print(f"Error saving base64 image: {e}")
        return None

def _is_safe_notification_link(link):
    """Allow only internal app-relative notification links."""
    if not link or not link.startswith('/') or link.startswith('//'):
        return False

    parsed = urlparse(link)
    return not parsed.scheme and not parsed.netloc


def _notifications_fallback_url():
    return url_for('user_bp.notifications')


def _notification_target_link(link):
    return link if _is_safe_notification_link(link) else _notifications_fallback_url()


def _load_notifications(cursor, user_id, limit):
    cursor.execute("""
        SELECT id, type, title, message, link, is_read, read_at, created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (user_id, limit))
    return cursor.fetchall()


def _validate_notification_csrf():
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    valid, error = validate_csrf_token(token)
    if not valid:
        return False, error

    clear_csrf_token()
    return True, None


def _validate_state_change_csrf(clear_token=False):
    """Validate CSRF token for form or JSON state-changing requests."""
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    valid, error = validate_csrf_token(token)
    if not valid:
        return False, error

    if clear_token:
        clear_csrf_token()
    return True, None


# ============================================================================
# BLUEPRINT CONFIGURATION
# ============================================================================
user_bp = Blueprint(
    'user_bp', 
    __name__, 
    template_folder='templates',
    static_folder='static', 
    static_url_path="/user_statics"
)


# ============================================================================
# DECORATORS
# ============================================================================
def login_required(f):
    """Decorator to require user login and prevent admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('loggedin'):
            flash('Please login to access this page', 'error')
            return redirect(url_for('auth_bp.login'))
        if session.get('role') == 'admin':
            flash('Admin accounts cannot access user features', 'error')
            return redirect(url_for('admin_bp.admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# PAGE ROUTES - DASHBOARD & PROFILE
# ============================================================================
@user_bp.route('/dashboard')
@login_required
def user_dashboard():
    """User dashboard page with statistics and recent activity"""
    default_context = {
        'session': session,
        'is_verified': False,
        'booking_count': 0,
        'active_count': 0,
        'pending_count': 0,
        'confirmed_count': 0,
        'completed_count': 0,
        'cancelled_count': 0,
        'total_spent': 0,
        'upcoming_bookings': [],
        'active_rentals': [],
        'testimonial_count': 0,
        'verification_status': 'not_submitted',
        'rejection_reason': None,
        'recent_bookings': [],
        'recent_notifications': [],
        'csrf_token_value': generate_csrf_token()
    }
    conn = get_db_connection()
    if not conn:
        return render_template('user_dashboard.html', **default_context)
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get user stats (total, status breakdown)
        cursor.execute("""
            SELECT 
                COUNT(*) as booking_count,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_count,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count
            FROM bookings 
            WHERE user_id = %s
        """, (session['user_id'],))
        status_stats = cursor.fetchone() or {}
        booking_count = status_stats.get('booking_count', 0) or 0
        active_count = status_stats.get('active_count', 0) or 0
        pending_count = status_stats.get('pending_count', 0) or 0
        confirmed_count = status_stats.get('confirmed_count', 0) or 0
        completed_count = status_stats.get('completed_count', 0) or 0
        cancelled_count = status_stats.get('cancelled_count', 0) or 0
        
        # Get total spent (completed and active bookings)
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total_spent
            FROM bookings 
            WHERE user_id = %s AND status IN ('completed', 'active')
        """, (session['user_id'],))
        total_spent_row = cursor.fetchone() or {}
        total_spent = total_spent_row.get('total_spent', 0) or 0
        
        # Get upcoming bookings (next 7 days)
        cursor.execute("""
            SELECT b.*, v.model, v.license_plate, vb.name as brand_name
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.user_id = %s AND b.status = 'pending' 
            AND b.start_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
            ORDER BY b.start_date ASC
        """, (session['user_id'],))
        upcoming_bookings = cursor.fetchall()
        
        # Get verification status
        cursor.execute("""
            SELECT verification_status, rejection_reason 
            FROM verifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT 1
        """, (session['user_id'],))
        verification = cursor.fetchone() or {}
        verification_status = verification.get('verification_status', 'not_submitted')
        rejection_reason = verification.get('rejection_reason')
        is_verified = verification_status == 'approved'
        
        # Get testimonial count
        cursor.execute("""
            SELECT COUNT(*) as count FROM testimonials
            WHERE user_id = %s
        """, (session['user_id'],))
        testimonial_row = cursor.fetchone() or {}
        testimonial_count = testimonial_row.get('count', 0) or 0
        
        # Get recent bookings (with custom addresses)
        cursor.execute("""
            SELECT b.*, v.model, v.brand_id, vb.name as brand_name,
                   b.custom_pickup_address, b.custom_return_address
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC
            LIMIT 3
        """, (session['user_id'],))
        recent_bookings = cursor.fetchall()

        recent_notifications = _load_notifications(cursor, session['user_id'], 5)
        
        # Get active rentals with countdown
        cursor.execute("""
            SELECT b.*, v.model, v.license_plate, vb.name as brand_name,
                   rt.pickup_time, rt.expected_return_time, rt.tracking_status,
                   rt.pickup_odometer_reading, rt.fuel_level_at_pickup,
                   b.custom_pickup_address, b.custom_return_address
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            LEFT JOIN rental_tracking rt ON b.id = rt.booking_id
            WHERE b.user_id = %s AND b.status IN ('confirmed', 'active')
            ORDER BY b.start_date ASC
        """, (session['user_id'],))
        active_rentals = cursor.fetchall()
        
        # Calculate countdown for each active rental
        now = datetime.now()
        for rental in active_rentals:
            if rental['start_date']:
                start = rental['start_date']
                if now < start:
                    days_left = (start - now).days
                    hours_left = (start - now).seconds // 3600
                    rental['status_message'] = f"Starts in {days_left} days, {hours_left} hours"
                    rental['countdown_type'] = 'upcoming'
                elif rental['end_date']:
                    end = rental['end_date']
                    if now < end:
                        days_left = (end - now).days
                        hours_left = (end - now).seconds // 3600
                        rental['status_message'] = f"Ends in {days_left} days, {hours_left} hours"
                        rental['countdown_type'] = 'active'
                    else:
                        rental['status_message'] = "OVERDUE - Please return vehicle"
                        rental['countdown_type'] = 'overdue'
        
        # Generate CSRF token for dashboard
        token = generate_csrf_token()
        
        return render_template(
            'user_dashboard.html',
            session=session,
            is_verified=is_verified,
            booking_count=booking_count,
            active_count=active_count,
            pending_count=pending_count,
            confirmed_count=confirmed_count,
            completed_count=completed_count,
            cancelled_count=cancelled_count,
            total_spent=total_spent,
            upcoming_bookings=upcoming_bookings,
            active_rentals=active_rentals,
            testimonial_count=testimonial_count,
            verification_status=verification_status,
            rejection_reason=rejection_reason,
            recent_bookings=recent_bookings,
            recent_notifications=recent_notifications,
            csrf_token_value=token
        )
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('user_dashboard.html', **default_context)
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/notifications')
@login_required
def notifications():
    """Display the user's notification inbox."""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template(
            'notifications.html',
            notifications=[],
            session=session,
            csrf_token_value=generate_csrf_token()
        )

    cursor = conn.cursor(dictionary=True)
    try:
        notifications_list = _load_notifications(cursor, session['user_id'], 50)
        return render_template(
            'notifications.html',
            notifications=notifications_list,
            session=session,
            csrf_token_value=generate_csrf_token()
        )
    except Exception as e:
        print(f"Notifications error: {e}")
        flash('Error loading notifications', 'error')
        return render_template(
            'notifications.html',
            notifications=[],
            session=session,
            csrf_token_value=generate_csrf_token()
        )
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/notifications/<int:notification_id>/open')
@login_required
def open_notification(notification_id):
    """Open a notification target and mark it as read."""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(_notifications_fallback_url())

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, link, is_read
            FROM notifications
            WHERE id = %s AND user_id = %s
        """, (notification_id, session['user_id']))
        notification = cursor.fetchone()

        if not notification:
            flash('Notification not found', 'error')
            return redirect(_notifications_fallback_url())

        if not notification['is_read']:
            cursor.execute("""
                UPDATE notifications
                SET is_read = TRUE, read_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (notification_id, session['user_id']))
            conn.commit()

        return redirect(_notification_target_link(notification.get('link')))
    except Exception as e:
        print(f"Open notification error: {e}")
        flash('Error opening notification', 'error')
        return redirect(_notifications_fallback_url())
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a single notification as read."""
    valid, error = _validate_notification_csrf()
    if not valid:
        flash(error, 'error')
        return redirect(_notifications_fallback_url())

    next_url = request.form.get('next', '')

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(_notifications_fallback_url())

    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE notifications
            SET is_read = TRUE, read_at = NOW()
            WHERE id = %s AND user_id = %s AND is_read = FALSE
        """, (notification_id, session['user_id']))
        conn.commit()
        return redirect(next_url if _is_safe_notification_link(next_url) else _notifications_fallback_url())
    except Exception as e:
        conn.rollback()
        print(f"Mark notification read error: {e}")
        flash('Error updating notification', 'error')
        return redirect(_notifications_fallback_url())
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications for the current user as read."""
    valid, error = _validate_notification_csrf()
    if not valid:
        flash(error, 'error')
        return redirect(_notifications_fallback_url())

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(_notifications_fallback_url())

    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE notifications
            SET is_read = TRUE, read_at = NOW()
            WHERE user_id = %s AND is_read = FALSE
        """, (session['user_id'],))
        conn.commit()
        return redirect(_notifications_fallback_url())
    except Exception as e:
        conn.rollback()
        print(f"Mark all notifications read error: {e}")
        flash('Error updating notifications', 'error')
        return redirect(_notifications_fallback_url())
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and update user profile"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('user_bp.user_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Update profile
        try:
            valid, error = _validate_state_change_csrf(clear_token=True)
            if not valid:
                flash(error, 'error')
                return redirect(url_for('user_bp.profile'))

            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            
            # Extract address dropdown names (we'll ensure JS sends names or we'll get them from the text)
            # For now, let's assume JS is updated to send these names
            region = request.form.get('region_name', '').strip()
            province = request.form.get('province_name', '').strip()
            city = request.form.get('city_name', '').strip()
            barangay = request.form.get('barangay_name', '').strip()
            
            state = region # Map Region to State for legacy compatibility
            
            postal_code = request.form.get('postal_code', '').strip()
            country = request.form.get('country', '').strip()

            if not first_name or not last_name:
                flash('First name and last name are required', 'error')
                return redirect(url_for('user_bp.profile'))

            if len(first_name) > 100 or len(last_name) > 100:
                flash('Name fields are too long', 'error')
                return redirect(url_for('user_bp.profile'))

            if phone and not re.match(r'^[0-9+\-\s()]{7,20}$', phone):
                flash('Please enter a valid phone number', 'error')
                return redirect(url_for('user_bp.profile'))

            if postal_code and len(postal_code) > 20:
                flash('Postal code is too long', 'error')
                return redirect(url_for('user_bp.profile'))
            
            cursor.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s, phone = %s, 
                    address = %s, city = %s, province = %s, barangay = %s, state = %s, 
                    postal_code = %s, country = %s
                WHERE id = %s
            """, (first_name, last_name, phone, address, city, province, barangay, state, postal_code, country, 
                  session['user_id']))
            conn.commit()
            
            # Update session username
            session['username'] = first_name
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('user_bp.profile'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    # GET request - show profile
    try:
        cursor.execute("""
            SELECT id, first_name, last_name, email, phone, address, city, 
                   state, postal_code, country, created_at
            FROM users 
            WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
        
        return render_template('profile.html', user=user, session=session)
    except Exception as e:
        flash('Error loading profile', 'error')
        return redirect(url_for('user_bp.user_dashboard'))
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password (AJAX endpoint)"""
    valid, error = _validate_state_change_csrf()
    if not valid:
        return jsonify({'success': False, 'message': error}), 403

    data = request.get_json() or {}
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters'})

    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$'
    if not re.match(password_pattern, new_password):
        return jsonify({
            'success': False,
            'message': 'Password must contain at least one uppercase letter, one lowercase letter, and one number'
        })
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'})
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get current password
        cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if not check_password_hash(user['password'], current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'})
        
        # Update password
        hashed_password = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", 
                      (hashed_password, session['user_id']))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
        
    except Exception:
        return jsonify({'success': False, 'message': 'Unable to change password right now'})
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# PAGE ROUTES - BOOKINGS & RENTALS
# ============================================================================
@user_bp.route('/book/<int:vehicle_id>')
@login_required
def book_vehicle_page(vehicle_id):
    """Display booking page for a vehicle"""
    from datetime import date
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('base_bp.browse_fleet'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get vehicle details
        cursor.execute("""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.id = %s AND v.status = 'available'
        """, (vehicle_id,))
        vehicle = cursor.fetchone()
        
        if not vehicle:
            flash('Vehicle not found or not available', 'error')
            return redirect(url_for('auth_bp.browse_fleet'))
        
        # Get user verification status
        cursor.execute("""
            SELECT verification_status, rejection_reason 
            FROM verifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT 1
        """, (session['user_id'],))
        verification = cursor.fetchone()
        
        verification_status = verification['verification_status'] if verification else 'not_submitted'
        rejection_reason = verification['rejection_reason'] if verification else None
        
        return render_template(
            'book_vehicle.html',
            vehicle=vehicle,
            verification_status=verification_status,
            rejection_reason=rejection_reason,
            today_date=date.today().strftime('%Y-%m-%d'),
            session=session,
            csrf_token_value=generate_csrf_token()
        )
        
    except Exception as e:
        print(f"Error loading booking page: {e}")
        flash('Error loading booking page', 'error')
        return redirect(url_for('auth_bp.browse_fleet'))
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/bookings')
@login_required
def my_bookings():
    """View user's booking history"""
    conn = get_db_connection()
    if not conn:
        return render_template('my_bookings.html', bookings=[], session=session)

    cursor = conn.cursor(dictionary=True)
    try:
        # Ensure user_id is integer
        user_id = int(session['user_id']) if 'user_id' in session else None
        if not user_id:
            return render_template('my_bookings.html', bookings=[], session=session)

        cursor.execute("""
            SELECT b.*, v.model, v.year, v.license_plate, v.daily_rate,
                   vb.name as brand_name, vb.id as brand_id
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC
        """, (user_id,))
        bookings = cursor.fetchall()

        # Get all bookings user has already reviewed
        try:
            cursor.execute("""
                SELECT DISTINCT booking_id FROM testimonials
                WHERE user_id = %s
            """, (user_id,))
            reviewed_bookings = {row['booking_id'] for row in cursor.fetchall()}
        except Exception as te:
            print(f"Testimonials query error: {te}")
            reviewed_bookings = set()

        # Add 'reviewed' flag to each booking
        for booking in bookings:
            booking['reviewed'] = booking['id'] in reviewed_bookings

        # Convert timedelta objects to strings for JSON serialization
        from datetime import timedelta
        for booking in bookings:
            for key, value in list(booking.items()):
                if isinstance(value, timedelta):
                    total_seconds = int(value.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    booking[key] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                # NOTE: Don't convert datetime objects - template uses .strftime()

        return render_template('my_bookings.html', bookings=bookings)
    except Exception as e:
        print(f"My bookings error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('my_bookings.html', bookings=[], session=session)
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/active-rentals')
@login_required
def active_rentals():
    """View active rentals with countdown and penalty estimation"""
    conn = get_db_connection()
    if not conn:
        return render_template('rental_tracking.html', active_rentals=[], session=session)

    cursor = conn.cursor(dictionary=True)
    try:
        # Get active rentals for the user (include rates for penalty calculation)
        cursor.execute("""
            SELECT b.*, v.model, v.license_plate, v.current_odometer, vb.name as brand_name,
                   rt.pickup_time, rt.expected_return_time, rt.tracking_status,
                   rt.pickup_odometer_reading, rt.fuel_level_at_pickup,
                   COALESCE(b.daily_rate_applied, v.daily_rate) as effective_daily_rate
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            LEFT JOIN rental_tracking rt ON b.id = rt.booking_id
            WHERE b.user_id = %s AND b.status IN ('confirmed', 'active')
            ORDER BY b.start_date ASC
        """, (session['user_id'],))
        active_rentals = cursor.fetchall()

        # Get late fee multiplier from settings
        cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'late_fee_daily_rate'")
        rate_setting = cursor.fetchone()
        late_fee_multiplier = float(rate_setting['setting_value']) if rate_setting else 1.5

        # Auto-update status: confirmed → active if start_date has passed
        now = datetime.now()
        for rental in active_rentals:
            if rental['status'] == 'confirmed' and rental['start_date'] and now >= rental['start_date']:
                cursor.execute("UPDATE bookings SET status = 'active' WHERE id = %s", (rental['id'],))
                rental['status'] = 'active'
                conn.commit()

        for rental in active_rentals:
            pickup_odometer = rental.get('pickup_odometer_reading')
            current_odometer = rental.get('current_odometer')
            baseline = pickup_odometer if pickup_odometer is not None else current_odometer
            rental['minimum_return_odometer'] = int(baseline) if baseline is not None else 0
            rental['current_vehicle_odometer'] = int(current_odometer) if current_odometer is not None else 0
            # Initialize penalty fields (set default values for non-overdue rentals)
            rental['estimated_penalty'] = 0
            rental['late_detail'] = ""

        # Calculate countdown and penalty estimation for each rental
        for rental in active_rentals:
            if rental['start_date']:
                start = rental['start_date']

                if now < start:
                    # Rental hasn't started yet
                    days_left = (start - now).days
                    hours_left = (start - now).seconds // 3600
                    rental['status_message'] = f"Starts in {days_left} days, {hours_left} hours"
                    rental['countdown_type'] = 'upcoming'
                elif rental['status'] == 'active' and rental['end_date']:
                    # Only mark as overdue if status is 'active' and past end date
                    end = rental['end_date']
                    if now < end:
                        days_left = (end - now).days
                        hours_left = (end - now).seconds // 3600
                        rental['status_message'] = f"Ends in {days_left} days, {hours_left} hours"
                        rental['countdown_type'] = 'active'
                    else:
                        # Calculate estimated penalty for overdue rentals
                        lateness_delta = now - end
                        total_minutes_late = lateness_delta.total_seconds() / 60
                        grace_period_minutes = 30

                        if total_minutes_late > grace_period_minutes:
                            effective_minutes_late = total_minutes_late - grace_period_minutes
                            hours_late_rounded = math.ceil(effective_minutes_late / 60)
                            daily_rate = float(rental.get('effective_daily_rate', 0))

                            if hours_late_rounded <= 24:
                                hourly_rate = (daily_rate * late_fee_multiplier) / 24
                                estimated_penalty = hourly_rate * hours_late_rounded
                                rental['estimated_penalty'] = round(estimated_penalty, 2)
                                rental['late_detail'] = f"{hours_late_rounded}h late (after 30-min grace)"
                            else:
                                days_late_rounded = math.ceil(hours_late_rounded / 24)
                                estimated_penalty = daily_rate * late_fee_multiplier * days_late_rounded
                                rental['estimated_penalty'] = round(estimated_penalty, 2)
                                rental['late_detail'] = f"{days_late_rounded}d late (after 30-min grace)"
                        else:
                            rental['estimated_penalty'] = 0
                            rental['late_detail'] = "Within grace period"

                        rental['status_message'] = "OVERDUE - Please return vehicle"
                        rental['countdown_type'] = 'overdue'
                elif rental['status'] == 'confirmed':
                    # Confirmed but not yet active - show awaiting activation with start date
                    if rental['start_date']:
                        start_str = rental['start_date'].strftime('%B %d, %Y, %H:%M')
                        rental['status_message'] = f"Booking confirmed, starts on {start_str}"
                    else:
                        rental['status_message'] = "Booking confirmed, awaiting activation"
                    rental['countdown_type'] = 'upcoming'

        return render_template('rental_tracking.html',
                               active_rentals=active_rentals,
                               late_fee_multiplier=late_fee_multiplier,
                               session=session)

    except Exception as e:
        print(f"Error loading active rentals: {e}")
        return render_template('rental_tracking.html', active_rentals=[], session=session)
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/invoices')
@login_required
def invoices():
    """View all user invoices"""
    conn = get_db_connection()
    if not conn:
        return render_template('invoices.html', invoices=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT i.*, 
                   b.booking_reference, 
                   b.start_date, 
                   b.end_date,
                   b.rental_days,
                   b.subtotal,
                   b.tax_amount,
                   b.total_amount as booking_total,
                   v.model, 
                   v.year,
                   v.license_plate,
                   vb.name as brand_name
            FROM invoices i
            JOIN bookings b ON i.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.user_id = %s
            ORDER BY i.created_at DESC
        """, (session['user_id'],))
        invoices = cursor.fetchall()
        
        return render_template('invoices.html', invoices=invoices, session=session)
    except Exception as e:
        print(f"Error loading invoices: {str(e)}")
        flash('Error loading invoices', 'error')
        return render_template('invoices.html', invoices=[], session=session)
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/download-invoice/<int:invoice_id>')
@login_required
def download_invoice(invoice_id):
    """View invoice as HTML"""
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('user_bp.invoices'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT i.*, 
                   b.booking_reference,
                   b.start_date, 
                   b.end_date, 
                   b.pickup_location, 
                   b.return_location,
                   b.rental_days,
                   b.daily_rate_applied,
                   b.subtotal, 
                   b.tax_amount, 
                   b.total_amount,
                   b.security_deposit,
                   b.status as booking_status,
                   v.model, 
                   v.year, 
                   v.license_plate, 
                   vb.name as brand_name,
                   u.first_name, 
                   u.last_name, 
                   u.email, 
                   u.phone, 
                   u.address,
                   COALESCE(u.city, '') as city,
                   COALESCE(u.state, '') as state,
                   COALESCE(u.postal_code, '') as postal_code,
                   COALESCE(u.country, 'Philippines') as country
            FROM invoices i
            JOIN bookings b ON i.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            JOIN users u ON b.user_id = u.id
            WHERE i.id = %s AND b.user_id = %s
        """, (invoice_id, session['user_id']))
        invoice = cursor.fetchone()
        
        if not invoice:
            flash('Invoice not found', 'error')
            return redirect(url_for('user_bp.invoices'))
        
        # Calculate balance due
        invoice['balance_due'] = invoice.get('total_amount', 0) - invoice.get('amount', 0)
        
        return render_template('invoice_view.html', invoice=invoice, session=session)
        
    except Exception as e:
        print(f"Error loading invoice: {str(e)}")
        flash(f'Error loading invoice: {str(e)}', 'error')
        return redirect(url_for('user_bp.invoices'))
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/invoice/<int:invoice_id>/pdf')
@login_required
def invoice_pdf(invoice_id):
    """Download invoice as PDF"""
    from MyFlaskApp.payment.invoice_generator import InvoiceGenerator
    from io import BytesIO
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('user_bp.invoices'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT i.*, 
                   b.booking_reference,
                   b.start_date, 
                   b.end_date, 
                   b.pickup_location, 
                   b.return_location,
                   b.rental_days,
                   b.daily_rate_applied,
                   b.subtotal, 
                   b.tax_amount, 
                   b.total_amount,
                   b.security_deposit,
                   b.status as booking_status,
                   v.model, 
                   v.year, 
                   v.license_plate, 
                   vb.name as brand_name,
                   u.first_name, 
                   u.last_name, 
                   u.email, 
                   u.phone, 
                   u.address,
                   COALESCE(u.city, '') as city,
                   COALESCE(u.state, '') as state,
                   COALESCE(u.postal_code, '') as postal_code,
                   COALESCE(u.country, 'Philippines') as country
            FROM invoices i
            JOIN bookings b ON i.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            JOIN users u ON b.user_id = u.id
            WHERE i.id = %s AND b.user_id = %s
        """, (invoice_id, session['user_id']))
        invoice = cursor.fetchone()
        
        if not invoice:
            flash('Invoice not found', 'error')
            return redirect(url_for('user_bp.invoices'))
        
        # Prepare data for PDF generator
        booking = {
            'booking_reference': invoice.get('booking_reference'),
            'start_date': invoice.get('start_date'),
            'end_date': invoice.get('end_date'),
            'pickup_location': invoice.get('pickup_location'),
            'return_location': invoice.get('return_location'),
            'rental_days': invoice.get('rental_days', 0),
            'daily_rate': invoice.get('daily_rate_applied', 0),
            'subtotal': invoice.get('subtotal', 0),
            'tax_amount': invoice.get('tax_amount', 0),
            'total_amount': invoice.get('total_amount', 0),
            'security_deposit': invoice.get('security_deposit', 0)
        }
        
        user = {
            'first_name': invoice.get('first_name'),
            'last_name': invoice.get('last_name'),
            'email': invoice.get('email'),
            'phone': invoice.get('phone'),
            'address': invoice.get('address'),
            'city': invoice.get('city'),
            'state': invoice.get('state'),
            'postal_code': invoice.get('postal_code'),
            'country': invoice.get('country')
        }
        
        vehicle = {
            'model': invoice.get('model'),
            'year': invoice.get('year'),
            'brand_name': invoice.get('brand_name'),
            'license_plate': invoice.get('license_plate')
        }
        
        payment = {
            'amount': invoice.get('amount', 0),
            'payment_status': invoice.get('status')
        }
        
        # Generate PDF
        pdf_buffer = InvoiceGenerator.generate_invoice(booking, user, vehicle, payment)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Invoice_{invoice.get('invoice_number', 'invoice')}.pdf"
        )
        
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('user_bp.invoices'))
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# PAGE ROUTES - VERIFICATION
# ============================================================================
@user_bp.route('/verification')
@login_required
def verification_page():
    # Debug: Write to file to ensure output isn't suppressed
    with open('D:\\verification_debug.log', 'a') as f:
        f.write(f"[{datetime.now()}] ENTERING verification_page()\n")
    print("DEBUG: ===== ENTERING verification_page() =====")
    """Show verification page"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('user_bp.user_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if user already has verification record
        cursor.execute("""
            SELECT * FROM verifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT 1
        """, (session['user_id'],))
        verification = cursor.fetchone()
        
        # Generate CSRF token and store in session
        token = generate_csrf_token()
        print(f"DEBUG: Token generated: {token}")  # Should appear in terminal now!
        print(f"DEBUG: Session token: {session.get('csrf_token')}")
        
        # Pass session to template (template will read csrf_token from session)
        return render_template('verification.html', 
                               verification=verification, 
                               session=session)
    except Exception as e:
        flash(f'Error loading verification: {str(e)}', 'error')
        return redirect(url_for('user_bp.user_dashboard'))
    finally:
        cursor.close()
        conn.close()
# ============================================================================
# API ROUTES - BOOKING OPERATIONS
# ============================================================================
@user_bp.route('/book-vehicle', methods=['POST'])
@login_required
def book_vehicle():
    """Book a vehicle (only for verified users)"""
    conn = None
    cursor = None

    valid, error = _validate_state_change_csrf()
    if not valid:
        return jsonify({'success': False, 'message': error}), 403

    data = request.get_json() or {}
    vehicle_id = data.get('vehicle_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    pickup_time = data.get('pickup_time')
    return_time = data.get('return_time')
    pickup_location = data.get('pickup_location')
    return_location = data.get('return_location')

    if not all([vehicle_id, start_date, end_date, pickup_location, return_location]):
        return jsonify({'success': False, 'message': 'All fields are required'})

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'User session expired'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT verification_status FROM verifications 
            WHERE user_id = %s AND verification_status = 'approved'
        """, (session['user_id'],))
        verified = cursor.fetchone()
        
        if not verified:
            return jsonify({
                'success': False, 
                'message': 'Please complete identity verification before booking a vehicle.',
                'redirect': url_for('user_bp.verification_page')
            }), 403
        
        cursor.execute("""
            SELECT * FROM vehicles 
            WHERE id = %s AND status = 'available'
        """, (vehicle_id,))
        vehicle = cursor.fetchone()
        
        if not vehicle:
            return jsonify({'success': False, 'message': 'Vehicle is not available'})
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days

        if start.date() < datetime.now().date():
            return jsonify({'success': False, 'message': 'Start date cannot be in the past'})

        is_same_day = start_date == end_date
        is_hourly = is_same_day and pickup_time and return_time

        if not is_hourly and days <= 0:
            return jsonify({'success': False, 'message': 'End date must be after start date'})

        if is_hourly:
            pickup_h = int(pickup_time.split(':')[0])
            return_h = int(return_time.split(':')[0])
            hours = return_h - pickup_h
            if hours < 0: hours += 24
            
            hourly_rate = float(vehicle['daily_rate']) / 5
            subtotal = hours * hourly_rate
            subtotal = min(subtotal, float(vehicle['daily_rate']))
            rental_days = 1
        else:
            if days > 30:
                return jsonify({'success': False, 'message': 'Maximum rental period is 30 days'})
            
            daily_rate = float(vehicle['daily_rate'])
            subtotal = daily_rate * days
            rental_days = days
            hours = 0
        
        tax_amount = subtotal * 0.10
        total_amount = subtotal + tax_amount
        
        cursor.execute("""
            SELECT id FROM bookings 
            WHERE vehicle_id = %s 
            AND status IN ('confirmed', 'active')
            AND (
                (start_date BETWEEN %s AND %s)
                OR (end_date BETWEEN %s AND %s)
                OR (%s BETWEEN start_date AND end_date)
                OR (%s BETWEEN start_date AND end_date)
            )
        """, (vehicle_id, start_date, end_date, start_date, end_date, start_date, end_date))
        
        overlapping = cursor.fetchone()
        if overlapping:
            return jsonify({'success': False, 'message': 'Vehicle is already booked for these dates'})
        
        import secrets
        booking_reference = f"BK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{session['user_id']}-{vehicle_id}-{secrets.token_hex(4)}"
        
        cursor.execute("""
            INSERT INTO bookings (
                user_id, vehicle_id, start_date, end_date, pickup_time, return_time,
                pickup_location, return_location, rental_days, hourly_rate_applied,
                daily_rate_applied, subtotal, tax_amount, total_amount,
                security_deposit, status, booking_reference, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, NOW()
            )
        """, (
            session['user_id'], vehicle_id, start_date, end_date, 
            pickup_time, return_time, pickup_location, return_location,
            rental_days, hourly_rate if is_hourly else 0,
            vehicle['daily_rate'], subtotal, tax_amount, total_amount,
            vehicle['security_deposit'], booking_reference
        ))
        
        booking_id = cursor.lastrowid
        conn.commit()
        
        # Get vehicle and user details for notifications
        cursor.execute("""
            SELECT vb.name as brand_name, v.model
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.id = %s
        """, (vehicle_id,))
        vehicle = cursor.fetchone()
        
        # Notify USER about pending booking
        if vehicle:
            create_notification(
                user_id,
                'Booking Submitted',
                f'Your booking for {vehicle["brand_name"]} {vehicle["model"]} is pending payment. Reference: {booking_reference}',
                'booking_confirmation',
                url_for('user_bp.my_bookings')
            )

        # Notify ADMIN about new pending booking
        try:
            cursor.execute("SELECT id FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchall()
            
            if admin_users:
                # Get user name from database (more reliable than session)
                cursor.execute("SELECT CONCAT(first_name, ' ', last_name) as full_name FROM users WHERE id = %s", (user_id,))
                user_result = cursor.fetchone()
                user_display = user_result[0] if user_result else 'A user'
                
                notification_title = "New Booking Pending"
                notification_message = f"New booking {booking_reference} submitted by {user_display}"
                notification_link = "/admin/manage-bookings"
                
                for admin in admin_users:
                    cursor.execute("""
                        INSERT INTO notifications (user_id, title, message, type, link, created_at)
                        VALUES (%s, %s, %s, 'system', %s, NOW())
                    """, (admin[0], notification_title, notification_message, notification_link))
                
                conn.commit()
                print(f"DEBUG: Notified {len(admin_users)} admin(s) about new booking")
        except Exception as notify_err:
            print(f"DEBUG: Error notifying admins about new booking: {notify_err}")
        
        return jsonify({
            'success': True, 
            'message': 'Booking created! Proceed to payment.',
            'redirect': url_for('payment_bp.checkout', booking_id=booking_id),
            'booking_id': booking_id,
            'total_amount': total_amount
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Book vehicle error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@user_bp.route('/cancel-booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    """Cancel a booking"""
    valid, error = _validate_state_change_csrf(clear_token=True)
    if not valid:
        flash(error, 'error')
        return redirect(url_for('user_bp.my_bookings'))

    conn = get_db_connection()
    if not conn:
        flash('Database error. Please try again.', 'error')
        return redirect(url_for('user_bp.my_bookings'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE bookings 
            SET status = 'cancelled', cancelled_by = 'user', cancelled_at = NOW()
            WHERE id = %s AND user_id = %s AND status IN ('pending', 'confirmed')
        """, (booking_id, session['user_id']))
        
        if cursor.rowcount == 0:
            flash('Booking not found or cannot be cancelled.', 'error')
            return redirect(url_for('user_bp.my_bookings'))
        
        # Get booking details for notification
        cursor.execute("SELECT booking_reference FROM bookings WHERE id = %s", (booking_id,))
        booking = cursor.fetchone()
        
        conn.commit()
        flash('Booking cancelled successfully.', 'success')
        
        # Notify USER about cancellation
        if booking:
            create_notification(
                session['user_id'],
                'Booking Cancelled',
                f'Your booking (Ref: {booking[0]}) has been cancelled successfully.',
                'system',
                url_for('user_bp.my_bookings')
            )
        
        # Notify ADMIN about cancelled booking
        try:
            cursor.execute("SELECT id FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchall()
            
            if admin_users and booking:
                # Get user name from database
                cursor.execute("SELECT CONCAT(first_name, ' ', last_name) as full_name FROM users WHERE id = %s", (session['user_id'],))
                user_result = cursor.fetchone()
                user_display = user_result[0] if user_result else 'A user'
                
                notification_title = "Booking Cancelled"
                notification_message = f"Booking {booking[0]} has been cancelled by {user_display}"
                notification_link = "/admin/manage-bookings"
                
                for admin in admin_users:
                    cursor.execute("""
                        INSERT INTO notifications (user_id, title, message, type, link, created_at)
                        VALUES (%s, %s, %s, 'system', %s, NOW())
                    """, (admin[0], notification_title, notification_message, notification_link))
                
                conn.commit()
                print(f"DEBUG: Notified {len(admin_users)} admin(s) about booking cancellation")
        except Exception as notify_err:
            print(f"DEBUG: Error notifying admins about cancellation: {notify_err}")
        
        return redirect(url_for('user_bp.my_bookings'))
        
    except Exception as e:
        conn.rollback()
        flash(f'Error cancelling booking: {str(e)}', 'error')
        return redirect(url_for('user_bp.my_bookings'))
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/request-extension/<int:booking_id>', methods=['POST'])
@login_required
def request_extension(booking_id):
    """Request rental extension"""
    valid, error = _validate_state_change_csrf()
    if not valid:
        return jsonify({'success': False, 'message': error}), 403

    data = request.get_json() or {}
    requested_days = data.get('requested_days')
    reason = data.get('reason', '')
    
    if not requested_days or requested_days <= 0:
        return jsonify({'success': False, 'message': 'Invalid extension days'})
    
    if requested_days > 7:
        return jsonify({'success': False, 'message': 'Maximum extension is 7 days'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'})
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Verify booking belongs to user and is active
        cursor.execute("""
            SELECT b.*, v.daily_rate, v.brand_id, vb.name as brand_name
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'active'
        """, (booking_id, session['user_id']))
        booking = cursor.fetchone()
        
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found or not active'})
        
        # Calculate new end date
        new_end_date = booking['end_date'] + timedelta(days=requested_days)
        
        # Calculate additional fee
        additional_fee = booking['daily_rate'] * requested_days
        
        # Create extension request
        cursor.execute("""
            INSERT INTO extension_requests (
                booking_id, user_id, requested_extension_days, requested_new_end_date,
                reason, status, additional_fee, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'pending', %s, NOW())
        """, (booking_id, session['user_id'], requested_days, new_end_date, reason, additional_fee))
        
        conn.commit()
        
        # Notify admin
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, link, created_at)
            VALUES (1, 'system', 'Extension Request', 
                    CONCAT('User ', %s, ' requested extension for booking ', %s),
                    '/admin/manage-extensions', NOW())
        """, (session['username'], booking['booking_reference']))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Extension request submitted for {requested_days} days. Additional fee: ${additional_fee:.2f}',
            'additional_fee': additional_fee
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


import math

@user_bp.route('/return-vehicle/<int:booking_id>', methods=['POST'])
@login_required
def return_vehicle(booking_id):
    """Mark vehicle as returned with automatic fine calculation for late returns"""
    valid, error = _validate_state_change_csrf()
    if not valid:
        return jsonify({'success': False, 'message': error}), 403

    data = request.get_json() or {}
    return_odometer = data.get('odometer')
    fuel_level = data.get('fuel_level')
    condition_notes = data.get('condition_notes', '')

    if return_odometer is None or return_odometer == '' or not fuel_level:
        return jsonify({'success': False, 'message': 'Please provide odometer reading and fuel level'})

    try:
        return_odometer = int(return_odometer)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Odometer reading must be a whole number'})

    if return_odometer <= 0:
        return jsonify({'success': False, 'message': 'Odometer reading must be greater than zero'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'})

    cursor = conn.cursor(dictionary=True)
    try:
        # Get booking details including end_date and rates for fine calculation
        cursor.execute("""
            SELECT b.id, b.vehicle_id, b.end_date, b.daily_rate_applied, b.booking_reference,
                   b.user_id, rt.pickup_odometer_reading, v.current_odometer, v.daily_rate
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            LEFT JOIN rental_tracking rt ON b.id = rt.booking_id
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'active'
        """, (booking_id, session['user_id']))
        booking = cursor.fetchone()

        if not booking:
            cursor.execute("""
                SELECT id
                FROM bookings
                WHERE id = %s AND user_id = %s
            """, (booking_id, session['user_id']))
            existing_booking = cursor.fetchone()

            if existing_booking:
                return jsonify({'success': False, 'message': 'This booking is not active yet and cannot be returned'})

            return jsonify({'success': False, 'message': 'Booking not found'})

        minimum_return_odometer = booking['pickup_odometer_reading']
        if minimum_return_odometer is None:
            minimum_return_odometer = booking['current_odometer']
        minimum_return_odometer = int(minimum_return_odometer) if minimum_return_odometer is not None else 0

        if return_odometer < minimum_return_odometer:
            return jsonify({
                'success': False,
                'message': f'Odometer reading cannot be lower than {minimum_return_odometer} km'
            })

        # ============================================================
        # FINE CALCULATION FOR LATE RETURNS
        # ============================================================
        fine_amount = 0
        hours_late = 0
        days_late = 0
        fine_created = False
        fine_message = ""

        now = datetime.now()
        end_date = booking['end_date']

        if now > end_date:
            # Calculate raw lateness
            lateness_delta = now - end_date
            total_seconds_late = lateness_delta.total_seconds()
            total_minutes_late = total_seconds_late / 60

            # Apply 30-minute grace period
            grace_period_minutes = 30
            if total_minutes_late > grace_period_minutes:
                # Calculate hours late (with grace period subtracted)
                effective_minutes_late = total_minutes_late - grace_period_minutes
                hours_late = math.ceil(effective_minutes_late / 60)  # Round up to nearest hour

                # Get late fee multiplier from system settings (default 1.5)
                cursor.execute("""
                    SELECT setting_value FROM system_settings
                    WHERE setting_key = 'late_fee_daily_rate'
                """)
                rate_setting = cursor.fetchone()
                late_fee_multiplier = float(rate_setting['setting_value']) if rate_setting else 1.5

                # Use daily_rate_applied from booking, fallback to vehicle's daily_rate
                daily_rate = float(booking['daily_rate_applied']) if booking['daily_rate_applied'] else float(booking['daily_rate'])

                # Calculate penalty
                if hours_late <= 24:
                    # Hourly penalty (rounded up)
                    hourly_rate = (daily_rate * late_fee_multiplier) / 24
                    fine_amount = hourly_rate * hours_late
                    fine_message = f"Late return: {hours_late} hour(s) past due (within 24h, 30-min grace period applied)"
                else:
                    # Full-day penalty
                    days_late = math.ceil(hours_late / 24)
                    fine_amount = daily_rate * late_fee_multiplier * days_late
                    fine_message = f"Late return: {days_late} day(s) past due (30-min grace period applied)"

                # Create fine record
                cursor.execute("""
                    INSERT INTO fines (booking_id, user_id, hours_late, days_late,
                                    hourly_rate, daily_rate, fine_amount, reason, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                """, (booking_id, session['user_id'], hours_late, days_late,
                      (daily_rate * late_fee_multiplier) / 24 if hours_late <= 24 else None,
                      daily_rate * late_fee_multiplier if hours_late > 24 else None,
                      fine_amount, fine_message))
                fine_created = True

        # ============================================================

        # Update booking
        cursor.execute("""
            UPDATE bookings 
            SET actual_return_date = NOW(), status = 'completed'
            WHERE id = %s AND user_id = %s AND status = 'active'
        """, (booking_id, session['user_id']))
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'This booking is not active yet and cannot be returned'})
        
        # Update rental tracking
        cursor.execute("""
            UPDATE rental_tracking 
            SET actual_return_time = NOW(), return_odometer_reading = %s, 
                fuel_level_at_return = %s, condition_at_return = %s, tracking_status = 'returned'
            WHERE booking_id = %s
        """, (return_odometer, fuel_level, condition_notes, booking_id))
        
        # Update vehicle odometer
        cursor.execute("""
            UPDATE vehicles 
            SET current_odometer = %s 
            WHERE id = (SELECT vehicle_id FROM bookings WHERE id = %s)
        """, (return_odometer, booking_id))
        
        conn.commit()
        
        # ============================================================
        # SEND NOTIFICATIONS AND EMAIL
        # ============================================================
        # Get user and vehicle details for notifications
        cursor.execute("""
            SELECT u.email, u.first_name, v.model, vb.name as brand_name
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s
        """, (booking_id,))
        user_vehicle_info = cursor.fetchone()
        
        # Send notification to user
        notification_message = f'Your vehicle return for booking {booking["booking_reference"]} has been recorded.'
        if fine_created and fine_amount > 0:
            notification_message += f' A late return penalty of ₱{fine_amount:.2f} has been applied.'
        
        create_notification(
            session['user_id'],
            'Vehicle Returned Successfully',
            notification_message,
            'booking_confirmation',
            url_for('user_bp.my_bookings')
        )
        
        # Send fine notice email if late
        if fine_created and fine_amount > 0 and user_vehicle_info:
            try:
                from MyFlaskApp.services.email import EmailService
                
                # Get fine record
                cursor.execute("""
                    SELECT * FROM fines 
                    WHERE booking_id = %s 
                    ORDER BY created_at DESC LIMIT 1
                """, (booking_id,))
                fine_record = cursor.fetchone()
                
                if fine_record:
                    EmailService.send_fine_notice(
                        user={'email': user_vehicle_info['email'], 'first_name': user_vehicle_info['first_name']},
                        fine=fine_record,
                        booking=booking,
                        vehicle={'brand_name': user_vehicle_info['brand_name'], 'model': user_vehicle_info['model']}
                    )
            except Exception as email_err:
                print(f"Error sending fine notice email: {email_err}")
        
        # ============================================================
        # PREPARE RESPONSE
        # ============================================================
        response_data = {'success': True, 'message': 'Vehicle returned successfully! Thank you!'}
        
        if fine_created and fine_amount > 0:
            response_data['fine_applied'] = True
            response_data['fine_amount'] = round(fine_amount, 2)
            response_data['late_message'] = fine_message
            response_data['message'] = f'Vehicle returned successfully! Late penalty: ₱{fine_amount:.2f}'
        
        return jsonify(response_data)
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - VEHICLE DATA
# ============================================================================
@user_bp.route('/get-vehicle/<int:vehicle_id>')
@login_required
def get_vehicle(vehicle_id):
    """Get vehicle details for booking modal"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.id = %s AND v.status = 'available'
        """, (vehicle_id,))
        vehicle = cursor.fetchone()
        
        if vehicle:
            return jsonify(vehicle)
        return jsonify({'error': 'Vehicle not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - REVIEWS
# ============================================================================
@user_bp.route('/submit-review', methods=['POST'])
@login_required
def submit_review():
    """Submit a review for a completed booking with optional photo"""
    booking_id = request.form.get('booking_id', type=int)
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not booking_id or not rating or not comment:
        return jsonify({'success': False, 'message': 'Booking, rating, and comment are required'})

    if rating < 1 or rating > 5:
        return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'})

    if len(comment) > 2000:
        return jsonify({'success': False, 'message': 'Review is too long'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # Verify booking exists, is completed, and belongs to user
        cursor.execute("""
            SELECT b.id, b.vehicle_id, b.user_id
            FROM bookings b
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'completed'
        """, (booking_id, session['user_id']))
        booking = cursor.fetchone()

        if not booking:
            return jsonify({'success': False, 'message': 'Invalid booking or booking not yet completed'})

        # Check if already reviewed this specific booking
        cursor.execute("SELECT id FROM testimonials WHERE user_id = %s AND booking_id = %s", 
                   (session['user_id'], booking_id))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'You have already reviewed this booking'})

        # Handle image upload
        image_path = None
        print(f"DEBUG: Files in request: {list(request.files.keys())}")
        if 'review_image' in request.files:
            file = request.files['review_image']
            print(f"DEBUG: review_image file: {file}, filename: {file.filename if file else 'None'}")
            if file and file.filename:
                upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'base', 'uploads', 'reviews')
                print(f"DEBUG: upload_dir: {upload_dir}")
                print(f"DEBUG: upload_dir exists: {os.path.exists(upload_dir)}")
                os.makedirs(upload_dir, exist_ok=True)

                filename, error = save_upload(file, upload_dir, allowed_extensions=ALLOWED_EXTENSIONS)
                if error:
                    print(f"DEBUG: Error saving file: {error}")
                else:
                    image_path = f"reviews/{filename}"
                    print(f"DEBUG: Image saved - filename: {filename}, image_path: {image_path}")

        # Insert review (no approval needed - status set to 'approved')
        cursor.execute("""
            INSERT INTO testimonials (user_id, booking_id, vehicle_id, rating, comment, image_path, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'approved')
        """, (session['user_id'], booking_id, booking['vehicle_id'], rating, comment, image_path))

        # Notify all admins about new review
        print(f"DEBUG: Creating admin notifications...")
        
        # Get user name
        cursor.execute("SELECT CONCAT(first_name, ' ', last_name) as name FROM users WHERE id = %s", 
                   (session['user_id'],))
        user_result = cursor.fetchone()
        user_name = user_result[0] if user_result else 'A user'
        
        # Get vehicle name
        cursor.execute("""
            SELECT CONCAT(vb.name, ' ', v.model) as vehicle
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s
        """, (booking_id,))
        vehicle_result = cursor.fetchone()
        vehicle_name = vehicle_result[0] if vehicle_result else 'a vehicle'
        
        print(f"DEBUG: User: {user_name}, Vehicle: {vehicle_name}")
        
        # Get all admin users
        cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        admin_users = cursor.fetchall()
        
        print(f"DEBUG: Found {len(admin_users)} admin(s)")
        
        if admin_users:
            notification_title = "New Review Submitted"
            notification_message = f"{user_name} submitted a review for {vehicle_name}"
            notification_link = "/admin/testimonials"
            
            for admin in admin_users:
                print(f"DEBUG: Creating notification for admin {admin[0]}")
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, type, link, created_at)
                    VALUES (%s, %s, %s, 'system', %s, NOW())
                """, (admin[0], notification_title, notification_message, notification_link))
            
            print(f"DEBUG: Admin notifications created")
        
        # Commit everything together (review + notifications)
        conn.commit()
        print(f"DEBUG: Review and notifications committed successfully")
        
        return jsonify({'success': True, 'message': 'Thank you for your review!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - VERIFICATION SUBMISSION
# ============================================================================
@user_bp.route('/submit-verification', methods=['POST'])
@login_required
@require_csrf
def submit_verification():
    # Debug: Write to file
    with open('D:\\verification_debug.log', 'a') as f:
        f.write(f"[{datetime.now()}] ENTERING submit_verification()\n")
        f.write(f"[{datetime.now()}] Form keys: {list(request.form.keys())}\n")
        f.write(f"[{datetime.now()}] csrf_token: {request.form.get('csrf_token')}\n")
    print("DEBUG: ===== ENTERING submit_verification() =====")
    """Submit verification documents with OCR extraction for admin review"""
    
    # Check if already verified
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT verification_status FROM verifications 
            WHERE user_id = %s AND verification_status = 'approved'
        """, (session['user_id'],))
        existing = cursor.fetchone()
        
        if existing:
            return jsonify({'success': False, 'message': 'Your account is already verified'}), 400
    finally:
        cursor.close()
    
    # Get form data
    id_card_type = request.form.get('id_card_type', '').strip()
    
    # DEBUG: Log received data
    print(f"DEBUG: id_card_type={id_card_type}")
    print(f"DEBUG: license_front_base64 length={len(request.form.get('license_front_base64', ''))}")
    print(f"DEBUG: license_back_base64 length={len(request.form.get('license_back_base64', ''))}")
    print(f"DEBUG: id_card_image_base64 length={len(request.form.get('id_card_image_base64', ''))}")
    print(f"DEBUG: selfie_image_base64 length={len(request.form.get('selfie_image_base64', ''))}")
    
    # Validate required fields
    if not id_card_type:
        return jsonify({'success': False, 'message': 'ID card type is required'}), 400
    
    # Handle image uploads (base64 from camera OR file upload)
    # Check for base64 camera data first, fall back to file upload
    license_front_base64 = request.form.get('license_front_base64', '').strip()
    license_back_base64 = request.form.get('license_back_base64', '').strip()
    id_card_base64 = request.form.get('id_card_image_base64', '').strip()
    selfie_base64 = request.form.get('selfie_image_base64', '').strip()
    
    # Also check for file uploads as fallback
    license_front_file = request.files.get('license_front')
    license_back_file = request.files.get('license_back')
    id_card_file = request.files.get('id_card_image')
    selfie_file = request.files.get('selfie_image')
    
    # DEBUG: Log file uploads
    print(f"DEBUG: license_front_file={license_front_file.filename if license_front_file else 'None'}")
    print(f"DEBUG: license_back_file={license_back_file.filename if license_back_file else 'None'}")
    print(f"DEBUG: id_card_file={id_card_file.filename if id_card_file else 'None'}")
    print(f"DEBUG: selfie_file={selfie_file.filename if selfie_file else 'None'}")
    
    # Validate that license front image is provided (required field)
    has_license_front = bool(license_front_base64) or (license_front_file and license_front_file.filename)
    if not has_license_front:
        return jsonify({'success': False, 'message': 'License front image is required'}), 400
    
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    license_front_path = None
    license_back_path = None
    id_card_path = None
    selfie_path = None
    
    prefix = f"user_{session['user_id']}"
    
    # License Front Image
    if license_front_base64:
        filename, error = save_base64_upload(
            license_front_base64, UPLOAD_FOLDER, 
            ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, 
            f"{prefix}_license_front"
        )
        if error:
            return jsonify({'success': False, 'message': f'License front: {error}'}), 400
        license_front_path = filename
    elif license_front_file and license_front_file.filename:
        filename, error = save_upload(license_front_file, UPLOAD_FOLDER, allowed_extensions=ALLOWED_EXTENSIONS)
        if error:
            return jsonify({'success': False, 'message': f'License front: {error}'}), 400
        license_front_path = filename
    
    # License Back Image
    if license_back_base64:
        filename, error = save_base64_upload(
            license_back_base64, UPLOAD_FOLDER,
            ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB,
            f"{prefix}_license_back"
        )
        if error:
            if license_front_path:
                os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            return jsonify({'success': False, 'message': f'License back: {error}'}), 400
        license_back_path = filename
    elif license_back_file and license_back_file.filename:
        filename, error = save_upload(license_back_file, UPLOAD_FOLDER, allowed_extensions=ALLOWED_EXTENSIONS)
        if error:
            if license_front_path:
                os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            return jsonify({'success': False, 'message': f'License back: {error}'}), 400
        license_back_path = filename
    
    # ID Card Image
    if id_card_base64:
        filename, error = save_base64_upload(
            id_card_base64, UPLOAD_FOLDER,
            ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB,
            f"{prefix}_id"
        )
        if error:
            if license_front_path: os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            if license_back_path: os.remove(os.path.join(UPLOAD_FOLDER, license_back_path))
            return jsonify({'success': False, 'message': f'ID card: {error}'}), 400
        id_card_path = filename
    elif id_card_file and id_card_file.filename:
        filename, error = save_upload(id_card_file, UPLOAD_FOLDER, allowed_extensions=ALLOWED_EXTENSIONS)
        if error:
            if license_front_path: os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            if license_back_path: os.remove(os.path.join(UPLOAD_FOLDER, license_back_path))
            return jsonify({'success': False, 'message': f'ID card: {error}'}), 400
        id_card_path = filename
    
    # Selfie Image
    if selfie_base64:
        filename, error = save_base64_upload(
            selfie_base64, UPLOAD_FOLDER,
            ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB,
            f"{prefix}_selfie"
        )
        if error:
            if license_front_path: os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            if license_back_path: os.remove(os.path.join(UPLOAD_FOLDER, license_back_path))
            if id_card_path: os.remove(os.path.join(UPLOAD_FOLDER, id_card_path))
            return jsonify({'success': False, 'message': f'Selfie: {error}'}), 400
        selfie_path = filename
    elif selfie_file and selfie_file.filename:
        filename, error = save_upload(selfie_file, UPLOAD_FOLDER, allowed_extensions=ALLOWED_EXTENSIONS)
        if error:
            if license_front_path: os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            if license_back_path: os.remove(os.path.join(UPLOAD_FOLDER, license_back_path))
            if id_card_path: os.remove(os.path.join(UPLOAD_FOLDER, id_card_path))
            return jsonify({'success': False, 'message': f'Selfie: {error}'}), 400
        selfie_path = filename
    
    # ============================================================
    # OCR VALIDATION - Extract data for admin review
    # ============================================================
    ocr_result = None
    try:
        front_full_path = os.path.join(UPLOAD_FOLDER, license_front_path) if license_front_path else None
        back_full_path = os.path.join(UPLOAD_FOLDER, license_back_path) if license_back_path else None
        
        if front_full_path:
            ocr_result = LicenseOCRService.validate_license(
                front_image_path=front_full_path,
                back_image_path=back_full_path
            )
            
    except Exception as e:
        print(f"OCR Error: {e}")
        ocr_result = {
            'success': False,
            'confidence_score': 0,
            'errors': [str(e)]
        }
    
    # Insert into database with OCR results
    cursor = conn.cursor()
    try:
        # Check if user already has pending verification
        cursor.execute("""
            SELECT id FROM verifications 
            WHERE user_id = %s AND verification_status IN ('pending', 'approved')
        """, (session['user_id'],))
        existing = cursor.fetchone()
        
        if existing:
            return jsonify({'success': False, 'message': 'You already have a pending verification request'}), 400
        
        # Build OCR data for storage
        ocr_data = {
            'confidence_score': ocr_result.get('confidence_score', 0) if ocr_result else 0,
            'extracted_license_number': ocr_result.get('extracted_license_number') if ocr_result else None,
            'extracted_id_number': ocr_result.get('extracted_id_number') if ocr_result else None,
            'extracted_expiry': ocr_result.get('extracted_expiry') if ocr_result else None,
            'license_match': None,
            'expiry_match': None,
            'is_expired': None,
            'errors': ocr_result.get('errors', []) if ocr_result else []
        }
        
        # Convert to JSON string for database storage
        ocr_json = json.dumps(ocr_data)
        
        cursor.execute("""
            INSERT INTO verifications (
                user_id, license_front_image, license_back_image,
                id_card_type, id_card_image, selfie_image,
                verification_status, ocr_confidence_score, ocr_extracted_license, 
                ocr_extracted_expiry, ocr_raw_data, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, NOW())
        """, (
            session['user_id'],
            license_front_path, license_back_path,
            id_card_type, id_card_path, selfie_path,
            ocr_data['confidence_score'],
            ocr_data['extracted_license_number'],
            ocr_data['extracted_expiry'],
            ocr_json
        ))
        
        conn.commit()
        
        # Create notification for admin
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, link, created_at)
            VALUES (%s, 'verification', 'New Verification Request', 
                    'A new verification request needs review', '/admin/manage-verifications', NOW())
        """, (1,))  # Admin user ID = 1
        
        conn.commit()
        
        # Prepare response with OCR feedback for user
        response_data = {
            'success': True, 
            'message': 'Verification documents submitted successfully! Admin will review your documents.',
        }
        
        # Add OCR feedback if available
        if ocr_result:
            confidence = ocr_result.get('confidence_score', 0)
            response_data['ocr_confidence'] = confidence
            
            if confidence < 0.5:
                response_data['ocr_warning'] = 'Image quality is low. Admin may request clearer images.'
            elif ocr_result.get('license_match') is False:
                response_data['ocr_warning'] = 'Extracted license number does not match your input. Please verify.'
            elif ocr_result.get('expiry_match') is False:
                response_data['ocr_warning'] = 'Extracted expiry date does not match your input. Please verify.'
        
        return jsonify(response_data)
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - VEHICLE AVAILABILITY
# ============================================================================
@user_bp.route('/api/vehicles/availability')
def get_vehicle_availability():
    """Get availability count for each vehicle for today"""
    from datetime import datetime
    
    conn = get_db_connection()
    if not conn:
        return jsonify({}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        today = datetime.now().date()
        
        cursor.execute("""
            SELECT v.id, COUNT(b.id) as booked_count
            FROM vehicles v
            LEFT JOIN bookings b ON v.id = b.vehicle_id
            AND b.status IN ('confirmed', 'active', 'pending')
            AND DATE(b.start_date) <= %s
            AND DATE(b.end_date) >= %s
            WHERE v.status = 'available'
            GROUP BY v.id
        """, (today, today))
        
        results = cursor.fetchall()
        
        availability = {}
        for row in results:
            available = 1 - row['booked_count']
            if available < 0:
                available = 0
            availability[row['id']] = available
        
        return jsonify(availability)
        
    except Exception as e:
        print(f"Error getting availability: {e}")
        return jsonify({}), 500
    finally:
        cursor.close()
        conn.close()
