"""
Payment Blueprint Module
Handles payment processing, checkout, and verification workflows.
Integrates with GCash/PayMongo for payment processing.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, current_app, json
from functools import wraps
import logging
import requests 

from MyFlaskApp import get_db_connection
from MyFlaskApp.payment.payment_service import *
from MyFlaskApp.payment.invoice_service import InvoiceService
from MyFlaskApp.email.service import EmailService
from MyFlaskApp.payment.config import *
from MyFlaskApp.payment.gcash_service import GCashService
from MyFlaskApp.utils.csrf import generate_csrf_token, validate_csrf_token, clear_csrf_token

# Configure logger for defensive logging
logger = logging.getLogger(__name__)

# ============================================================================
# BLUEPRINT CONFIGURATION
# ============================================================================
payment_bp = Blueprint('payment_bp', __name__, template_folder='templates', 
                        static_folder='static', static_url_path="/payment_statics")

# Initialize GCash service
gcash_service = GCashService()
logger.info("[PAYMENT] GCash service initialized")

# ============================================================================
# DECORATORS
# ============================================================================
def login_required(f):
    """
    Decorator to require user login for payment routes.
    
    Process:
        1. Check if user is logged in via session
        2. If not logged in, flash error and redirect to login page
        3. If logged in, proceed with the route
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('loggedin'):
            logger.warning("[PAYMENT] Unauthorized access attempt - user not logged in")
            flash('Please login to continue', 'error')
            return redirect(url_for('auth_bp.login'))
        logger.debug(f"[PAYMENT] Login verified for user: {session.get('email')}")
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# STANDARDIZED ERROR MESSAGES
# ============================================================================
PAYMENT_ERROR_MESSAGES = {
    'DB_CONNECTION_ERROR': 'Database connection error. Please try again.',
    'BOOKING_NOT_FOUND': 'Booking not found or already processed.',
    'INVALID_BOOKING': 'Invalid booking.',
    'BOOKING_ID_REQUIRED': 'Booking ID is required.',
    'PAYMENT_ALREADY_COMPLETED': 'Payment already completed.',
    'PAYMENT_PROCESSING_ERROR': 'Error processing payment. Please try again.',
    'PAYMENT_VERIFICATION_FAILED': 'Payment verification failed.',
}

