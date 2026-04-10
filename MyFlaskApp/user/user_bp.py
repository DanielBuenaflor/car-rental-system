# ============================================================================
# IMPORTS
# ============================================================================
import os
import json
import base64
import re
from functools import wraps
from datetime import datetime, timedelta

from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from MyFlaskApp import get_db_connection
from MyFlaskApp.payment.invoice_service import InvoiceService
from MyFlaskApp.utils.ocr_service import LicenseOCRService


# ============================================================================
# CONFIGURATION
# ============================================================================
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    'base', 'uploads', 'verifications'
)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}


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

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    conn = get_db_connection()
    if not conn:
        return render_template('user_dashboard.html', session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get user stats
        cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE user_id = %s", 
                      (session['user_id'],))
        booking_count = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM testimonials 
            WHERE user_id = %s AND status = 'approved'
        """, (session['user_id'],))
        testimonial_count = cursor.fetchone()['count']
        
        # Get verification status
        cursor.execute("""
            SELECT verification_status, rejection_reason 
            FROM verifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT 1
        """, (session['user_id'],))
        verification = cursor.fetchone()
        verification_status = verification['verification_status'] if verification else 'not_submitted'
        rejection_reason = verification['rejection_reason'] if verification else None
        
        # Get recent bookings
        cursor.execute("""
            SELECT b.*, v.model, v.brand_id, vb.name as brand_name
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC
            LIMIT 3
        """, (session['user_id'],))
        recent_bookings = cursor.fetchall()
        
        return render_template(
            'user_dashboard.html',
            session=session,
            booking_count=booking_count,
            testimonial_count=testimonial_count,
            verification_status=verification_status,
            rejection_reason=rejection_reason,
            recent_bookings=recent_bookings
        )
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('user_dashboard.html', session=session)
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
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            state = request.form.get('state', '').strip()
            postal_code = request.form.get('postal_code', '').strip()
            country = request.form.get('country', '').strip()
            
            cursor.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s, phone = %s, 
                    address = %s, city = %s, state = %s, 
                    postal_code = %s, country = %s
                WHERE id = %s
            """, (first_name, last_name, phone, address, city, state, postal_code, country, 
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
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters'})
    
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
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
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
            session=session
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
        cursor.execute("""
            SELECT b.*, v.model, v.year, v.license_plate, v.daily_rate, 
                   vb.name as brand_name, vb.id as brand_id
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC
        """, (session['user_id'],))
        bookings = cursor.fetchall()
        
        return render_template('my_bookings.html', bookings=bookings, session=session)
    except Exception as e:
        print(f"My bookings error: {e}")
        return render_template('my_bookings.html', bookings=[], session=session)
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/active-rentals')
@login_required
def active_rentals():
    """View active rentals with countdown"""
    conn = get_db_connection()
    if not conn:
        return render_template('rental_tracking.html', active_rentals=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get active rentals for the user
        cursor.execute("""
            SELECT b.*, v.model, v.license_plate, vb.name as brand_name,
                   rt.pickup_time, rt.expected_return_time, rt.tracking_status,
                   rt.current_odometer_reading, rt.fuel_level_at_pickup
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            LEFT JOIN rental_tracking rt ON b.id = rt.booking_id
            WHERE b.user_id = %s AND b.status IN ('confirmed', 'active')
            ORDER BY b.start_date ASC
        """, (session['user_id'],))
        active_rentals = cursor.fetchall()
        
        # Calculate countdown for each rental
        now = datetime.now()
        for rental in active_rentals:
            if rental['start_date']:
                start = rental['start_date']
                
                if now < start:
                    # Rental hasn't started yet
                    days_left = (start - now).days
                    hours_left = (start - now).seconds // 3600
                    rental['status_message'] = f"Starts in {days_left} days, {hours_left} hours"
                    rental['countdown_type'] = 'upcoming'
                elif rental['end_date']:
                    # Rental is active
                    end = rental['end_date']
                    if now < end:
                        days_left = (end - now).days
                        hours_left = (end - now).seconds // 3600
                        rental['status_message'] = f"Ends in {days_left} days, {hours_left} hours"
                        rental['countdown_type'] = 'active'
                    else:
                        rental['status_message'] = "OVERDUE - Please return vehicle"
                        rental['countdown_type'] = 'overdue'
        
        return render_template('rental_tracking.html', active_rentals=active_rentals, session=session)
        
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
            WHERE i.invoice_id = %s AND b.user_id = %s
        """, (invoice_id, session['user_id']))
        invoice = cursor.fetchone()
        
        if not invoice:
            flash('Invoice not found', 'error')
            return redirect(url_for('user_bp.invoices'))
        
        # Calculate balance due
        invoice['balance_due'] = invoice.get('total_amount', 0) - invoice.get('paid_amount', 0)
        
        return render_template('invoice_view.html', invoice=invoice, session=session)
        
    except Exception as e:
        print(f"Error loading invoice: {str(e)}")
        flash(f'Error loading invoice: {str(e)}', 'error')
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
    
    # Check if user is verified
    conn = get_db_connection()
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
    finally:
        cursor.close()
    
    data = request.get_json()
    vehicle_id = data.get('vehicle_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    pickup_location = data.get('pickup_location')
    return_location = data.get('return_location')
    
    if not all([vehicle_id, start_date, end_date, pickup_location, return_location]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if vehicle is available
        cursor.execute("""
            SELECT * FROM vehicles 
            WHERE id = %s AND status = 'available'
        """, (vehicle_id,))
        vehicle = cursor.fetchone()
        
        if not vehicle:
            return jsonify({'success': False, 'message': 'Vehicle is not available'})
        
        # Check for overlapping bookings
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
        
        # Calculate total amount
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        rental_days = (end - start).days
        
        if rental_days <= 0:
            return jsonify({'success': False, 'message': 'End date must be after start date'})
        
        daily_rate = float(vehicle['daily_rate'])
        subtotal = daily_rate * rental_days
        tax_amount = subtotal * 0.10
        total_amount = subtotal + tax_amount
        
        # Generate booking reference
        booking_reference = f"BK-{datetime.now().strftime('%Y%m%d')}-{session['user_id']}-{vehicle_id}"
        
        # Create booking
        cursor.execute("""
            INSERT INTO bookings (
                user_id, vehicle_id, start_date, end_date, pickup_location, return_location,
                rental_days, daily_rate_applied, subtotal, tax_amount, total_amount,
                security_deposit, status, booking_reference, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, NOW()
            )
        """, (
            session['user_id'], vehicle_id, start_date, end_date, pickup_location, return_location,
            rental_days, daily_rate, subtotal, tax_amount, total_amount,
            vehicle['security_deposit'], booking_reference
        ))
        
        booking_id = cursor.lastrowid
        conn.commit()
        

        
        # Redirect to payment checkout page
        return jsonify({
            'success': True, 
            'message': 'Booking created! Proceed to payment.',
            'redirect': url_for('payment_bp.checkout', booking_id=booking_id),
            'booking_id': booking_id,
            'total_amount': total_amount
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/cancel-booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    """Cancel a booking"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE bookings 
            SET status = 'cancelled', cancelled_by = 'user', cancelled_at = NOW()
            WHERE id = %s AND user_id = %s AND status IN ('pending', 'confirmed')
        """, (booking_id, session['user_id']))
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Booking not found or cannot be cancelled'})
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Booking cancelled successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@user_bp.route('/request-extension/<int:booking_id>', methods=['POST'])
@login_required
def request_extension(booking_id):
    """Request rental extension"""
    data = request.get_json()
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


@user_bp.route('/return-vehicle/<int:booking_id>', methods=['POST'])
@login_required
def return_vehicle(booking_id):
    """Mark vehicle as returned"""
    data = request.get_json()
    return_odometer = data.get('odometer')
    fuel_level = data.get('fuel_level')
    condition_notes = data.get('condition_notes', '')
    
    if not return_odometer or not fuel_level:
        return jsonify({'success': False, 'message': 'Please provide odometer reading and fuel level'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'})
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Update booking
        cursor.execute("""
            UPDATE bookings 
            SET actual_return_date = NOW(), status = 'completed'
            WHERE id = %s AND user_id = %s AND status = 'active'
        """, (booking_id, session['user_id']))
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Booking not found or already returned'})
        
        # Update rental tracking
        cursor.execute("""
            UPDATE rental_tracking 
            SET actual_return_time = NOW(), return_odometer_reading = %s, 
                fuel_level_at_return = %s, condition_notes = %s, tracking_status = 'returned'
            WHERE booking_id = %s
        """, (return_odometer, fuel_level, condition_notes, booking_id))
        
        # Update vehicle odometer
        cursor.execute("""
            UPDATE vehicles 
            SET current_odometer = %s 
            WHERE id = (SELECT vehicle_id FROM bookings WHERE id = %s)
        """, (return_odometer, booking_id))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Vehicle returned successfully! Thank you!'})
        
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
# API ROUTES - TESTIMONIALS
# ============================================================================
@user_bp.route('/submit-testimonial', methods=['POST'])
@login_required
def submit_testimonial():
    """Submit a testimonial (users can submit up to 10 testimonials)"""
    data = request.get_json()
    rating = data.get('rating')
    comment = data.get('comment', '').strip()
    
    if not rating or not comment:
        return jsonify({'success': False, 'message': 'Rating and comment are required'})
    
    if rating < 1 or rating > 5:
        return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    cursor = conn.cursor()
    try:
        # Check how many testimonials user has submitted (excluding rejected ones)
        cursor.execute("""
            SELECT COUNT(*) as count FROM testimonials 
            WHERE user_id = %s AND status != 'rejected'
        """, (session['user_id'],))
        result = cursor.fetchone()
        testimonial_count = result[0] if result else 0
        
        # Allow up to 10 testimonials per user
        if testimonial_count >= 10:
            return jsonify({
                'success': False, 
                'message': f'You have already submitted {testimonial_count} testimonials. Maximum allowed is 10.'
            })
        
        # Insert new testimonial
        cursor.execute("""
            INSERT INTO testimonials (user_id, rating, comment, status, created_at)
            VALUES (%s, %s, %s, 'pending', NOW())
        """, (session['user_id'], rating, comment))
        conn.commit()
        
        remaining = 9 - testimonial_count
        return jsonify({
            'success': True, 
            'message': f'Thank you for your review! It will be visible after admin approval. You can submit {remaining} more review(s).',
            'remaining': remaining,
            'total_submitted': testimonial_count + 1
        })
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
def submit_verification():
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
    license_number = request.form.get('license_number', '').strip()
    license_expiry = request.form.get('license_expiry', '').strip()
    id_card_type = request.form.get('id_card_type', '').strip()
    id_card_number = request.form.get('id_card_number', '').strip()
    
    # Validate required fields
    if not all([license_number, license_expiry, id_card_type, id_card_number]):
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
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
    
    # Validate that license front image is provided (required field)
    has_license_front = bool(license_front_base64) or (license_front_file and allowed_file(license_front_file.filename))
    if not has_license_front:
        return jsonify({'success': False, 'message': 'License front image is required'}), 400
    
    # Create upload directory if not exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Save images (base64 takes priority over file upload)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    license_front_path = None
    license_back_path = None
    id_card_path = None
    selfie_path = None
    
    # License Front Image
    if license_front_base64:
        filename = f"user_{session['user_id']}_license_front_{timestamp}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if save_base64_image(license_front_base64, filepath):
            license_front_path = filename
    elif license_front_file and allowed_file(license_front_file.filename):
        ext = license_front_file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{session['user_id']}_license_front_{timestamp}.{ext}"
        license_front_file.save(os.path.join(UPLOAD_FOLDER, filename))
        license_front_path = filename
    
    # License Back Image
    if license_back_base64:
        filename = f"user_{session['user_id']}_license_back_{timestamp}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if save_base64_image(license_back_base64, filepath):
            license_back_path = filename
    elif license_back_file and allowed_file(license_back_file.filename):
        ext = license_back_file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{session['user_id']}_license_back_{timestamp}.{ext}"
        license_back_file.save(os.path.join(UPLOAD_FOLDER, filename))
        license_back_path = filename
    
    # ID Card Image
    if id_card_base64:
        filename = f"user_{session['user_id']}_id_{timestamp}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if save_base64_image(id_card_base64, filepath):
            id_card_path = filename
    elif id_card_file and allowed_file(id_card_file.filename):
        ext = id_card_file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{session['user_id']}_id_{timestamp}.{ext}"
        id_card_file.save(os.path.join(UPLOAD_FOLDER, filename))
        id_card_path = filename
    
    # Selfie Image
    if selfie_base64:
        filename = f"user_{session['user_id']}_selfie_{timestamp}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if save_base64_image(selfie_base64, filepath):
            selfie_path = filename
    elif selfie_file and allowed_file(selfie_file.filename):
        ext = selfie_file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{session['user_id']}_selfie_{timestamp}.{ext}"
        selfie_file.save(os.path.join(UPLOAD_FOLDER, filename))
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
                back_image_path=back_full_path,
                expected_license_number=license_number,
                expected_expiry=license_expiry
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
            'extracted_expiry': ocr_result.get('extracted_expiry') if ocr_result else None,
            'license_match': ocr_result.get('license_match') if ocr_result else None,
            'expiry_match': ocr_result.get('expiry_match') if ocr_result else None,
            'is_expired': ocr_result.get('is_expired') if ocr_result else None,
            'errors': ocr_result.get('errors', []) if ocr_result else []
        }
        
        # Convert to JSON string for database storage
        ocr_json = json.dumps(ocr_data)
        
        cursor.execute("""
            INSERT INTO verifications (
                user_id, license_number, license_expiry_date, 
                license_front_image, license_back_image,
                id_card_type, id_card_number, id_card_image, selfie_image,
                verification_status, ocr_confidence_score, ocr_extracted_license, 
                ocr_extracted_expiry, ocr_raw_data, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, NOW())
        """, (
            session['user_id'], license_number, license_expiry,
            license_front_path, license_back_path,
            id_card_type, id_card_number, id_card_path, selfie_path,
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