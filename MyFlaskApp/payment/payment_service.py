import random
import string
from datetime import datetime
from MyFlaskApp import get_db_connection

def generate_payment_reference():
    """Generate unique payment reference"""
    prefix = 'PAY'
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_str}"

def process_booking_payment(booking_id, user_id, amount, payment_method='credit_card'):
    """
    Process payment for a booking
    Creates a PENDING payment record (not successful yet)
    """
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'message': 'Database error'}
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get booking details
        cursor.execute("""
            SELECT * FROM bookings WHERE id = %s AND user_id = %s
        """, (booking_id, user_id))
        booking = cursor.fetchone()
        
        if not booking:
            return {'success': False, 'message': 'Booking not found'}
        
        # Generate payment reference
        payment_reference = generate_payment_reference()
        
        # Create payment record with PENDING status (NOT successful)
        # The user hasn't paid yet - they will be redirected to PayMongo
        cursor.execute("""
            INSERT INTO payments (
                payment_reference, booking_id, user_id, amount, 
                payment_type, payment_method, payment_status, created_at
            ) VALUES (%s, %s, %s, %s, 'full', %s, 'pending', NOW())
        """, (payment_reference, booking_id, user_id, amount, payment_method))
        
        payment_id = cursor.lastrowid
        conn.commit()
        
        return {
            'success': True,
            'payment_id': payment_id,
            'payment_reference': payment_reference,
            'booking_reference': booking['booking_reference']
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        cursor.close()
        conn.close()

def update_payment_status(payment_reference, status, transaction_id=None):
    """Update payment status after successful payment"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE payments 
            SET payment_status = %s, transaction_id = %s, paid_at = NOW()
            WHERE payment_reference = %s
        """, (status, transaction_id, payment_reference))
        
        conn.commit()
        
        # Get booking_id to update booking status
        cursor.execute("SELECT booking_id FROM payments WHERE payment_reference = %s", (payment_reference,))
        result = cursor.fetchone()
        if result:
            booking_id = result[0]
            cursor.execute("""
                UPDATE bookings 
                SET status = 'confirmed' 
                WHERE id = %s AND status = 'pending'
            """, (booking_id,))
            conn.commit()
        
        return True
    except Exception as e:
        print(f"Error updating payment status: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def apply_promotion(booking_id, promo_code):
    """Apply promotion code to booking"""
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'message': 'Database error'}
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get promotion details
        cursor.execute("""
            SELECT * FROM promotions 
            WHERE code = %s AND is_active = 1 
            AND start_date <= CURDATE() AND end_date >= CURDATE()
            AND (usage_limit IS NULL OR used_count < usage_limit)
        """, (promo_code,))
        promotion = cursor.fetchone()
        
        if not promotion:
            return {'success': False, 'message': 'Invalid or expired promo code'}
        
        # Get booking total
        cursor.execute("SELECT total_amount FROM bookings WHERE id = %s", (booking_id,))
        booking = cursor.fetchone()
        
        if not booking:
            return {'success': False, 'message': 'Booking not found'}
        
        total_amount = booking['total_amount']
        
        # Calculate discount
        if promotion['discount_type'] == 'percentage':
            discount = total_amount * (promotion['discount_value'] / 100)
            if promotion['max_discount_amount']:
                discount = min(discount, promotion['max_discount_amount'])
        else:  # fixed
            discount = promotion['discount_value']
        
        # Apply minimum booking amount check
        if promotion['min_booking_amount'] and total_amount < promotion['min_booking_amount']:
            return {'success': False, 'message': f'Minimum booking amount is ₱{promotion["min_booking_amount"]}'}
        
        # Update booking with discount
        final_amount = total_amount - discount
        
        cursor.execute("""
            UPDATE bookings 
            SET discount_amount = %s, total_amount = %s, promotion_code = %s
            WHERE id = %s
        """, (discount, final_amount, promo_code, booking_id))
        
        # Update promotion usage count
        cursor.execute("""
            UPDATE promotions SET used_count = used_count + 1 WHERE id = %s
        """, (promotion['id'],))
        
        conn.commit()
        
        return {
            'success': True,
            'discount': discount,
            'original_amount': total_amount,
            'final_amount': final_amount,
            'promotion_name': promotion['name']
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        cursor.close()
        conn.close()