@payment_bp.route('/checkout/<int:booking_id>')
@login_required
def checkout(booking_id):
    """
    Payment checkout page - displays booking details and available promotions.
    
    Input:
        booking_id (int): ID of the booking to process payment for
        
    Process:
        1. Verify database connection
        2. Retrieve booking details with vehicle information
        3. Validate booking belongs to current user and is in pending status
        4. Fetch active promotions applicable to the booking
        5. Render checkout page with booking and promotion data
        
    Output:
        Rendered checkout.html template with:
            - booking: Booking details dict
            - promotions: List of active promotions
            - session: Current user session
    """
    logger.info(f"[PAYMENT] Checkout page accessed for booking ID: {booking_id}")
    
    # Generate CSRF token for the form
    generate_csrf_token()
    
    # Establish database connection
    database_connection = get_db_connection()
    if not database_connection:
        logger.error("[PAYMENT] Checkout failed: Database connection error")
        flash(PAYMENT_ERROR_MESSAGES['DB_CONNECTION_ERROR'], 'error')
        return redirect(url_for('user_bp.user_dashboard'))
    
    database_cursor = database_connection.cursor(dictionary=True)
    
    try:
        logger.debug(f"[PAYMENT] Retrieving booking {booking_id} for user {session['user_id']}")
        
        # Retrieve booking details with vehicle and brand information
        database_cursor.execute("""
            SELECT b.*, 
                   COALESCE(b.discount_amount, 0) as discount_amount,
                   v.model, v.brand_id, vb.name as brand_name, 
                   v.daily_rate, v.security_deposit
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s
        """, (booking_id,))
        booking_details = database_cursor.fetchone()
        
        # Validate booking exists and is accessible
        if not booking_details:
            logger.warning(f"[PAYMENT] Booking {booking_id} not found or not accessible for user {session['user_id']}")
            flash(PAYMENT_ERROR_MESSAGES['BOOKING_NOT_FOUND'], 'error')
            return redirect(url_for('user_bp.my_bookings'))
        
        # Check if already paid
        if booking_details['status'] in ['paid', 'confirmed', 'completed']:
            flash('This booking has already been processed.', 'info')
            return redirect(url_for('user_bp.my_bookings'))
        
        logger.info(f"[PAYMENT] Booking {booking_id} retrieved successfully. Total: {booking_details['total_amount']}")
        
        # Fetch active promotions for display
        database_cursor.execute("""
            SELECT * FROM promotions 
            WHERE is_active = 1 
            AND start_date <= CURDATE() AND end_date >= CURDATE()
            AND (usage_limit IS NULL OR used_count < usage_limit)
            ORDER BY discount_value DESC
        """)
        active_promotions = database_cursor.fetchall()
        logger.debug(f"[PAYMENT] Retrieved {len(active_promotions)} active promotions")
        
        logger.info(f"[PAYMENT] Rendering checkout page for booking {booking_id}")
        return render_template('checkout.html', 
                               booking=booking_details, 
                               promotions=active_promotions,
                               session=session)
        
    except Exception as checkout_error:
        error_details = f"[{type(checkout_error).__name__}] {str(checkout_error)}"
        logger.error(f"[PAYMENT] Error loading checkout for booking {booking_id}: {error_details}")
        print(f"[PAYMENT] Error loading checkout: {checkout_error}")
        flash(f'Error loading checkout: {str(checkout_error)}', 'error')
        return redirect(url_for('user_bp.my_bookings'))
    finally:
        database_cursor.close()
        database_connection.close()
        logger.debug(f"[PAYMENT] Database connection closed after checkout page load")

@payment_bp.route('/initiate-payment/<int:booking_id>')
@login_required
def initiate_payment(booking_id):
    """Initiate payment - creates PayMongo session and redirects to checkout"""
    logger.info(f"[PAYMENT] Initiating payment for booking {booking_id}")
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('payment_bp.checkout', booking_id=booking_id))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get booking details
        cursor.execute("""
            SELECT b.*, v.model, vb.name as brand_name
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'pending'
        """, (booking_id, session['user_id']))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Invalid booking', 'error')
            return redirect(url_for('user_bp.my_bookings'))
        
        payment_amount = float(booking['total_amount'])
        
        # Create PayMongo checkout session
        payment_result = gcash_service.create_gcash_payment(
            booking_id=booking_id,
            amount=payment_amount,
            customer_name=session.get('username', 'Customer'),
            customer_email=session.get('email', ''),
            booking_reference=booking['booking_reference']
        )
        
        if not payment_result['success']:
            flash(f'Payment error: {payment_result.get("message", "Failed")}', 'error')
            return redirect(url_for('payment_bp.checkout', booking_id=booking_id))
        
        # Create pending payment record
        payment_reference = generate_payment_reference()
        checkout_session_id = payment_result['checkout_session_id']
        
        cursor.execute("""
            INSERT INTO payments (
                payment_reference, booking_id, user_id, amount,
                payment_type, payment_method, payment_status,
                transaction_id, payment_details, created_at
            ) VALUES (%s, %s, %s, %s, 'full', 'gcash', 'pending', %s, %s, NOW())
        """, (payment_reference, booking_id, session['user_id'], payment_amount,
              checkout_session_id, json.dumps({'checkout_url': payment_result['checkout_url']})))
        conn.commit()
        
        logger.info(f"[PAYMENT] Payment initiated, redirecting to PayMongo")
        
        # Redirect to PayMongo
        return redirect(payment_result['checkout_url'])
        
    except Exception as e:
        logger.error(f"[PAYMENT] Error initiating payment: {e}")
        flash('Payment error', 'error')
        return redirect(url_for('payment_bp.checkout', booking_id=booking_id))
    finally:
        cursor.close()
        conn.close()

