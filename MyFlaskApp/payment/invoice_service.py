from datetime import datetime
import os
from MyFlaskApp import get_db_connection

class InvoiceService:

    @staticmethod
    def generate_invoice_number():
        """Generate unique invoice number"""
        timestamp = datetime.now().strftime('%Y%m%d')
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM invoices WHERE invoice_number LIKE %s", (f'INV-{timestamp}%',))
            count = cursor.fetchone()[0]
            return f"INV-{timestamp}-{str(count + 1).zfill(4)}"
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def create_invoice_for_booking(booking_id):
        """Create invoice for booking - FIXED for your table structure"""
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'message': 'Database error'}

        cursor = conn.cursor(dictionary=True)
        try:
            # Get booking details
            cursor.execute("""
                SELECT b.*, v.model, v.brand_id, vb.name as brand_name,
                       u.first_name, u.last_name, u.email, u.phone, u.address,
                       u.city, u.state, u.postal_code, u.country, b.user_id
                FROM bookings b
                JOIN vehicles v ON b.vehicle_id = v.id
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                JOIN users u ON b.user_id = u.id
                WHERE b.id = %s
            """, (booking_id,))
            booking = cursor.fetchone()

            if not booking:
                return {'success': False, 'message': 'Booking not found'}

            # Check if invoice already exists
            cursor.execute("SELECT id FROM invoices WHERE booking_id = %s", (booking_id,))
            existing = cursor.fetchone()
            if existing:
                return {'success': True, 'invoice_id': existing['id'], 'message': 'Invoice already exists'}

            # Generate invoice number
            invoice_number = InvoiceService.generate_invoice_number()

            # Calculate amounts
            subtotal = booking.get('subtotal', 0)
            tax_amount = booking.get('tax_amount', 0)
            discount_amount = booking.get('discount_amount', 0) or 0
            total_amount = booking.get('total_amount', 0)

            # Create invoice - using correct column names for your table
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number,
                    booking_id,
                    user_id,
                    invoice_date,
                    due_date,
                    subtotal,
                    tax_amount,
                    discount_amount,
                    total_amount,
                    balance_due,
                    status
                ) VALUES (
                    %s, %s, %s, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 7 DAY),
                    %s, %s, %s, %s, %s,
                    'pending'
                )
            """, (invoice_number, booking_id, booking['user_id'], subtotal, tax_amount, discount_amount, total_amount, total_amount))

            invoice_id = cursor.lastrowid
            conn.commit()

            return {
                'success': True,
                'invoice_id': invoice_id,
                'invoice_number': invoice_number,
                'booking': booking
            }

        except Exception as e:
            conn.rollback()
            print(f"Error creating invoice: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def create_invoice(booking_id, user_id):
        """Create invoice for booking"""
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'message': 'Database error'}

        cursor = conn.cursor(dictionary=True)
        try:
            # Get booking details
            cursor.execute("""
                SELECT b.*, v.model, v.brand_id, vb.name as brand_name,
                       u.first_name, u.last_name, u.email, u.phone, u.address,
                       u.city, u.state, u.postal_code, u.country
                FROM bookings b
                JOIN vehicles v ON b.vehicle_id = v.id
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                JOIN users u ON b.user_id = u.id
                WHERE b.id = %s AND b.user_id = %s
            """, (booking_id, user_id))
            booking = cursor.fetchone()

            if not booking:
                return {'success': False, 'message': 'Booking not found'}

            # Check if invoice already exists
            cursor.execute("SELECT id FROM invoices WHERE booking_id = %s", (booking_id,))
            existing = cursor.fetchone()
            if existing:
                return {'success': True, 'invoice_id': existing['id'], 'message': 'Invoice already exists'}

            # Get payment details
            cursor.execute("""
                SELECT * FROM payments
                WHERE booking_id = %s AND payment_status = 'successful'
                ORDER BY paid_at DESC LIMIT 1
            """, (booking_id,))
            payment = cursor.fetchone()

            # Generate invoice number
            invoice_number = InvoiceService.generate_invoice_number()

            # Calculate amounts
            subtotal = booking['subtotal']
            tax_amount = booking['tax_amount']
            discount_amount = booking.get('discount_amount', 0) or 0
            total_amount = booking['total_amount']
            amount_paid = payment['amount'] if payment else 0

            # Create invoice - using correct column names
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number,
                    booking_id,
                    user_id,
                    invoice_date,
                    due_date,
                    subtotal,
                    tax_amount,
                    discount_amount,
                    total_amount,
                    balance_due,
                    status
                ) VALUES (
                    %s, %s, %s, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 7 DAY),
                    %s, %s, %s, %s, %s,
                    CASE WHEN %s >= %s THEN 'paid' ELSE 'pending' END
                )
            """, (invoice_number, booking_id, booking['user_id'], subtotal, tax_amount, discount_amount, total_amount, total_amount,
                  amount_paid, total_amount))

            invoice_id = cursor.lastrowid
            conn.commit()

            return {
                'success': True,
                'invoice_id': invoice_id,
                'invoice_number': invoice_number,
                'booking': booking,
                'payment': payment
            }

        except Exception as e:
            conn.rollback()
            print(f"Error creating invoice: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_invoice_by_booking(booking_id):
        """Get invoice for a specific booking"""
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT i.*,
                       b.booking_reference, b.start_date, b.end_date,
                       b.pickup_location, b.return_location, b.rental_days,
                       v.model, vb.name as brand_name, v.license_plate,
                       u.first_name, u.last_name, u.email, u.phone, u.address
                FROM invoices i
                JOIN bookings b ON i.booking_id = b.id
                JOIN vehicles v ON b.vehicle_id = v.id
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                JOIN users u ON b.user_id = u.id
                WHERE i.booking_id = %s
            """, (booking_id,))
            return cursor.fetchone()
        except Exception as e:
            print(f"Error getting invoice: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def update_payment_status(invoice_id, status, payment_method=None, transaction_id=None):
        """Update invoice payment status"""
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE invoices
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (status, invoice_id))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating payment status: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def mark_as_paid(invoice_id, payment_method=None, transaction_id=None):
        """Mark invoice as paid"""
        return InvoiceService.update_payment_status(invoice_id, 'paid', payment_method, transaction_id)

    @staticmethod
    def get_user_invoices(user_id):
        """Get all invoices for a user"""
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT i.*, b.booking_reference, v.model, vb.name as brand_name
                FROM invoices i
                JOIN bookings b ON i.booking_id = b.id
                JOIN vehicles v ON b.vehicle_id = v.id
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE b.user_id = %s
                ORDER BY i.created_at DESC
            """, (user_id,))
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting user invoices: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def generate_pdf(invoice_id):
        """Generate PDF invoice (placeholder - creates HTML invoice)"""
        print(f"Invoice {invoice_id} generated - PDF coming soon!")
        return None
