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
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'pending'
        """, (booking_id, session['user_id']))
        booking_details = database_cursor.fetchone()
        
        # Validate booking exists and is accessible
        if not booking_details:
            logger.warning(f"[PAYMENT] Booking {booking_id} not found or not accessible for user {session['user_id']}")
            flash(PAYMENT_ERROR_MESSAGES['BOOKING_NOT_FOUND'], 'error')
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
    
    # Extract request data
    request_data = request.get_json()
    booking_id = request_data.get('booking_id')
    
    # Validate booking_id is provided
    if not booking_id:
        logger.warning("[PAYMENT] Payment processing failed: Booking ID not provided")
        return jsonify({'error': PAYMENT_ERROR_MESSAGES['BOOKING_ID_REQUIRED']}), 400
    
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
        
        # Create checkout session with PayMongo
        logger.info(f"[PAYMENT] Creating PayMongo checkout session for booking {booking_id}")
        payment_result = gcash_service.create_payment_session(
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
            checkout_url = payment_result['checkout_url']
            
            logger.info(f"[PAYMENT] PayMongo session created: {checkout_session_id}")
            
            # Create pending payment record in database
            database_cursor.execute("""
                INSERT INTO payments (
                    payment_reference, booking_id, user_id, amount, 
                    payment_type, payment_method, payment_status, 
                    transaction_id, payment_details, created_at
                ) VALUES (%s, %s, %s, %s, 'full', 'gcash', 'pending', %s, %s, NOW())
            """, (payment_reference, booking_id, session['user_id'], payment_amount, 
                  checkout_session_id, json.dumps({'checkout_url': checkout_url})))
            database_connection.commit()
            
            logger.info(f"[PAYMENT] Pending payment record created: {payment_reference}")
            
            # Return checkout URL for frontend redirect
            return jsonify({
                'success': True,
                'redirect_url': checkout_url,
                'checkout_session_id': checkout_session_id,
                'message': 'Redirecting to GCash payment page...'
            })
        else:
            error_message = payment_result.get('message', 'Payment processing failed')
            logger.error(f"[PAYMENT] PayMongo session creation failed: {error_message}")
            return jsonify({'error': error_message}), 400
            
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
                
                # Create invoice record
                database_cursor.execute("""
                    INSERT INTO invoices (
                        booking_id, invoice_number, issue_date, due_date,
                        subtotal, total_amount, paid_amount, payment_status, invoice_status
                    )
                    SELECT 
                        id,
                        CONCAT('INV-', DATE_FORMAT(NOW(), '%Y%m%d'), '-', id),
                        CURDATE(),
                        DATE_ADD(CURDATE(), INTERVAL 7 DAY),
                        total_amount, total_amount, total_amount,
                        'completed', 'paid'
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
    """Payment success page - with verification"""
    booking_id = request.args.get('booking_id')
    session_id = request.args.get('session_id')
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            if not session_id and booking_id:
                print(f"⚠️ No session_id in URL, retrieving from database for booking {booking_id}")
                cursor.execute("""
                    SELECT transaction_id, payment_status FROM payments 
                    WHERE booking_id = %s AND payment_status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                """, (booking_id,))
                payment = cursor.fetchone()
                if payment:
                    session_id = payment['transaction_id']
                    print(f"📋 Found session_id from DB: {session_id}")
            
            if session_id:
                print(f"🔍 Verifying payment for session: {session_id}")
                
                if session_id == "{CHECKOUT_SESSION_ID}":
                    print("❌ Invalid session_id - placeholder not replaced")
                    return render_template('success.html', 
                                         session=session, 
                                         booking_id=booking_id,
                                         verified=False,
                                         error="Invalid payment session")
                
                result = gcash_service.retrieve_payment_status(session_id)
                
                print(f"DEBUG: retrieve_payment_status result: {result}")
                
                if result['success'] and result.get('paid'):
                    print(f"✅ Payment verified for session: {session_id}")
                    print(f"✅ Payment verified for session: {session_id}")
                    
                    cursor.execute("""
                        SELECT payment_status FROM payments 
                        WHERE transaction_id = %s
                    """, (session_id,))
                    payment = cursor.fetchone()
                    
                    if payment and payment['payment_status'] == 'pending':
                        cursor.execute("""
                            UPDATE payments 
                            SET payment_status = 'successful', paid_at = NOW()
                            WHERE transaction_id = %s
                        """, (session_id,))
                        
                        if booking_id:
                            cursor.execute("""
                                UPDATE bookings 
                                SET status = 'confirmed'
                                WHERE id = %s
                            """, (booking_id,))
                            conn.commit()
                            print(f"✅ Booking {booking_id} confirmed")
                            
                            cursor.execute("""
                                SELECT b.*, v.model, v.license_plate, vb.name as brand_name,
                                       u.email, u.first_name, u.last_name
                                FROM bookings b
                                JOIN vehicles v ON b.vehicle_id = v.id
                                JOIN vehicle_brands vb ON v.brand_id = vb.id
                                JOIN users u ON b.user_id = u.id
                                WHERE b.id = %s
                            """, (booking_id,))
                            booking = cursor.fetchone()
                            
                            if booking:
                                user = {
                                    'email': booking['email'],
                                    'first_name': booking['first_name'],
                                    'last_name': booking['last_name']
                                }
                                vehicle = {
                                    'model': booking['model'],
                                    'license_plate': booking['license_plate'],
                                    'brand_name': booking['brand_name']
                                }
                                try:
                                    EmailService.send_booking_confirmation(user, booking, vehicle)
                                    print(f"📧 Confirmation email sent to {booking['email']}")
                                except Exception as email_err:
                                    print(f"Email error (non-fatal): {email_err}")
                    
                    return render_template('success.html', 
                                         session=session, 
                                         booking_id=booking_id,
                                         verified=True)
                else:
                    error_msg = result.get('message', 'Payment verification failed')
                    print(f"❌ Payment verification failed: {error_msg}")
                    return render_template('success.html', 
                                         session=session, 
                                         booking_id=booking_id,
                                         verified=False,
                                         error=error_msg)
        except Exception as e:
            print(f"Error in payment verification: {e}")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('success.html', 
                         session=session, 
                         booking_id=booking_id,
                         verified=False)
@payment_bp.route('/failed')
def payment_failed():
    """Payment failed page"""
    return render_template('failed.html', session=session)

@payment_bp.route('/cancel')
def payment_cancel():
    """Payment cancelled by user"""
    booking_id = request.args.get('booking_id')
    flash('Payment was cancelled. Your booking is still pending.', 'warning')
    if booking_id:
        return redirect(url_for('payment_bp.checkout', booking_id=booking_id))
    return redirect(url_for('user_bp.my_bookings'))