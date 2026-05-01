# ============================================================================
# IMPORTS
# ============================================================================
import os
import json
import base64
import re
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
# CONFIGURATION
# ============================================================================
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS  # Use secure upload module's extensions
MAX_FILE_SIZE_MB = 5
# Correct path: from MyFlaskApp/blueprints/user/routes.py -> MyFlaskApp/base/uploads/verifications/
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
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
# PAGE ROUTES - PROFILE (Dashboard moved to user_bp.py to avoid duplicates)
# ============================================================================


@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and update user profile"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect('/user/dashboard')
    
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
        return redirect('/user/dashboard')
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
                   rt.pickup_odometer_reading, rt.fuel_level_at_pickup
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
    print("DEBUG: ===== ENTERING verification_page() in blueprints/user/routes.py =====")
    """Show verification page"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect('/user/dashboard')
    
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
        print(f"DEBUG: Token generated in blueprints: {token}")
        
        return render_template('verification.html', 
                               verification=verification, 
                               session=session)
    except Exception as e:
        flash(f'Error loading verification: {str(e)}', 'error')
        return redirect('/user/dashboard')
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
    
    # Extract and validate data first (before any DB operations)
    data = request.get_json()
    vehicle_id = data.get('vehicle_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    pickup_location = data.get('pickup_location')
    return_location = data.get('return_location')
    return_location_id = data.get('return_location_id')
    is_custom_pickup = data.get('is_custom_pickup', False)
    is_custom_return = data.get('is_custom_return', False)
    
    # Custom pickup fields
    custom_pickup_address = data.get('custom_pickup_address')
    custom_pickup_lat = data.get('custom_pickup_lat')
    custom_pickup_lng = data.get('custom_pickup_lng')
    
    # Custom return fields - DEFINE THEM FIRST
    custom_return_address = data.get('custom_return_address')
    custom_return_lat = data.get('custom_return_lat')
    custom_return_lng = data.get('custom_return_lng')
    
    one_way_fee = float(data.get('one_way_fee', 0))
    delivery_fee = float(data.get('delivery_fee', 0))
    
    # Handle NULLs: If user chose standard branch, set custom fields to None
    # Convert empty strings to None for proper NULL storage
    if not is_custom_pickup:
        custom_pickup_address = None
        custom_pickup_lat = None
        custom_pickup_lng = None
    else:
        # If custom but empty string, convert to None
        custom_pickup_address = custom_pickup_address if custom_pickup_address else None
        custom_pickup_lat = custom_pickup_lat if custom_pickup_lat else None
        custom_pickup_lng = custom_pickup_lng if custom_pickup_lng else None
    
    if not is_custom_return:
        custom_return_address = None
        custom_return_lat = None
        custom_return_lng = None
    else:
        # If custom but empty string, convert to None
        custom_return_address = custom_return_address if custom_return_address else None
        custom_return_lat = custom_return_lat if custom_return_lat else None
        custom_return_lng = custom_return_lng if custom_return_lng else None
    
    if not all([vehicle_id, start_date, end_date, pickup_location, return_location]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    # Single connection for entire operation
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if user is verified
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
        total_before_tax = subtotal + one_way_fee + delivery_fee
        tax_amount = total_before_tax * 0.10
        total_amount = total_before_tax + tax_amount
        
        # Generate booking reference
        import secrets
        booking_reference = f"BK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{session['user_id']}-{vehicle_id}-{secrets.token_hex(4)}"
        
        # Create booking
        cursor.execute("""
            INSERT INTO bookings (
                user_id, vehicle_id, start_date, end_date, pickup_location, return_location,
                rental_days, daily_rate_applied, subtotal, tax_amount, total_amount,
                security_deposit, status, booking_reference, created_at,
                return_location_id, custom_pickup_address,
                custom_pickup_lat, custom_pickup_lng, delivery_fee, one_way_fee,
                custom_return_address, custom_return_lat, custom_return_lng
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            session['user_id'], vehicle_id, start_date, end_date, pickup_location, return_location,
            rental_days, daily_rate, subtotal, tax_amount, total_amount,
            vehicle['security_deposit'], 'pending', booking_reference,
            return_location_id, custom_pickup_address,
            custom_pickup_lat, custom_pickup_lng, delivery_fee, one_way_fee,
            custom_return_address, custom_return_lat, custom_return_lng
        ))
        
        booking_id = cursor.lastrowid
        conn.commit()
        
        conn.commit()
        
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
        
        conn.commit()
        flash('Booking cancelled successfully.', 'success')
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
@require_csrf
def submit_verification():
    print("DEBUG: ===== ENTERING submit_verification() in blueprints/user/routes.py =====")
    """Submit verification documents with OCR extraction for admin review"""
    
    # Check if already verified
    print("DEBUG: Checking if already verified...")
    conn = get_db_connection()
    if not conn:
        print("DEBUG: Database connection failed")
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT verification_status FROM verifications 
            WHERE user_id = %s AND verification_status = 'approved'
        """, (session['user_id'],))
        existing = cursor.fetchone()
        
        if existing:
            print(f"DEBUG: Already verified! Status: {existing['verification_status']}")
            return jsonify({'success': False, 'message': 'Your account is already verified'}), 400
    finally:
        cursor.close()
    
    # Get form data
    print("DEBUG: Getting form data...")
    id_card_type = request.form.get('id_card_type', '').strip()
    print(f"DEBUG: id_card_type='{id_card_type}'")
    
    # Validate required fields
    if not id_card_type:
        print("DEBUG: ID card type missing!")
        return jsonify({'success': False, 'message': 'ID card type is required'}), 400
    
    # Handle image uploads (base64 from camera OR file upload)
    # Check for base64 camera data first, fall back to file upload
    print("DEBUG: Getting image data...")
    license_front_base64 = request.form.get('license_front_base64', '').strip()
    license_back_base64 = request.form.get('license_back_base64', '').strip()
    id_card_base64 = request.form.get('id_card_image_base64', '').strip()
    selfie_base64 = request.form.get('selfie_image_base64', '').strip()
    
    print(f"DEBUG: license_front_base64 length={len(license_front_base64)}")
    print(f"DEBUG: license_back_base64 length={len(license_back_base64)}")
    print(f"DEBUG: id_card_base64 length={len(id_card_base64)}")
    print(f"DEBUG: selfie_base64 length={len(selfie_base64)}")
    
    # Also check for file uploads as fallback
    license_front_file = request.files.get('license_front')
    license_back_file = request.files.get('license_back')
    id_card_file = request.files.get('id_card_image')
    selfie_file = request.files.get('selfie_image')
    
    print(f"DEBUG: license_front_file={license_front_file.filename if license_front_file else 'None'}")
    print(f"DEBUG: license_back_file={license_back_file.filename if license_back_file else 'None'}")
    print(f"DEBUG: id_card_file={id_card_file.filename if id_card_file else 'None'}")
    print(f"DEBUG: selfie_file={selfie_file.filename if selfie_file else 'None'}")
    
    # Validate that license front image is provided (required field)
    has_license_front = bool(license_front_base64) or (license_front_file and allowed_file(license_front_file.filename))
    if not has_license_front:
        print("DEBUG: License front image missing!")
        return jsonify({'success': False, 'message': 'License front image is required'}), 400
    
    print("DEBUG: Creating upload folder...")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print(f"DEBUG: UPLOAD_FOLDER exists: {os.path.exists(UPLOAD_FOLDER)}")
    
    license_front_path = None
    license_back_path = None
    id_card_path = None
    selfie_path = None
    
    prefix = f"user_{session['user_id']}"
    print(f"DEBUG: prefix={prefix}")
    
    # License Front Image
    print("DEBUG: Processing license front image...")
    print(f"DEBUG: type(allowed_file) = {type(allowed_file)}")
    if license_front_base64:
        filename, error = save_base64_upload(
            license_front_base64, UPLOAD_FOLDER, 
            ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, 
            f"{prefix}_license_front"
        )
        if error:
            return jsonify({'success': False, 'message': f'License front: {error}'}), 400
        license_front_path = filename
    elif license_front_file and allowed_file(license_front_file.filename):
        # Direct file save - bypasses secure_upload to avoid file pointer issues
        filename = f"{prefix}_license_front_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        try:
            license_front_file.save(filepath)
            license_front_path = filename
        except Exception as e:
            return jsonify({'success': False, 'message': f'License front: Error saving file: {str(e)}'}), 400
    
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
    elif license_back_file and allowed_file(license_back_file.filename):
        # Direct file save - bypasses secure_upload to avoid file pointer issues
        filename = f"{prefix}_license_back_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        try:
            license_back_file.save(filepath)
            license_back_path = filename
        except Exception as e:
            if license_front_path:
                os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            return jsonify({'success': False, 'message': f'License back: Error saving file: {str(e)}'}), 400
    
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
    elif id_card_file and allowed_file(id_card_file.filename):
        # Direct file save - bypasses secure_upload to avoid file pointer issues
        filename = f"{prefix}_id_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        try:
            id_card_file.save(filepath)
            id_card_path = filename
        except Exception as e:
            if license_front_path: os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            if license_back_path: os.remove(os.path.join(UPLOAD_FOLDER, license_back_path))
            return jsonify({'success': False, 'message': f'ID card: Error saving file: {str(e)}'}), 400
    
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
    elif selfie_file and allowed_file(selfie_file.filename):
        # Direct file save - bypasses secure_upload to avoid file pointer issues
        filename = f"{prefix}_selfie_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        try:
            selfie_file.save(filepath)
            selfie_path = filename
        except Exception as e:
            if license_front_path: os.remove(os.path.join(UPLOAD_FOLDER, license_front_path))
            if license_back_path: os.remove(os.path.join(UPLOAD_FOLDER, license_back_path))
            if id_card_path: os.remove(os.path.join(UPLOAD_FOLDER, id_card_path))
            return jsonify({'success': False, 'message': f'Selfie: Error saving file: {str(e)}'}), 400
    
    # ============================================================
    # OCR VALIDATION - Extract data for admin review
    # ============================================================
    print("DEBUG: Starting OCR validation...")
    ocr_result = None
    name_mismatch = False
    name_mismatch_details = []
    
    try:
        front_full_path = os.path.join(UPLOAD_FOLDER, license_front_path) if license_front_path else None
        back_full_path = os.path.join(UPLOAD_FOLDER, license_back_path) if license_back_path else None
        id_card_full_path = os.path.join(UPLOAD_FOLDER, id_card_path) if id_card_path else None
        selfie_full_path = os.path.join(UPLOAD_FOLDER, selfie_path) if selfie_path else None
        
        print(f"DEBUG: front_full_path={front_full_path}")
        print(f"DEBUG: back_full_path={back_full_path}")
        print(f"DEBUG: id_card_full_path={id_card_full_path}")
        print(f"DEBUG: selfie_full_path={selfie_full_path}")
        
        # Extract name from License (front image)
        license_name = None
        if front_full_path:
            print("DEBUG: Calling LicenseOCRService.validate_license...")
            ocr_result = LicenseOCRService.validate_license(
                front_image_path=front_full_path,
                back_image_path=back_full_path
            )
            print(f"DEBUG: OCR result={ocr_result}")
            license_name = ocr_result.get('extracted_name') if ocr_result else None
            
            # Extract text from ID card and selfie for name comparison
            id_card_name = None
            selfie_name = None
            
            if id_card_full_path:
                print("DEBUG: Extracting text from ID card...")
                id_card_text = LicenseOCRService.extract_text(id_card_full_path)
                if id_card_text:
                    id_card_name = LicenseOCRService.extract_name(id_card_text)
                    print(f"DEBUG: ID card name: {id_card_name}")
            
            if selfie_full_path:
                print("DEBUG: Extracting text from selfie...")
                selfie_text = LicenseOCRService.extract_text(selfie_full_path)
                if selfie_text:
                    selfie_name = LicenseOCRService.extract_name(selfie_text)
                    print(f"DEBUG: Selfie name: {selfie_name}")
            
            # Compare names across documents
            print("DEBUG: Comparing names across documents...")
            names_found = [n for n in [license_name, id_card_name, selfie_name] if n]
            
            if len(names_found) >= 2:
                # Normalize names for comparison (uppercase, remove extra spaces)
                normalized_names = [n.upper().replace('  ', ' ') for n in names_found]
                print(f"DEBUG: Normalized names: {normalized_names}")
                
                # Check if all names match
                if len(set(normalized_names)) > 1:
                    name_mismatch = True
                    name_mismatch_details = [f"License: {license_name}", f"ID Card: {id_card_name}", f"Selfie: {selfie_name}"]
                    print(f"DEBUG: NAME MISMATCH! Details: {name_mismatch_details}")
                else:
                    print("DEBUG: All names match!")
            else:
                print("DEBUG: Not enough names extracted for comparison")
        
    except Exception as e:
        print(f"OCR Error: {e}")
        ocr_result = {
            'success': False,
            'confidence_score': 0,
            'errors': [str(e)]
        }
    
    # Reject if names don't match
    if name_mismatch:
        # Clean up uploaded files
        for f in [license_front_path, license_back_path, id_card_path, selfie_path]:
            if f:
                try:
                    os.remove(os.path.join(UPLOAD_FOLDER, f))
                except:
                    pass
        return jsonify({
            'success': False, 
            'message': 'Name mismatch across documents. Please ensure all documents show the same name.',
            'details': name_mismatch_details
        }), 400
    
    # Build OCR data for storage
    print("DEBUG: Building OCR data...")
    ocr_data = {
        'confidence_score': ocr_result.get('confidence_score', 0) if ocr_result else 0,
        'extracted_license_number': ocr_result.get('extracted_license_number') if ocr_result else None,
        'extracted_expiry': ocr_result.get('extracted_expiry') if ocr_result else None,
        'extracted_name': ocr_result.get('extracted_name') if ocr_result else None,
        'license_match': ocr_result.get('license_match') if ocr_result else None,
        'expiry_match': ocr_result.get('expiry_match') if ocr_result else None,
        'name_match': not name_mismatch,
        'is_expired': ocr_result.get('is_expired') if ocr_result else None,
        'errors': ocr_result.get('errors', []) if ocr_result else []
    }
    
    # Convert to JSON string for database storage
    ocr_json = json.dumps(ocr_data)
    print(f"DEBUG: OCR JSON={ocr_json[:200]}...")  # First 200 chars
    
    # Insert into database with OCR results
    print("DEBUG: Inserting into database...")
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if user already has pending verification
        print("DEBUG: Checking for existing verification...")
        cursor.execute("""
            SELECT id, verification_status, license_front_image, license_back_image, 
                   id_card_image, selfie_image
            FROM verifications 
            WHERE user_id = %s AND verification_status = 'pending'
        """, (session['user_id'],))
        existing = cursor.fetchone()
        
        # If pending verification exists, delete it and its files
        if existing:
            print(f"DEBUG: Found existing pending verification! ID: {existing['id']}")
            # Delete old image files
            old_files = [
                existing.get('license_front_image'),
                existing.get('license_back_image'),
                existing.get('id_card_image'),
                existing.get('selfie_image')
            ]
            for old_file in old_files:
                if old_file:
                    old_path = os.path.join(UPLOAD_FOLDER, old_file)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                            print(f"DEBUG: Deleted old file: {old_file}")
                        except Exception as e:
                            print(f"DEBUG: Error deleting {old_file}: {e}")
            
            # Delete old verification record
            cursor.execute("DELETE FROM verifications WHERE id = %s", (existing['id'],))
            print(f"DEBUG: Deleted old verification record ID: {existing['id']}")
            conn.commit()
        
        # Convert to JSON string for database storage
        ocr_json = json.dumps(ocr_data)
        print(f"DEBUG: OCR JSON={ocr_json[:200]}...")  # First 200 chars
        
        # Insert into database with OCR results
        print("DEBUG: Inserting into database...")
        cursor = conn.cursor(dictionary=True)
        try:
            # Convert to JSON string for database storage
            ocr_json = json.dumps(ocr_data)
            print(f"DEBUG: OCR JSON (first 200 chars): {ocr_json[:200]}")
            
            print("DEBUG: Executing INSERT...")
            cursor.execute("""
                INSERT INTO verifications (
                    user_id, license_front_image, license_back_image,
                    id_card_type, id_card_image, selfie_image,
                    verification_status, ocr_confidence_score, ocr_extracted_license, 
                    ocr_extracted_expiry, ocr_extracted_name, ocr_raw_data, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s, NOW())
            """, (
                session['user_id'],
                license_front_path, license_back_path,
                id_card_type, id_card_path, selfie_path,
                ocr_data.get('confidence_score', 0),
                ocr_data.get('extracted_license_number'),
                ocr_data.get('extracted_expiry'),
                ocr_data.get('extracted_name'),
                ocr_json
            ))
            print("DEBUG: INSERT successful!")
        
        except Exception as db_error:
            print(f"DEBUG: Database error: {db_error}")
            conn.rollback()
            return jsonify({'success': False, 'message': f'Database error: {str(db_error)}'}), 500
        
        conn.commit()
        
        # Create notification for admin
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, link, created_at)
            VALUES (%s, 'verification', 'New Verification Request', 
                    'A new verification request needs review', '/admin/manage-verifications', NOW())
        """, (1,))  # Admin user ID = 1
        
        conn.commit()
        
        # Prepare response with OCR feedback for user
        print("DEBUG: Preparing success response...")
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
        
        print(f"DEBUG: RETURNING SUCCESS: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"DEBUG: EXCEPTION: {e}")
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        print("DEBUG: ===== EXITING submit_verification() =====")
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
