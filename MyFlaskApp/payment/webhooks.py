# webhooks.py
from flask import Blueprint, request, jsonify, session, current_app,  url_for, redirect
from MyFlaskApp import get_db_connection
import json
import hmac
import hashlib
import os, requests
from datetime import datetime

# Create blueprint
webhook_bp = Blueprint('webhook_bp', __name__)


def verify_paymongo_signature(payload, signature):
    """
    Verify PayMongo webhook signature for security
    Optional but recommended for production
    """
    webhook_secret = os.environ.get('PAYMONGO_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        # If no webhook secret is set, skip verification (for development)
        return True
    
    try:
        computed_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


def paymongo_webhook_handler():
    """
    Handle PayMongo webhook events
    """
    payload = request.get_data()
    print(f"📨 Webhook received - checking event type...")
    
    # Signature verification disabled for testing
    # signature = request.headers.get('PayMongo-Signature', '')
    # if not verify_paymongo_signature(payload, signature):
    #     print("❌ Invalid webhook signature - rejecting request")
    #     return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400
        
        # Get event type
        event_data = data.get('data', {})
        event_attributes = event_data.get('attributes', {})
        event_type = event_attributes.get('type')
        
        print(f"📨 Webhook received: {event_type}")
        
        # Handle different event types
        if event_type == 'checkout_session.payment.paid':
            # Add idempotency check to prevent double processing
            checkout_session_id = event_data.get('id')
            
            # Check if already processed
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        SELECT id FROM payments 
                        WHERE transaction_id = %s AND payment_status = 'successful'
                    """, (checkout_session_id,))
                    if cursor.fetchone():
                        print(f"⚠️ Webhook already processed for session: {checkout_session_id}")
                        return jsonify({'success': True, 'message': 'Already processed'}), 200
                finally:
                    cursor.close()
                    conn.close()
            
            return handle_checkout_session_paid(event_data)
        
        elif event_type == 'checkout_session.payment.failed':
            return handle_checkout_session_failed(event_data)
        
        elif event_type == 'source.chargeable':
            return handle_source_chargeable(event_data)
        
        elif event_type == 'payment.paid':
            return handle_payment_paid(event_data)
        
        elif event_type == 'payment.failed':
            return handle_payment_failed(event_data)
        
        else:
            print(f"⚠️ Unhandled event type: {event_type}")
            return jsonify({'success': True, 'message': 'Event received but not handled'}), 200
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON payload: {e}")
        return jsonify({'success': False, 'message': 'Invalid JSON'}), 400
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

def handle_checkout_session_paid(event_data):
    """Handle successful checkout session payment"""
    try:
        checkout_session_id = event_data.get('id')
        attributes = event_data.get('attributes', {})
        event_type = attributes.get('type')

        print(f"💰 Payment successful for checkout session: {checkout_session_id}")

        booking_id = None

        if event_type == 'checkout_session.payment.paid':
            nested_data = attributes.get('data', {})
            nested_attrs = nested_data.get('attributes', {})

            direct_metadata = nested_attrs.get('metadata', {})
            booking_id = direct_metadata.get('booking_id')

            if not booking_id:
                payment_intent = nested_attrs.get('payment_intent', {})
                pi_attrs = payment_intent.get('attributes', {})
                pi_metadata = pi_attrs.get('metadata', {})
                booking_id = pi_metadata.get('booking_id')

        if not booking_id:
            print("❌ No booking_id in metadata")
            return jsonify({'success': False, 'message': 'No booking_id in metadata'}), 400

        print(f"📝 Booking ID: {booking_id}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return jsonify({'success': False, 'message': 'Database error'}), 500
        
        cursor = conn.cursor()
        
        try:
            # 1. Update payment record
            cursor.execute("""
                UPDATE payments 
                SET payment_status = 'successful', 
                    paid_at = NOW()
                WHERE transaction_id = %s AND payment_status = 'pending'
            """, (checkout_session_id,))
            
            if cursor.rowcount == 0:
                print(f"⚠️ No pending payment found for session: {checkout_session_id}")
                # Try to get booking and create payment record
                cursor.execute("""
                    SELECT id, user_id, total_amount FROM bookings WHERE id = %s
                """, (booking_id,))
                booking = cursor.fetchone()
                
                if booking:
                    from MyFlaskApp.payment.payment_service import generate_payment_reference
                    payment_reference = generate_payment_reference()
                    
                    cursor.execute("""
                        INSERT INTO payments (
                            payment_reference, booking_id, user_id, amount,
                            payment_type, payment_method, payment_status,
                            transaction_id, paid_at, created_at
                        ) VALUES (%s, %s, %s, %s, 'full', 'gcash', 'successful', %s, NOW(), NOW())
                    """, (payment_reference, booking_id, booking[1], booking[2], checkout_session_id))
            
            # 2. Update booking status
            cursor.execute("""
                UPDATE bookings 
                SET status = 'confirmed'
                WHERE id = %s AND status = 'pending'
            """, (booking_id,))
            
            conn.commit()
            print(f"✅ Booking {booking_id} updated to confirmed and COMMITTED")
            
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
            
            # Get user and booking details for notification
            cursor.execute("""
                SELECT b.user_id, b.booking_reference, b.total_amount,
                       v.brand_name, v.model
                FROM bookings b
                JOIN vehicles v ON b.vehicle_id = v.id
                WHERE b.id = %s
            """, (booking_id,))
            booking_details = cursor.fetchone()
            
            # Send in-app notification for payment success
            if booking_details:
                try:
                    cursor.execute("""
                        INSERT INTO notifications (user_id, title, message, type, link, created_at)
                        VALUES (%s, 'Payment Confirmed', %s, 'payment_confirmation', %s, NOW())
                    """, (
                        booking_details[0],
                        f'Payment of ₱{booking_details[2]:.2f} confirmed for {booking_details[3]} {booking_details[4]}. Booking {booking_details[1]} is now confirmed!',
                        '/user/my-bookings'
                    ))
                    conn.commit()
                except Exception as e:
                    print(f"Notification error: {e}")
            
            # 3. CREATE INVOICE
            from MyFlaskApp.payment.invoice_service import InvoiceService
            
            invoice_result = InvoiceService.create_invoice_for_booking(booking_id)
            
            if invoice_result['success']:
                invoice_id = invoice_result['invoice_id']
                InvoiceService.update_payment_status(invoice_id, 'paid')
                print(f"✅ Invoice {invoice_id} created with status PAID")
                
                # Send confirmation email
                try:
                    # Get user and booking details
                    cursor.execute("""
                        SELECT u.email, u.first_name, b.id as booking_id, 
                               b.booking_reference, b.start_date, b.end_date,
                               v.model, vb.name as brand_name
                        FROM bookings b
                        JOIN users u ON b.user_id = u.id
                        JOIN vehicles v ON b.vehicle_id = v.id
                        JOIN vehicle_brands vb ON v.brand_id = vb.id
                        WHERE b.id = %s
                    """, (booking_id,))
                    result = cursor.fetchone()
                    
                    if result:
                        user = {'email': result[0], 'first_name': result[1]}
                        booking = {
                            'booking_reference': result[3],
                            'start_date': result[4],
                            'end_date': result[5]
                        }
                        vehicle = {'brand_name': result[7], 'model': result[6]}
                        
                        from MyFlaskApp.email.service import EmailService
                        email_sent = EmailService.send_booking_confirmation(user, booking, vehicle)
                        if email_sent:
                            print(f"📧 Booking confirmation email sent to {user['email']}")
                        else:
                            print(f"⚠️ Failed to send email to {user['email']}")
                except Exception as e:
                    print(f"Email error: {e}")
                    import traceback
                    traceback.print_exc()
            
            conn.commit()
            print(f"✅ Successfully processed payment for booking {booking_id}")
            
            return jsonify({'success': True, 'message': 'Payment processed successfully'}), 200
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Database error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"❌ Error handling checkout session paid: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


def handle_checkout_session_failed(event_data):
    """Handle failed checkout session payment"""
    try:
        checkout_session_id = event_data.get('id')
        attributes = event_data.get('attributes', {})
        metadata = attributes.get('metadata', {})
        booking_id = metadata.get('booking_id')
        
        print(f"❌ Payment failed for session: {checkout_session_id}")
        
        if booking_id:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                try:
                    # Update payment status
                    cursor.execute("""
                        UPDATE payments 
                        SET payment_status = 'failed'
                        WHERE transaction_id = %s AND payment_status = 'pending'
                    """, (checkout_session_id,))
                     
                    # Update booking status back to pending (so user can retry)
                    cursor.execute("""
                        UPDATE bookings 
                        SET status = 'pending'
                        WHERE id = %s AND status = 'pending'
                    """, (booking_id,))
                    
                    # Get user_id and booking details for notification
                    cursor.execute("""
                        SELECT b.user_id, b.booking_reference, b.total_amount
                        FROM bookings b
                        WHERE b.id = %s
                    """, (booking_id,))
                    booking_info = cursor.fetchone()
                     
                    # Send notification for failed payment
                    if booking_info:
                        cursor.execute("""
                            INSERT INTO notifications (user_id, title, message, type, link, created_at)
                            VALUES (%s, 'Payment Failed', %s, 'payment_confirmation', '/user/my-bookings', NOW())
                        """, (
                            booking_info[0],
                            f'Payment for booking {booking_info[1]} failed. Amount: ₱{booking_info[2]:.2f}. Please try again.'
                        ))
                    
                    conn.commit()
                    print(f"✅ Updated failed payment for booking {booking_id}")
                except Exception as e:
                    print(f"Error updating failed payment: {e}")
                    conn.rollback()
                finally:
                    cursor.close()
                    conn.close()
        
        return jsonify({'success': True, 'message': 'Payment failure recorded'}), 200
        
    except Exception as e:
        print(f"Error handling checkout session failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


def handle_source_chargeable(event_data):
    """Handle source.chargeable event (legacy)"""
    try:
        source_id = event_data.get('id')
        attributes = event_data.get('attributes', {})
        metadata = attributes.get('metadata', {})
        booking_id = metadata.get('booking_id')
        
        print(f"💰 Source chargeable: {source_id}")
        
        # Get source details to create payment
        from MyFlaskApp.payment.gcash_service import GCashService
        gcash_service = GCashService()
        
        # Retrieve source
        response = requests.get(
            f"https://api.paymongo.com/v1/sources/{source_id}",
            headers=gcash_service.get_auth_header()
        )
        
        if response.status_code == 200:
            source_data = response.json()
            amount = source_data['data']['attributes']['amount'] / 100
            
            # Create payment
            payment_payload = {
                "data": {
                    "attributes": {
                        "amount": int(amount * 100),
                        "currency": "PHP",
                        "source": {
                            "id": source_id,
                            "type": "source"
                        },
                        "description": f"Booking #{booking_id}"
                    }
                }
            }
            
            payment_response = requests.post(
                "https://api.paymongo.com/v1/payments",
                headers=gcash_service.get_auth_header(),
                json=payment_payload
            )
            
            if payment_response.status_code == 200:
                print(f"✅ Payment created from source {source_id}")
                
                # Update booking and create invoice
                if booking_id:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        try:
                            cursor.execute("""
                                        UPDATE bookings 
                                        SET status = 'confirmed'
                                        WHERE id = %s
                                    """, (booking_id,))
                            conn.commit()
            
                            # Notify ADMIN about confirmed booking
                            try:
                                cursor.execute("SELECT id FROM users WHERE role = 'admin'")
                                admin_users = cursor.fetchall()
            
                                if admin_users:
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
            
                        except Exception as e:
                            print(f"Error updating booking: {e}")
                        finally:
                            cursor.close()
                            conn.close()
            
            return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Error handling source chargeable: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


def handle_payment_paid(event_data):
    """Handle payment.paid event"""
    try:
        payment_id = event_data.get('id')
        attributes = event_data.get('attributes', {})
        metadata = attributes.get('metadata', {})
        booking_id = metadata.get('booking_id')
        
        print(f"💰 Payment paid: {payment_id}")
        
        if booking_id:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                try:
                    # Update booking status
                    cursor.execute("""
                        UPDATE bookings 
                        SET status = 'confirmed'
                        WHERE id = %s
                    """, (booking_id,))
                    conn.commit()
                    
                    # Notify ADMIN about confirmed booking
                    try:
                        cursor.execute("SELECT id FROM users WHERE role = 'admin'")
                        admin_users = cursor.fetchall()
                        
                        if admin_users:
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
                    
                    print(f"✅ Booking {booking_id} confirmed")
                except Exception as e:
                    print(f"Error updating booking: {e}")
                finally:
                    cursor.close()
                    conn.close()
            
            return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Error handling payment paid: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


def handle_payment_failed(event_data):
    """Handle payment.failed event"""
    try:
        payment_id = event_data.get('id')
        print(f"❌ Payment failed: {payment_id}")
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error handling payment failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# Test endpoint to verify webhook is working
@webhook_bp.route('/test', methods=['GET'])
def test_webhook():
    """Test endpoint to verify webhook is accessible"""
    return jsonify({
        'success': True,
        'message': 'Webhook endpoint is working',
        'endpoints': {
            'paymongo': '/webhook/paymongo',
            'test': '/webhook/test'
        }
    }), 200


# For optional local webhook testing
@webhook_bp.route('/simulate-payment', methods=['POST'])
def simulate_payment():
    """Simulate a successful payment for testing (development only)"""
    data = request.get_json()
    booking_id = data.get('booking_id')
    
    if not booking_id:
        return jsonify({'success': False, 'message': 'booking_id required'}), 400
    
    print(f"🧪 Simulating payment for booking {booking_id}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        # Get booking info to get user_id and amounts (bookings uses total_amount, invoices uses amount)
        cursor.execute("SELECT user_id, total_amount FROM bookings WHERE id = %s", (booking_id,))
        booking = cursor.fetchone()
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found'}), 404
        user_id, invoice_amount = booking
        
        # Update booking status
        cursor.execute("""
            UPDATE bookings 
            SET status = 'confirmed'
            WHERE id = %s
        """, (booking_id,))
        
        # Create invoice with all required columns (using 'amount' per DB schema)
        cursor.execute("""
            INSERT INTO invoices (booking_id, user_id, invoice_number, invoice_date, due_date, subtotal, tax_amount, discount_amount, amount, balance_due, status)
            VALUES (%s, %s, %s, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 7 DAY), %s, 0, 0, %s, %s, 'paid')
        """, (booking_id, user_id, f"INV-{datetime.now().strftime('%Y%m%d')}-{booking_id}", invoice_amount, invoice_amount, invoice_amount))
        
        conn.commit()
        return jsonify({'success': True, 'message': f'Payment simulated for booking {booking_id}'}), 200
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
