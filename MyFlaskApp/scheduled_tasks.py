"""
Scheduled tasks for the car rental system.
Run these periodically via cron job or task scheduler.
"""

from MyFlaskApp import get_db_connection
from MyFlaskApp.user.user_bp import create_notification


def send_rental_reminders():
    """Send reminders for rentals starting/ending tomorrow."""
    conn = get_db_connection()
    if not conn:
        print("Database connection failed")
        return
    
    cursor = conn.cursor()
    try:
        # Rentals starting in 24h
        cursor.execute("""
            SELECT b.id, b.user_id, b.booking_reference, vb.name as brand_name, v.model
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE DATE(b.start_date) = CURDATE() + INTERVAL 1 DAY
            AND b.status = 'confirmed'
        """)
        bookings_starting = cursor.fetchall()
        
        for booking in bookings_starting:
            user_id, ref, brand, model = booking[1], booking[2], booking[3], booking[4]
            create_notification(
                user_id,
                'Rental Starts Tomorrow',
                f'Your {brand} {model} rental (Ref: {ref}) starts tomorrow! Get ready for your trip.',
                'booking_reminder',
                '/user/my-bookings'
            )
        
        # Rentals ending in 24h
        cursor.execute("""
            SELECT b.id, b.user_id, b.booking_reference, vb.name as brand_name, v.model
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE DATE(b.end_date) = CURDATE() + INTERVAL 1 DAY
            AND b.status = 'active'
        """)
        bookings_ending = cursor.fetchall()
        
        for booking in bookings_ending:
            user_id, ref, brand, model = booking[1], booking[2], booking[3], booking[4]
            create_notification(
                user_id,
                'Rental Ends Tomorrow',
                f'Your {brand} {model} rental (Ref: {ref}) ends tomorrow. Return by end of day to avoid late fees.',
                'booking_reminder',
                '/user/my-bookings'
            )
        
        conn.commit()
        print(f"✅ Sent {len(bookings_starting)} start reminders and {len(bookings_ending)} end reminders")
        
    except Exception as e:
        print(f"Error sending rental reminders: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def check_overdue_bookings():
    """Mark overdue bookings and notify users."""
    conn = get_db_connection()
    if not conn:
        print("Database connection failed")
        return
    
    cursor = conn.cursor()
    try:
        # Mark overdue bookings
        cursor.execute("""
            UPDATE bookings 
            SET status = 'overdue' 
            WHERE end_date < NOW() AND status = 'active'
        """)
        
        overdue_count = cursor.rowcount
        
        # Notify users with overdue bookings
        if overdue_count > 0:
            cursor.execute("""
                SELECT b.user_id, b.booking_reference, b.id, vb.name as brand_name, v.model
                FROM bookings b
                JOIN vehicles v ON b.vehicle_id = v.id
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE b.status = 'overdue' 
                AND DATE(b.end_date) = CURDATE() - INTERVAL 1 DAY
            """)
            overdue_bookings = cursor.fetchall()
            
            for booking in overdue_bookings:
                user_id, ref, booking_id, brand, model = booking[0], booking[1], booking[2], booking[3], booking[4]
                create_notification(
                    user_id,
                    'Booking Overdue',
                    f'Your {brand} {model} rental (Ref: {ref}) is overdue! Please return immediately to avoid additional fines.',
                    'fine_notice',
                    '/user/my-bookings'
                )
            
            print(f"✅ Marked {overdue_count} bookings as overdue and sent notifications")
        else:
            print("No overdue bookings found")
        
        conn.commit()
        
    except Exception as e:
        print(f"Error checking overdue bookings: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def send_maintenance_reminders():
    """Send reminders for vehicles due for maintenance."""
    conn = get_db_connection()
    if not conn:
        print("Database connection failed")
        return
    
    cursor = conn.cursor()
    try:
        # Vehicles with maintenance due in 7 days
        cursor.execute("""
            SELECT v.id, vb.name as brand_name, v.model, v.next_service_date
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE DATE(v.next_service_date) = CURDATE() + INTERVAL 7 DAY
            AND v.status != 'maintenance'
        """)
        maintenance_due = cursor.fetchall()
        
        for vehicle in maintenance_due:
            vehicle_id, brand, model, service_date = vehicle[0], vehicle[1], vehicle[2], vehicle[3]
            # Notify admin (user_id = 1)
            create_notification(
                1,
                'Maintenance Due Soon',
                f'{brand} {model} (ID: {vehicle_id}) is due for maintenance on {service_date.strftime("%Y-%m-%d")}.',
                'maintenance',
                '/admin/manage-vehicles'
            )
        
        conn.commit()
        print(f"✅ Sent {len(maintenance_due)} maintenance reminders")
        
    except Exception as e:
        print(f"Error sending maintenance reminders: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scheduled_tasks.py [reminders|overdue|maintenance|all]")
        sys.exit(1)
    
    task = sys.argv[1]
    
    if task == 'reminders':
        send_rental_reminders()
    elif task == 'overdue':
        check_overdue_bookings()
    elif task == 'maintenance':
        send_maintenance_reminders()
    elif task == 'all':
        send_rental_reminders()
        check_overdue_bookings()
        send_maintenance_reminders()
    else:
        print(f"Unknown task: {task}")
        sys.exit(1)
