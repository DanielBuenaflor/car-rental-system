from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, current_app, json
from functools import wraps
from MyFlaskApp import get_db_connection
from MyFlaskApp.payment.payment_service import *
from MyFlaskApp.payment.invoice_service import InvoiceService
from MyFlaskApp.email.service import EmailService
from dotenv import load_dotenv
from MyFlaskApp.payment.config import *
from MyFlaskApp.payment.gcash_service import GCashService
import requests 

payment_bp = Blueprint('payment_bp', __name__, template_folder='templates', 
                        static_folder='static', static_url_path="/payment_statics")

# Initialize GCash service
gcash_service = GCashService()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('loggedin'):
            flash('Please login to continue', 'error')
            return redirect(url_for('auth_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

@payment_bp.route('/checkout/<int:booking_id>')
@login_required
def checkout(booking_id):
    """Payment checkout page"""
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('user_bp.user_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, 
                   COALESCE(b.discount_amount, 0) as discount_amount,
                   v.model, v.brand_id, vb.name as brand_name, 
                   v.daily_rate, v.security_deposit
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'pending'
        """, (booking_id, session['user_id']))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already processed', 'error')
            return redirect(url_for('user_bp.my_bookings'))
        
        cursor.execute("""
            SELECT * FROM promotions 
            WHERE is_active = 1 
            AND start_date <= CURDATE() AND end_date >= CURDATE()
            AND (usage_limit IS NULL OR used_count < usage_limit)
            ORDER BY discount_value DESC
        """)
        promotions = cursor.fetchall()
        
        return render_template('checkout.html', 
                               booking=booking, 
                               promotions=promotions,
                               session=session)
        
    except Exception as e:
        print(f"Error loading checkout: {e}")
        flash(f'Error loading checkout: {str(e)}', 'error')
        return redirect(url_for('user_bp.my_bookings'))
    finally:
        cursor.close()
        conn.close()

@payment_bp.route('/process-payment', methods=['POST'])
@login_required
def process_payment():
    """Process payment with GCash using Checkout Session"""
    data = request.get_json()
    booking_id = data.get('booking_id')
    
    if not booking_id:
        return jsonify({'error': 'Booking ID required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get booking details
        cursor.execute("""
            SELECT b.*, v.model, v.brand_id, vb.name as brand_name
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE b.id = %s AND b.user_id = %s AND b.status = 'pending'
        """, (booking_id, session['user_id']))
        booking = cursor.fetchone()
        
        if not booking:
            return jsonify({'error': 'Invalid booking'}), 404
        
        amount = float(booking['total_amount'])
        
        # Check if payment already exists
        cursor.execute("""
            SELECT id, payment_status FROM payments 
            WHERE booking_id = %s AND payment_status IN ('pending', 'successful')
        """, (booking_id,))
        existing_payment = cursor.fetchone()
        
        if existing_payment:
            if existing_payment['payment_status'] == 'successful':
                return jsonify({'error': 'Payment already completed'}), 400
            else:
                # Cancel old pending payment and create new one
                cursor.execute("""
                    UPDATE payments 
                    SET payment_status = 'failed'
                    WHERE booking_id = %s AND payment_status = 'pending'
                """, (booking_id,))
                conn.commit()
        
        # Create Checkout Session with PayMongo
        result = gcash_service.create_gcash_payment(
            booking_id=booking_id,
            amount=amount,
            customer_name=session.get('username', 'Customer'),
            customer_email=session.get('email', ''),
            booking_reference=booking['booking_reference']
        )
        
        if result['success']:
            # Generate payment reference
            payment_reference = generate_payment_reference()
            
            # Create pending payment record
            cursor.execute("""
                INSERT INTO payments (
                    payment_reference, booking_id, user_id, amount, 
                    payment_type, payment_method, payment_status, 
                    transaction_id, payment_details, created_at
                ) VALUES (%s, %s, %s, %s, 'full', 'gcash', 'pending', %s, %s, NOW())
            """, (payment_reference, booking_id, session['user_id'], amount, 
                  result['checkout_session_id'], json.dumps({'checkout_url': result['checkout_url']})))
            conn.commit()
            
            # Return checkout URL to frontend
            return jsonify({
                'success': True,
                'redirect_url': result['checkout_url'],
                'checkout_session_id': result['checkout_session_id'],
                'message': 'Redirecting to GCash payment page...'
            })
        else:
            return jsonify({'error': result['message']}), 400
            
    except Exception as e:
        print(f"Error in process_payment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

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
    """Verify payment status after checkout"""
    result = gcash_service.retrieve_payment_status(checkout_session_id)
    
    if result['success'] and result['paid']:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Update payment record
            cursor.execute("""
                UPDATE payments 
                SET payment_status = 'successful', paid_at = NOW()
                WHERE transaction_id = %s
            """, (checkout_session_id,))
            conn.commit()
            
            # Get booking_id
            cursor.execute("SELECT booking_id FROM payments WHERE transaction_id = %s", (checkout_session_id,))
            payment_result = cursor.fetchone()
            
            if payment_result:
                booking_id = payment_result['booking_id']
                
                # Update booking status
                cursor.execute("""
                    UPDATE bookings 
                    SET status = 'confirmed', payment_status = 'completed'
                    WHERE id = %s
                """, (booking_id,))
                conn.commit()
                
                # Create invoice
                cursor.execute("""
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
                conn.commit()
                
                print(f"✅ Payment verified and invoice created for booking {booking_id}")
                return redirect(url_for('payment_bp.payment_success', booking_id=booking_id))
                
        except Exception as e:
            print(f"Error verifying payment: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
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
    
    # If we have a session_id, verify the payment
    if session_id:
        print(f"🔍 Verifying payment for session: {session_id}")
        
        # Verify payment with PayMongo
        result = gcash_service.retrieve_payment_status(session_id)
        
        if result['success'] and result['paid']:
            print(f"✅ Payment verified for session: {session_id}")
            
            # Update payment and booking if not already done
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                try:
                    # Check if already processed
                    cursor.execute("""
                        SELECT payment_status FROM payments 
                        WHERE transaction_id = %s
                    """, (session_id,))
                    payment = cursor.fetchone()
                    
                    if payment and payment['payment_status'] == 'pending':
                        # Update payment
                        cursor.execute("""
                            UPDATE payments 
                            SET payment_status = 'successful', paid_at = NOW()
                            WHERE transaction_id = %s
                        """, (session_id,))
                        
                        # Update booking
                        if booking_id:
                            cursor.execute("""
                                UPDATE bookings 
                                SET status = 'confirmed', payment_status = 'completed'
                                WHERE id = %s
                            """, (booking_id,))
                        
                        conn.commit()
                        print(f"✅ Manual verification updated booking {booking_id}")
                        
                except Exception as e:
                    print(f"Error in manual verification: {e}")
                    conn.rollback()
                finally:
                    cursor.close()
                    conn.close()
            
            return render_template('success.html', 
                                 session=session, 
                                 booking_id=booking_id,
                                 verified=True)
        else:
            # Payment not verified
            return render_template('success.html', 
                                 session=session, 
                                 booking_id=booking_id,
                                 verified=False,
                                 error="Payment verification failed")
    
    # No session_id - show success page without verification (legacy)
    return render_template('success.html', 
                         session=session, 
                         booking_id=booking_id,
                         verified=False)
@payment_bp.route('/failed')
def payment_failed():
    """Payment failed page"""
    return render_template('failed.html', session=session)