@payment_bp.route('/process-payment', methods=['POST'])
@login_required
def process_payment():
    """
    Process payment with GCash using PayMongo Checkout Session.
    
    Input:
        JSON payload:
            - booking_id (int): ID of the booking to pay for
            
    Process:
        1. Extract and validate booking_id from request
        2. Establish database connection
        3. Retrieve booking details and validate ownership/status
        4. Check for existing payments (prevent duplicates)
        5. Create PayMongo checkout session via GCash service
        6. Generate unique payment reference
        7. Store pending payment record in database
        8. Return checkout URL for frontend redirect
        
    Output:
        JSON response (success):
            - success (bool): True
            - redirect_url (str): PayMongo checkout URL
            - checkout_session_id (str): Session ID for verification
            - message (str): Status message
            
        JSON response (error):
            - error (str): Error message
    """
    logger.info("[PAYMENT] Payment processing initiated")
    
    # Extract request data - handle both JSON and form POST
    if request.is_json:
        request_data = request.get_json()
        booking_id = request_data.get('booking_id')
        csrf_token = request_data.get('csrf_token')
    else:
        booking_id = request.form.get('booking_id')
        csrf_token = request.form.get('csrf_token')
    
    # Validate CSRF token
    valid, error = validate_csrf_token(csrf_token)
    if not valid:
        logger.warning(f"[PAYMENT] CSRF validation failed: {error}")
        return '<script>alert("Security error. Please refresh and try again."); window.location.href="/user/dashboard";</script>', 400
    
    # Validate booking_id is provided
    if not booking_id:
        logger.warning("[PAYMENT] Payment processing failed: Booking ID not provided")
        return jsonify({'error': PAYMENT_ERROR_MESSAGES['BOOKING_ID_REQUIRED']}), 400
    
    # Convert to int if string
    try:
        booking_id = int(booking_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid booking ID'}), 400
    
    logger.info(f"[PAYMENT] Processing payment for booking ID: {booking_id}")
    
    # Establish database connection
    database_connection = get_db_connection()
    if not database_connection:
        logger.error("[PAYMENT] Payment processing failed: Database connection error")
        return jsonify({'error': PAYMENT_ERROR_MESSAGES['DB_CONNECTION_ERROR']}), 500
    
    database_cursor = database_connection.cursor(dictionary=True)
    
    try:
        logger.debug(f"[PAYMENT] Retrieving booking {booking_id} for user {session['user_id']}")
        
        # Retrieve booking details with vehicle information
        database_cursor.execute("""
            SELECT b.*, v.model, v.brand_id, vb.name as brand_name
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'pending'
        """, (booking_id, session['user_id']))
        booking_details = database_cursor.fetchone()
        
        # Validate booking exists and is pending
        if not booking_details:
            logger.warning(f"[PAYMENT] Invalid booking {booking_id} for user {session['user_id']}")
            return jsonify({'error': PAYMENT_ERROR_MESSAGES['INVALID_BOOKING']}), 404
        
        payment_amount = float(booking_details['total_amount'])
        logger.info(f"[PAYMENT] Booking {booking_id} validated. Amount: {payment_amount}")
        
        # Check for existing payments to prevent duplicates
        database_cursor.execute("""
            SELECT id, payment_status FROM payments 
            WHERE booking_id = %s AND payment_status IN ('pending', 'successful')
        """, (booking_id,))
        existing_payment = database_cursor.fetchone()
        
        if existing_payment:
            if existing_payment['payment_status'] == 'successful':
                logger.warning(f"[PAYMENT] Duplicate payment attempt for booking {booking_id}")
                return jsonify({'error': PAYMENT_ERROR_MESSAGES['PAYMENT_ALREADY_COMPLETED']}), 400
            else:
                # Cancel old pending payment
                logger.info(f"[PAYMENT] Canceling old pending payment for booking {booking_id}")
                database_cursor.execute("""
                    UPDATE payments 
                    SET payment_status = 'failed'
                    WHERE booking_id = %s AND payment_status = 'pending'
                """, (booking_id,))
                database_connection.commit()
                logger.debug(f"[PAYMENT] Old pending payment marked as failed")
        
        # Create checkout session with PayMongo/GCash
        logger.info(f"[PAYMENT] Creating PayMongo checkout session for booking {booking_id}")
        payment_result = gcash_service.create_gcash_payment(
            booking_id=booking_id,
            amount=payment_amount,
            customer_name=session.get('username', 'Customer'),
            customer_email=session.get('email', ''),
            booking_reference=booking_details['booking_reference']
        )
        
        if payment_result['success']:
            # Generate unique payment reference
            payment_reference = generate_payment_reference()
            checkout_session_id = payment_result['checkout_session_id']
            
            logger.info(f"[PAYMENT] PayMongo session created: {checkout_session_id}")
            
            # Create pending payment record in database
            database_cursor.execute("""
                INSERT INTO payments (
                    payment_reference, booking_id, user_id, amount, 
                    payment_type, payment_method, payment_status, 
                    transaction_id, payment_details, created_at
                ) VALUES (%s, %s, %s, %s, 'full', 'gcash', 'pending', %s, %s, NOW())
            """, (payment_reference, booking_id, session['user_id'], payment_amount, 
                  checkout_session_id, json.dumps({'checkout_url': payment_result['checkout_url']})))
            database_connection.commit()
            
            logger.info(f"[PAYMENT] Pending payment record created: {payment_reference}")
            
            # Redirect to PayMongo checkout page
            checkout_url = payment_result['checkout_url']
            print(f"🔍 DEBUG: Redirecting to PayMongo: {checkout_url}")
            return redirect(checkout_url)
        else:
            error_message = payment_result.get('message', 'Payment processing failed')
            logger.error(f"[PAYMENT] PayMongo session creation failed: {error_message}")
            return f'''<!DOCTYPE html>
<html><head><script>alert("Payment error: {error_message}"); window.location.href = "{url_for('payment_bp.checkout', booking_id=booking_id)}";</script></head></html>''', 400
            
    except Exception as processing_error:
        error_details = f"[{type(processing_error).__name__}] {str(processing_error)}"
        logger.error(f"[PAYMENT] Error in process_payment: {error_details}")
        print(f"[PAYMENT] Error in process_payment: {processing_error}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': PAYMENT_ERROR_MESSAGES['PAYMENT_PROCESSING_ERROR']}), 500
    finally:
        database_cursor.close()
        database_connection.close()
        logger.debug("[PAYMENT] Database connection closed after payment processing")

@payment_bp.route('/apply-promo', methods=['POST'])
@login_required
def apply_promo():
    """Apply promotion code to booking"""
    data = request.get_json()
    booking_id = data.get('booking_id')
    promo_code = data.get('promo_code')
    
    result = apply_promotion(booking_id, promo_code)
    
    if result['success']:
        return jsonify({
            'success': True,
            'discount': result['discount'],
            'original_amount': result['original_amount'],
            'final_amount': result['final_amount'],
            'promotion_name': result['promotion_name']
        })
    else:
        return jsonify({
            'success': False,
            'message': result['message']
        }), 400

@payment_bp.route('/verify-payment/<checkout_session_id>', methods=['GET'])
@login_required
def verify_payment(checkout_session_id):
    """
    Verify payment status after checkout and update records.
    
    Input:
        checkout_session_id (str): PayMongo checkout session ID
        
    Process:
        1. Retrieve payment status from PayMongo/GCash service
        2. If payment successful:
            a. Update payment record status to 'successful'
            b. Get associated booking ID
            c. Update booking status to 'confirmed'
            d. Create invoice record
        3. Redirect to success or failed page
        
    Output:
        Redirect to payment_success or payment_failed route
    """
    logger.info(f"[PAYMENT] Verifying payment for session: {checkout_session_id}")
    
    # Retrieve payment status from PayMongo
    verification_result = gcash_service.retrieve_payment_status(checkout_session_id)
    
    if verification_result['success'] and verification_result['paid']:
        logger.info(f"[PAYMENT] Payment verified as successful for session: {checkout_session_id}")
        
        # Establish database connection
        database_connection = get_db_connection()
        database_cursor = database_connection.cursor(dictionary=True)
        
        try:
            # Update payment record to successful
            database_cursor.execute("""
                UPDATE payments 
                SET payment_status = 'successful', paid_at = NOW()
                WHERE transaction_id = %s
            """, (checkout_session_id,))
            database_connection.commit()
            logger.debug(f"[PAYMENT] Payment record updated to successful for session: {checkout_session_id}")
            
            # Retrieve associated booking ID
            database_cursor.execute(
                "SELECT booking_id FROM payments WHERE transaction_id = %s", 
                (checkout_session_id,)
            )
            payment_record = database_cursor.fetchone()
            
            if payment_record:
                booking_id = payment_record['booking_id']
                logger.info(f"[PAYMENT] Updating booking {booking_id} to confirmed status")
                
                # Update booking status to confirmed
                database_cursor.execute("""
                    UPDATE bookings 
                    SET status = 'confirmed', payment_status = 'completed'
                    WHERE id = %s
                """, (booking_id,))
                database_connection.commit()
                logger.info(f"[PAYMENT] Booking {booking_id} status updated to confirmed")
                
                # Create invoice record (bookings.total_amount -> invoices.amount per DB schema)
                database_cursor.execute("""
                    INSERT INTO invoices (
                        booking_id, user_id, invoice_number, invoice_date, due_date,
                        subtotal, tax_amount, discount_amount, amount, balance_due, status
                    )
                    SELECT 
                        id, user_id,
                        CONCAT('INV-', DATE_FORMAT(NOW(), '%Y%m%d'), '-', id),
                        CURDATE(),
                        DATE_ADD(CURDATE(), INTERVAL 7 DAY),
                        total_amount, tax_amount, discount_amount, total_amount, total_amount,
                        'paid'
                    FROM bookings 
                    WHERE id = %s
                """, (booking_id,))
                database_connection.commit()
                
                logger.info(f"[PAYMENT] Invoice created for booking {booking_id}")
                print(f"[PAYMENT] Payment verified and invoice created for booking {booking_id}")
                
                return redirect(url_for('payment_bp.payment_success', booking_id=booking_id))
            else:
                logger.error(f"[PAYMENT] No booking found for session: {checkout_session_id}")
                
        except Exception as verification_error:
            error_details = f"[{type(verification_error).__name__}] {str(verification_error)}"
            logger.error(f"[PAYMENT] Error verifying payment: {error_details}")
            print(f"[PAYMENT] Error verifying payment: {verification_error}")
            database_connection.rollback()
        finally:
            database_cursor.close()
            database_connection.close()
            logger.debug("[PAYMENT] Database connection closed after payment verification")
    else:
        logger.warning(f"[PAYMENT] Payment verification failed for session: {checkout_session_id}")
    
    return redirect(url_for('payment_bp.payment_failed'))

# Keep old route for backward compatibility (but it will redirect)
@payment_bp.route('/verify-gcash-payment/<payment_intent_id>', methods=['GET'])
@login_required
def verify_gcash_payment(payment_intent_id):
    """Legacy verify endpoint - redirects to new method if possible"""
    # Try to get checkout session from payments table
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT transaction_id FROM payments WHERE transaction_id = %s", (payment_intent_id,))
        result = cursor.fetchone()
        if result:
            # If it's actually a checkout session ID
            return redirect(url_for('payment_bp.verify_payment', checkout_session_id=payment_intent_id))
    except:
        pass
    
    flash('Payment verification method not found', 'error')
    return redirect(url_for('payment_bp.payment_failed'))


@payment_bp.route('/success')
def payment_success():
    """Payment success page - trust database first"""
    booking_id = request.args.get('booking_id')
    session_id = request.args.get('session_id')
    
    print(f"[SUCCESS] booking_id={booking_id}, session_id={session_id}")

    # STEP 1: GUARANTEE database is checked FIRST - even if session_id is the placeholder
    if booking_id:
        print(f"[SUCCESS] Checking database for booking {booking_id}")
        
        # CLOSE any existing connection first to get fresh data
        import gc
        gc.collect()
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT status FROM bookings WHERE id = %s", (booking_id,))
                booking = cursor.fetchone()
                print(f"[SUCCESS] Booking status from DB: {booking}")
                
                # STEP 2: CHECK THE STATUS IMMEDIATELY
                if booking and booking['status'] == 'confirmed':
                    print("✅ Database already confirmed. Showing success page.")
                    
                    # --- ADD THIS NEW QUERY HERE ---
                    cursor.execute("SELECT id FROM invoices WHERE booking_id = %s", (booking_id,))
                    invoice = cursor.fetchone()
                    invoice_id = invoice['id'] if invoice else None
                    # -------------------------------

                    cursor.execute("SELECT payment_status FROM payments WHERE booking_id = %s ORDER BY created_at DESC LIMIT 1", (booking_id,))
                    payment = cursor.fetchone()
                    already = payment and payment['payment_status'] == 'successful'
                    
                    # Pass 'invoice_id' to the template below
                    return render_template('success.html', 
                                         session=session, 
                                         booking_id=booking_id, 
                                         invoice_id=invoice_id, # Added this
                                         verified=True, 
                                         already_confirmed=already)
            except Exception:
                pass
            finally:
                cursor.close()
                conn.close()

    # STEP 3: Only if no booking_id provided, try to find it from pending payments
    if not booking_id:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT booking_id FROM payments WHERE transaction_id LIKE 'cs_%%' AND payment_status = 'pending' ORDER BY created_at DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    booking_id = row['booking_id']
                    if booking_id:
                        cursor.execute("SELECT status FROM bookings WHERE id = %s", (booking_id,))
                        booking = cursor.fetchone()
                        if booking and booking['status'] == 'confirmed':
                            print("✅ Database already confirmed. Showing success page.")
                            cursor.execute("SELECT id FROM invoices WHERE booking_id = %s", (booking_id,))
                            inv = cursor.fetchone()
                            invoice_id = inv['id'] if inv else None
                            return render_template('success.html', session=session, booking_id=booking_id, invoice_id=invoice_id, verified=True, already_confirmed=True)
            except Exception:
                pass
            finally:
                cursor.close()
                conn.close()

    # STEP 4: Verify payment using booking_id (user returned from PayMongo)
    # Get the pending payment for this booking to find the transaction_id
    payment_verified = False
    if booking_id:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("""
                    SELECT transaction_id, payment_status 
                    FROM payments 
                    WHERE booking_id = %s 
                    ORDER BY created_at DESC LIMIT 1
                """, (booking_id,))
                payment = cursor.fetchone()
                
                if payment and payment['payment_status'] == 'pending' and payment['transaction_id']:
                    session_id = payment['transaction_id']
                    print(f"🔍 Found pending payment for booking {booking_id}, checking session: {session_id}")
                    
                    # Use payment_intent status check for more accurate results
                    result = gcash_service.get_payment_intent_status(session_id)
                    print(f"[VERIFY] PayMongo payment_intent result: {result}")
                    
                    if result['success'] and result['paid']:
                        print(f"✅ Payment verified via payment_intent: {result.get('payment_intent_id')}, status: {result.get('status')}")
                        
                        # Update payment status
                        cursor.execute("UPDATE payments SET payment_status = 'successful', paid_at = NOW() WHERE transaction_id = %s", (session_id,))
                        
                        # Update booking status
                        cursor.execute("UPDATE bookings SET status = 'confirmed' WHERE id = %s", (booking_id,))
                        
                        # Notify ADMIN about confirmed booking
                        try:
                            cursor.execute("SELECT id FROM users WHERE role = 'admin'")
                            admin_users = cursor.fetchall()
                            
                            if admin_users:
                                # Get booking reference
                                cursor.execute("SELECT booking_reference FROM bookings WHERE id = %s", (booking_id,))
                                booking_ref = cursor.fetchone()
                                ref = booking_ref[0] if booking_ref else 'N/A'
                                
                                notification_title = "Booking Confirmed"
                                notification_message = f"Booking {ref} has been confirmed (payment received)"
                                notification_link = "/admin/manage-bookings"
                                
                                for admin in admin_users:
                                    cursor.execute("""
                                        INSERT INTO notifications (user_id, title, message, type, link, created_at)
                                        VALUES (%s, %s, %s, 'system', %s, NOW())
                                    """, (admin[0], notification_title, notification_message, notification_link))
                                
                                conn.commit()
                                print(f"DEBUG: Notified {len(admin_users)} admin(s) about booking confirmation")
                        except Exception as notify_err:
                            print(f"DEBUG: Error notifying admins about confirmation: {notify_err}")
                        
                        conn.commit()
                        print(f"✅ Payment verified and booking {booking_id} confirmed")
                        payment_verified = True
                        
                        # Create invoice for this booking
                        try:
                            invoice_result = InvoiceService.create_invoice_for_booking(booking_id)
                            if invoice_result['success']:
                                invoice_id = invoice_result.get('invoice_id')
                                InvoiceService.update_payment_status(invoice_id, 'paid')
                                print(f"✅ Invoice {invoice_id} created and marked as paid for booking {booking_id}")
                            else:
                                print(f"⚠️ Failed to create invoice: {invoice_result.get('message')}")
                        except Exception as e:
                            print(f"⚠️ Error creating invoice: {e}")
                        
                        # Get invoice (now should exist)
                        cursor.execute("SELECT id FROM invoices WHERE booking_id = %s", (booking_id,))
                        inv = cursor.fetchone()
                        invoice_id = inv['id'] if inv else None
                        return render_template('success.html', session=session, booking_id=booking_id, invoice_id=invoice_id, verified=True)
                    else:
                        payment_status = result.get('status', 'unknown')
                        print(f"⚠️ Payment not yet completed. Payment intent status: {payment_status}")
                        
                        # Check if booking is already confirmed (e.g., via webhook)
                        cursor.execute("SELECT status FROM bookings WHERE id = %s", (booking_id,))
                        booking_status = cursor.fetchone()
                        if booking_status and booking_status['status'] == 'confirmed':
                            cursor.execute("SELECT id FROM invoices WHERE booking_id = %s", (booking_id,))
                            inv = cursor.fetchone()
                            invoice_id = inv['id'] if inv else None
                            return render_template('success.html', session=session, booking_id=booking_id, invoice_id=invoice_id, verified=True, already_confirmed=True)
                        
                        flash(f'Payment is pending ({payment_status}). Please complete the payment on GCash/Maya.', 'warning')
                        return redirect(url_for('payment_bp.checkout', booking_id=booking_id))
                elif payment and payment['payment_status'] == 'successful':
                    # Payment already successful
                    cursor.execute("SELECT status FROM bookings WHERE id = %s", (booking_id,))
                    booking_status = cursor.fetchone()
                    cursor.execute("SELECT id FROM invoices WHERE booking_id = %s", (booking_id,))
                    inv = cursor.fetchone()
                    invoice_id = inv['id'] if inv else None
                    return render_template('success.html', session=session, booking_id=booking_id, invoice_id=invoice_id, verified=True, already_confirmed=True)
            finally:
                cursor.close()
                conn.close()
    
    # If we get here, something went wrong
    flash('Payment was not completed. Please try again.', 'error')
    if booking_id:
        return redirect(url_for('payment_bp.checkout', booking_id=booking_id))
    return redirect(url_for('user_bp.my_bookings'))


@payment_bp.route('/webhook', methods=['POST'])
def webhook():
    """PayMongo webhook endpoint at /payment/webhook"""
    print(f"📨 WEBHOOK RECEIVED")
    print(f"📨 Headers: {dict(request.headers)}")
    print(f"📨 Raw Body: {request.get_data(as_text=True)[:500]}")
    
    from MyFlaskApp.payment.webhooks import paymongo_webhook_handler
    result = paymongo_webhook_handler()
    print(f"📨 Webhook handler result: {result}")
    return result


@payment_bp.route('/failed')
def payment_failed():
    """Payment failed page"""
    return render_template('failed.html', session=session)