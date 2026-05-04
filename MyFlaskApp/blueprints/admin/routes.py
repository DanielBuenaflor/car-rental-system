# ============================================================================
# IMPORTS
# ============================================================================
import os
import mysql.connector
from functools import wraps
from datetime import datetime

from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify, request
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from MyFlaskApp import get_db_connection
from MyFlaskApp.payment.payment_service import process_booking_payment
from MyFlaskApp.payment.invoice_service import InvoiceService
from MyFlaskApp.email.service import EmailService
from MyFlaskApp.utils.csrf import generate_csrf_token, validate_csrf_token, clear_csrf_token
from MyFlaskApp.utils.secure_upload import save_upload, ALLOWED_IMAGE_EXTENSIONS


# ============================================================================
# CONFIGURATION
# ============================================================================
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
    'base', 'uploads', 'vehicles'
)


# ============================================================================
# BLUEPRINT CONFIGURATION
# ============================================================================
admin_bp = Blueprint(
    'admin_bp', 
    __name__, 
    template_folder='templates',
    static_folder='static', 
    static_url_path="/admin_statics"
)


# ============================================================================
# DECORATORS
# ============================================================================
def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('loggedin'):
            flash('Please login to access this page', 'error')
            return redirect(url_for('auth_bp.login'))
        if session.get('role') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('base_bp.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# PAGE ROUTES
# ============================================================================

@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard page"""
    conn = get_db_connection()
    if not conn:
        return render_template('admin_dashboard.html', 
                               dashboard_stats={},
                               booking_trend={'labels': [], 'data': []},
                               revenue_trend={'labels': [], 'data': []},
                               recent_bookings=[],
                               pending_verifications=0,
                               session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get dashboard stats
        dashboard_stats = {}
        
        # User count
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user'")
        dashboard_stats['user_count'] = cursor.fetchone()['count']
        
        # Vehicle count
        cursor.execute("SELECT COUNT(*) as count FROM vehicles")
        dashboard_stats['vehicle_count'] = cursor.fetchone()['count']
        
        # Brand count
        cursor.execute("SELECT COUNT(*) as count FROM vehicle_brands")
        dashboard_stats['brand_count'] = cursor.fetchone()['count']
        
        # Booking count
        cursor.execute("SELECT COUNT(*) as count FROM bookings")
        dashboard_stats['booking_count'] = cursor.fetchone()['count']
        
        # New queries
        cursor.execute("SELECT COUNT(*) as count FROM contact_queries WHERE status = 'new'")
        dashboard_stats['new_queries'] = cursor.fetchone()['count']
        
        # Subscriber count
        cursor.execute("SELECT COUNT(*) as count FROM subscribers WHERE is_active = 1")
        dashboard_stats['subscriber_count'] = cursor.fetchone()['count']
        
        # Extension count
        cursor.execute("SELECT COUNT(*) as count FROM extension_requests WHERE status = 'pending'")
        dashboard_stats['extension_count'] = cursor.fetchone()['count']
        
        # Pending verifications
        cursor.execute("SELECT COUNT(*) as count FROM verifications WHERE verification_status = 'pending'")
        pending_verifications = cursor.fetchone()['count']
        
        # Total revenue from bookings table
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE status IN ('completed', 'active', 'confirmed')")
        revenue_data = cursor.fetchone()
        dashboard_stats['total_revenue'] = revenue_data['total'] if revenue_data['total'] else 0
        
        # Booking trend (last 6 months)
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as count
            FROM bookings
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month ASC
        """)
        booking_trend = cursor.fetchall()
        booking_trend_data = {
            'labels': [item['month'] for item in booking_trend],
            'data': [item['count'] for item in booking_trend]
        }
        
        # Revenue trend from bookings (last 6 months)
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COALESCE(SUM(total_amount), 0) as total
            FROM bookings
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
            AND status IN ('completed', 'active', 'confirmed')
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month ASC
        """)
        revenue_trend = cursor.fetchall()
        revenue_trend_data = {
            'labels': [item['month'] for item in revenue_trend],
            'data': [float(item['total']) for item in revenue_trend]
        }
        
        # Recent bookings
        cursor.execute("""
            SELECT b.*, CONCAT(u.first_name, ' ', u.last_name) as user_name, 
                   v.model, vb.name as brand_name
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY b.created_at DESC
            LIMIT 5
        """)
        recent_bookings = cursor.fetchall()
        
        return render_template('admin_dashboard.html', 
                               dashboard_stats=dashboard_stats,
                               booking_trend=booking_trend_data,
                               revenue_trend=revenue_trend_data,
                               recent_bookings=recent_bookings,
                               pending_verifications=pending_verifications,
                               session=session)
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        import traceback
        traceback.print_exc()
        return render_template('admin_dashboard.html', 
                               dashboard_stats={},
                               booking_trend={'labels': [], 'data': []},
                               revenue_trend={'labels': [], 'data': []},
                               recent_bookings=[],
                               pending_verifications=0,
                               session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-brands')
@admin_required
def manage_brands():
    """Manage vehicle brands"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_brands.html', brands=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vehicle_brands ORDER BY name")
        brands = cursor.fetchall()
        return render_template('manage_brands.html', brands=brands, session=session)
    except Exception as e:
        print(f"Error loading brands: {e}")
        return render_template('manage_brands.html', brands=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-vehicles')
@admin_required
def manage_vehicles():
    """Manage vehicles with search and filters"""
    from MyFlaskApp.utils.secure_db import fetch_all, fetch_one
    from MyFlaskApp.utils.secure_db import DatabaseError
    
    search = request.args.get('search', '').strip()
    brand_id = request.args.get('brand_id', '')
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    try:
        conditions = []
        params = []
        
        if search:
            conditions.append("(v.model LIKE %s OR v.license_plate LIKE %s OR vb.name LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if brand_id:
            try:
                conditions.append("v.brand_id = %s")
                params.append(int(brand_id))
            except (ValueError, TypeError):
                pass
        
        if status:
            valid_statuses = ['available', 'rented', 'maintenance', 'reserved', 'unavailable']
            if status in valid_statuses:
                conditions.append("v.status = %s")
                params.append(status)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        count_query = f"""
            SELECT COUNT(*) as total
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            {where_clause}
        """
        total = fetch_one(count_query, tuple(params))
        total_count = total['total'] if total else 0
        
        offset = (page - 1) * per_page
        list_query = f"""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            {where_clause}
            ORDER BY v.id DESC
            LIMIT %s OFFSET %s
        """
        vehicles = fetch_all(list_query, tuple(params + [per_page, offset]))
        
        brands = fetch_all("SELECT id, name FROM vehicle_brands ORDER BY name")
        
        print(f"Loaded {len(vehicles)} vehicles and {len(brands)} brands")
        
        return render_template('manage_vehicles.html', 
                               vehicles=vehicles, 
                               brands=brands,
                               total=total_count,
                               page=page,
                               per_page=per_page,
                               search=search,
                               brand_id=brand_id,
                               status=status,
                               session=session)
    except DatabaseError as e:
        print(f"Error loading vehicles: {e}")
        flash('Error loading vehicles', 'error')
        return render_template('manage_vehicles.html', vehicles=[], brands=[], 
                               total=0, page=1, per_page=per_page,
                               search=search, brand_id=brand_id, status=status,
                               session=session)
    except Exception as e:
        print(f"Error loading vehicles: {e}")
        flash('Error loading vehicles', 'error')
        return render_template('manage_vehicles.html', vehicles=[], brands=[], 
                               total=0, page=1, per_page=per_page,
                               search=search, brand_id=brand_id, status=status,
                               session=session)


@admin_bp.route('/manage-users')
@admin_required
def manage_users():
    """Manage users"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_users.html', users=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, first_name, last_name, email, phone, role, is_active, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        return render_template('manage_users.html', users=users, session=session)
    except Exception as e:
        print(f"Error loading users: {e}")
        return render_template('manage_users.html', users=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-bookings')
@admin_required
def manage_bookings():
    """Manage bookings"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_bookings.html', bookings=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   u.email as user_email,
                   u.phone as user_phone,
                   v.model, v.year, v.license_plate, v.daily_rate as daily_rate_applied,
                   vb.name as brand_name
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY b.created_at DESC
        """)
        bookings = cursor.fetchall()
        return render_template('manage_bookings.html', bookings=bookings, session=session)
    except Exception as e:
        print(f"Error loading bookings: {e}")
        return render_template('manage_bookings.html', bookings=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/testimonials')
@admin_required
def admin_view_testimonials():
    """Admin view all testimonials (read-only)"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    conn = get_db_connection()
    if not conn:
        return render_template('admin_testimonials.html', testimonials=[], page=1, total_pages=1, session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM testimonials")
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result else 0
        total_pages = (total + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get all testimonials with user + vehicle info
        cursor.execute("""
            SELECT t.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   u.email as user_email,
                   vb.name as brand_name, v.model
            FROM testimonials t
            JOIN users u ON t.user_id = u.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            LEFT JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        testimonials = cursor.fetchall()
        
        return render_template('admin_testimonials.html', 
                               testimonials=testimonials,
                               page=page,
                               total_pages=total_pages,
                               session=session)
    except Exception as e:
        print(f"Admin testimonials error: {e}")
        return render_template('admin_testimonials.html', testimonials=[], page=1, total_pages=1, session=session)
    finally:
        cursor.close()
        conn.close()

    
@admin_bp.route('/manage-queries')
@admin_required
def manage_queries():
    """Manage contact queries"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_queries.html', queries=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT q.*, CONCAT(u.first_name, ' ', u.last_name) as user_name
            FROM contact_queries q
            LEFT JOIN users u ON q.user_id = u.id
            ORDER BY q.created_at DESC
        """)
        queries = cursor.fetchall()
        return render_template('manage_queries.html', queries=queries, session=session)
    except Exception as e:
        print(f"Error loading queries: {e}")
        return render_template('manage_queries.html', queries=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-subscribers')
@admin_required
def manage_subscribers():
    """Manage subscribers"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_subscribers.html', subscribers=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM subscribers
            ORDER BY subscribed_at DESC
        """)
        subscribers = cursor.fetchall()
        return render_template('manage_subscribers.html', subscribers=subscribers, session=session)
    except Exception as e:
        print(f"Error loading subscribers: {e}")
        return render_template('manage_subscribers.html', subscribers=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-page-content')
@admin_required
def manage_page_content():
    """Manage page content"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_page_content.html', content_by_page={}, session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM page_contents
            ORDER BY page_name, order_position
        """)
        all_content = cursor.fetchall()
        
        # Group content by page
        content_by_page = {}
        for item in all_content:
            page = item['page_name']
            if page not in content_by_page:
                content_by_page[page] = []
            content_by_page[page].append(item)
        
        return render_template('manage_page_content.html', 
                               content_by_page=content_by_page,
                               session=session)
    except Exception as e:
        print(f"Error loading page content: {e}")
        return render_template('manage_page_content.html', content_by_page={}, session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-contact-details')
@admin_required
def manage_contact_details():
    """Manage contact details"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_contact_details.html', contacts=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM contact_details
            ORDER BY order_position
        """)
        contacts = cursor.fetchall()
        return render_template('manage_contact_details.html', contacts=contacts, session=session)
    except Exception as e:
        print(f"Error loading contact details: {e}")
        return render_template('manage_contact_details.html', contacts=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-verifications')
@admin_required
def manage_verifications():
    """Manage verifications page"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_verifications.html', verifications=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT v.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   u.email, u.phone
            FROM verifications v
            JOIN users u ON v.user_id = u.id
            ORDER BY v.created_at DESC
        """)
        verifications = cursor.fetchall()
        
        return render_template('manage_verifications.html', 
                               verifications=verifications,
                               session=session)
    except Exception as e:
        print(f"Error loading verifications: {e}")
        return render_template('manage_verifications.html', verifications=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-extensions')
@admin_required
def manage_extensions():
    """Manage extension requests"""
    conn = get_db_connection()
    if not conn:
        return render_template('manage_extensions.html', extensions=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT er.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   b.booking_reference, v.model, vb.name as brand_name
            FROM extension_requests er
            JOIN users u ON er.user_id = u.id
            JOIN bookings b ON er.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY er.created_at DESC
        """)
        extensions = cursor.fetchall()
        return render_template('manage_extensions.html', extensions=extensions, session=session)
    except Exception as e:
        print(f"Error loading extensions: {e}")
        return render_template('manage_extensions.html', extensions=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-invoices')
@admin_required
def manage_invoices():
    """Manage all invoices"""
    status_filter = request.args.get('status', 'all')
    
    conn = get_db_connection()
    if not conn:
        return render_template('manage_invoices.html', invoices=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT i.*, 
                   b.booking_reference,
                   b.start_date, 
                   b.end_date,
                   v.model, 
                   vb.name as brand_name,
                   u.first_name, 
                   u.last_name,
                   u.email
            FROM invoices i
            JOIN bookings b ON i.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            JOIN users u ON b.user_id = u.id
        """
        
        if status_filter == 'paid':
            query += " WHERE i.status = 'paid'"
        elif status_filter == 'pending':
            query += " WHERE i.status = 'pending'"
        elif status_filter == 'overdue':
            query += " WHERE i.status = 'overdue'"
        
        query += " ORDER BY i.invoice_date DESC"
        
        cursor.execute(query)
        invoices = cursor.fetchall()
        return render_template('manage_invoices.html', invoices=invoices, status_filter=status_filter, session=session)
    except Exception as e:
        print(f"Error loading invoices: {e}")
        return render_template('manage_invoices.html', invoices=[], session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/invoices')
@admin_required
def api_get_invoices():
    """API to get all invoices with filters"""
    status = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT i.*, 
                   b.booking_reference,
                   b.start_date, 
                   b.end_date,
                   v.model, 
                   vb.name as brand_name,
                   u.first_name, 
                   u.last_name,
                   u.email
            FROM invoices i
            JOIN bookings b ON i.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            JOIN users u ON b.user_id = u.id
            WHERE 1=1
        """
        
        params = []
        
        if status == 'paid':
            query += " AND i.status = 'paid'"
        elif status == 'pending':
            query += " AND i.status = 'pending'"
        elif status == 'overdue':
            query += " AND i.status = 'overdue'"
        
        if search:
            query += " AND (i.invoice_number LIKE %s OR u.first_name LIKE %s OR u.last_name LIKE %s OR u.email LIKE %s)"
            search_param = f"%{search}%"
            params = [search_param, search_param, search_param, search_param]
        
        query += " ORDER BY i.invoice_date DESC"
        
        cursor.execute(query, params)
        invoices = cursor.fetchall()
        return jsonify(invoices)
    except Exception as e:
        print(f"Error getting invoices: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/invoices/<int:invoice_id>/resend', methods=['POST'])
@admin_required
def api_resend_invoice(invoice_id):
    """Resend invoice email to customer"""
    from MyFlaskApp.email.service import EmailService
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT i.*, 
                   b.booking_reference,
                   b.start_date, 
                   b.end_date,
                   v.model, 
                   vb.name as brand_name,
                   u.first_name, 
                   u.last_name,
                   u.email
            FROM invoices i
            JOIN bookings b ON i.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            JOIN users u ON b.user_id = u.id
            WHERE i.id = %s
        """, (invoice_id,))
        invoice = cursor.fetchone()
        
        if not invoice:
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
        
        # Send invoice email
        user = {
            'email': invoice['email'],
            'first_name': invoice['first_name']
        }
        booking = {
            'booking_reference': invoice['booking_reference'],
            'start_date': invoice['start_date'],
            'end_date': invoice['end_date']
        }
        vehicle = {
            'brand_name': invoice['brand_name'],
            'model': invoice['model']
        }
        
        result = EmailService.send_invoice(user, invoice, booking, vehicle)
        
        if result:
            return jsonify({'success': True, 'message': 'Invoice resent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send email'})
            
    except Exception as e:
        print(f"Error resending invoice: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/manage-vehicle-images')
@admin_required
def manage_vehicle_images():
    """Manage vehicle images with search"""
    # Get search parameters
    search = request.args.get('search', '').strip()
    selected_vehicle_id = request.args.get('vehicle_id', type=int)
    
    conn = get_db_connection()
    if not conn:
        return render_template('manage_vehicle_images.html', 
                               all_vehicles=[], 
                               selected_vehicle=None,
                               vehicle_images_by_id={},
                               selected_vehicle_id=None,
                               search=search,
                               session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get all vehicles with search
        if search:
            cursor.execute("""
                SELECT v.*, vb.name as brand_name
                FROM vehicles v
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE v.model LIKE %s OR vb.name LIKE %s OR v.license_plate LIKE %s
                ORDER BY vb.name, v.model
            """, (f"%{search}%", f"%{search}%", f"%{search}%"))
        else:
            cursor.execute("""
                SELECT v.*, vb.name as brand_name
                FROM vehicles v
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                ORDER BY vb.name, v.model
            """)
        all_vehicles = cursor.fetchall()
        
        selected_vehicle = None
        vehicle_images_by_id = {}
        
        if selected_vehicle_id:
            # Get selected vehicle details
            cursor.execute("""
                SELECT v.*, vb.name as brand_name
                FROM vehicles v
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE v.id = %s
            """, (selected_vehicle_id,))
            selected_vehicle = cursor.fetchone()
            
            if selected_vehicle:
                # Get images for selected vehicle
                cursor.execute("""
                    SELECT * FROM vehicle_images 
                    WHERE vehicle_id = %s 
                    ORDER BY is_primary DESC, sort_order ASC
                """, (selected_vehicle_id,))
                images = cursor.fetchall()
                
                # Also get primary image from vehicles table if no images in vehicle_images
                if not images and selected_vehicle.get('primary_image'):
                    images = [{
                        'id': None,
                        'image_path': selected_vehicle['primary_image'],
                        'is_primary': True,
                        'sort_order': 0
                    }]
                
                vehicle_images_by_id[selected_vehicle_id] = images
        
        return render_template('manage_vehicle_images.html', 
                               all_vehicles=all_vehicles,
                               selected_vehicle=selected_vehicle,
                               vehicle_images_by_id=vehicle_images_by_id,
                               selected_vehicle_id=selected_vehicle_id,
                               search=search,
                               session=session)
    except Exception as e:
        print(f"Error loading vehicle images: {e}")
        return render_template('manage_vehicle_images.html', 
                               all_vehicles=[], 
                               selected_vehicle=None,
                               vehicle_images_by_id={},
                               selected_vehicle_id=None,
                               search=search,
                               session=session)
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/reports')
@admin_required
def reports():
    """Analytics reports page"""
    conn = get_db_connection()
    if not conn:
        return render_template('reports.html', 
                               most_rented=[], 
                               vehicle_usage=[], 
                               top_customers=[],
                               session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Most rented vehicles
        cursor.execute("""
            SELECT 
                vb.name AS brand,
                v.model,
                COUNT(b.id) AS rental_count,
                COALESCE(SUM(b.total_amount), 0) AS total_revenue,
                COALESCE(AVG(DATEDIFF(b.end_date, b.start_date)), 0) AS avg_rental_days
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            LEFT JOIN bookings b ON v.id = b.vehicle_id AND b.status NOT IN ('cancelled')
            GROUP BY v.id, vb.name, v.model
            ORDER BY rental_count DESC
            LIMIT 10
        """)
        most_rented = cursor.fetchall()
        
        # Vehicle usage rate
        cursor.execute("""
            SELECT 
                vb.name AS brand,
                v.model,
                COUNT(b.id) AS total_bookings,
                SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) AS completed_bookings,
                ROUND(SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) / NULLIF(COUNT(b.id), 0) * 100, 2) AS usage_rate
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            LEFT JOIN bookings b ON v.id = b.vehicle_id
            GROUP BY v.id, vb.name, v.model
            HAVING total_bookings > 0
            ORDER BY usage_rate DESC
            LIMIT 10
        """)
        vehicle_usage = cursor.fetchall()
        
        # Top customers by spending
        cursor.execute("""
            SELECT 
                CONCAT(u.first_name, ' ', u.last_name) AS customer_name,
                u.email,
                COUNT(b.id) AS total_bookings,
                COALESCE(SUM(b.total_amount), 0) AS total_spent,
                COALESCE(AVG(b.total_amount), 0) AS avg_booking_value
            FROM users u
            LEFT JOIN bookings b ON u.id = b.user_id AND b.status NOT IN ('cancelled')
            WHERE u.role = 'user'
            GROUP BY u.id, u.first_name, u.last_name, u.email
            HAVING total_bookings > 0
            ORDER BY total_spent DESC
            LIMIT 10
        """)
        top_customers = cursor.fetchall()
        
        return render_template('reports.html', 
                               most_rented=most_rented,
                               vehicle_usage=vehicle_usage,
                               top_customers=top_customers,
                               session=session)
    except Exception as e:
        print(f"Error loading reports: {e}")
        return render_template('reports.html', 
                               most_rented=[], 
                               vehicle_usage=[], 
                               top_customers=[],
                               session=session)
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - DASHBOARD
# ============================================================================

@admin_bp.route('/api/dashboard-stats')
@admin_required
def get_dashboard_stats():
    """Get dashboard statistics - Used for real-time updates"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        counts = {}
        
        # User counts
        try:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user'")
            counts['userCount'] = cursor.fetchone()['count']
        except:
            counts['userCount'] = 0
        
        # Vehicle counts
        try:
            cursor.execute("SELECT COUNT(*) as count FROM vehicles")
            counts['vehicleCount'] = cursor.fetchone()['count']
        except:
            counts['vehicleCount'] = 0
        
        # Brand counts
        try:
            cursor.execute("SELECT COUNT(*) as count FROM vehicle_brands")
            counts['brandCount'] = cursor.fetchone()['count']
        except:
            counts['brandCount'] = 0
        
        # Booking counts
        try:
            cursor.execute("SELECT COUNT(*) as count FROM bookings")
            counts['bookingCount'] = cursor.fetchone()['count']
        except:
            counts['bookingCount'] = 0
        
        # New queries
        try:
            cursor.execute("SELECT COUNT(*) as count FROM contact_queries WHERE status = 'new'")
            counts['newQueries'] = cursor.fetchone()['count']
        except:
            counts['newQueries'] = 0
        
        # Subscriber counts
        try:
            cursor.execute("SELECT COUNT(*) as count FROM subscribers WHERE is_active = 1")
            counts['subscriberCount'] = cursor.fetchone()['count']
        except:
            counts['subscriberCount'] = 0
        
        # Total revenue
        try:
            cursor.execute("SELECT SUM(total_amount) as total FROM payments WHERE payment_status = 'successful'")
            revenue_data = cursor.fetchone()
            counts['totalRevenue'] = revenue_data['total'] if revenue_data['total'] else 0
        except:
            counts['totalRevenue'] = 0
        
        # Booking trend (last 6 months)
        counts['bookingTrend'] = {'labels': [], 'data': []}
        try:
            cursor.execute("""
                SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as count
                FROM bookings
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
                GROUP BY DATE_FORMAT(created_at, '%Y-%m')
                ORDER BY month ASC
            """)
            booking_trend = cursor.fetchall()
            counts['bookingTrend'] = {
                'labels': [item['month'] for item in booking_trend],
                'data': [item['count'] for item in booking_trend]
            }
        except:
            pass
        
        # Revenue trend (last 6 months)
        counts['revenueTrend'] = {'labels': [], 'data': []}
        try:
            cursor.execute("""
                SELECT DATE_FORMAT(paid_at, '%Y-%m') as month, SUM(amount) as total
                FROM payments
                WHERE payment_status = 'successful' AND paid_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
                GROUP BY DATE_FORMAT(paid_at, '%Y-%m')
                ORDER BY month ASC
            """)
            revenue_trend = cursor.fetchall()
            counts['revenueTrend'] = {
                'labels': [item['month'] for item in revenue_trend],
                'data': [item['total'] for item in revenue_trend]
            }
        except:
            pass
        
        # Recent activity (last 5 bookings)
        counts['recentActivity'] = []
        try:
            cursor.execute("""
                SELECT b.*, u.first_name, u.last_name, v.model 
                FROM bookings b
                JOIN users u ON b.user_id = u.id
                JOIN vehicles v ON b.vehicle_id = v.id
                ORDER BY b.created_at DESC
                LIMIT 5
            """)
            recent_bookings = cursor.fetchall()
            
            for booking in recent_bookings:
                counts['recentActivity'].append({
                    'icon': 'calendar-check',
                    'message': f"New booking: {booking['first_name']} {booking['last_name']} booked {booking['model']}",
                    'time': booking['created_at'].strftime('%Y-%m-%d %H:%M') if booking['created_at'] else 'Just now'
                })
        except:
            pass
        
        return jsonify(counts)
        
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/toggle-view-mode', methods=['POST'])
@admin_required
def toggle_view_mode():
    """Toggle between admin view and user view"""
    try:
        if session.get('view_as_user'):
            session.pop('view_as_user', None)
            message = 'Switched to Admin View'
        else:
            session['view_as_user'] = True
            message = 'Viewing as User'
        
        return jsonify({
            'success': True,
            'message': message,
            'view_as_user': session.get('view_as_user', False)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================================
# API ROUTES - VEHICLE BRANDS
# ============================================================================

@admin_bp.route('/api/brands')
@admin_required
def api_get_brands():
    """Get all vehicle brands"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vehicle_brands ORDER BY name")
        brands = cursor.fetchall()
        return jsonify(brands)
    except Exception as e:
        print(f"Error getting brands: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/brands', methods=['POST'])
@admin_required
def api_create_brand():
    """Create new vehicle brand"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO vehicle_brands (name, description, created_at)
            VALUES (%s, %s, NOW())
        """, (data.get('name'), data.get('description', '')))
        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/brands/<int:brand_id>', methods=['PUT'])
@admin_required
def api_update_brand(brand_id):
    """Update vehicle brand"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE vehicle_brands 
            SET name = %s, description = %s
            WHERE id = %s
        """, (data.get('name'), data.get('description', ''), brand_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/brands/<int:brand_id>', methods=['DELETE'])
@admin_required
def api_delete_brand(brand_id):
    """Delete vehicle brand"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM vehicle_brands WHERE id = %s", (brand_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - VEHICLES
# ============================================================================

@admin_bp.route('/api/vehicles')
@admin_required
def api_get_vehicles():
    """Get all vehicles"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY v.id DESC
        """)
        vehicles = cursor.fetchall()
        
        # Convert any non-serializable objects
        for vehicle in vehicles:
            if 'created_at' in vehicle and vehicle['created_at']:
                vehicle['created_at'] = vehicle['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            if 'updated_at' in vehicle and vehicle['updated_at']:
                vehicle['updated_at'] = vehicle['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(vehicles)
    except Exception as e:
        print(f"Error getting vehicles: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/vehicles/<int:vehicle_id>')
@admin_required
def api_get_vehicle(vehicle_id):
    """Get single vehicle"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.id = %s
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


@admin_bp.route('/api/vehicles', methods=['POST'])
@admin_required
def api_create_vehicle():
    """Create new vehicle"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO vehicles (
                brand_id, model, year, license_plate, color, transmission,
                fuel_type, seating_capacity, daily_rate, weekly_rate, monthly_rate,
                security_deposit, mileage_limit_km, excess_km_charge, location, status, description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('brand_id'),
            data.get('model'),
            data.get('year'),
            data.get('license_plate'),
            data.get('color'),
            data.get('transmission'),
            data.get('fuel_type'),
            data.get('seating_capacity'),
            data.get('daily_rate'),
            data.get('weekly_rate'),
            data.get('monthly_rate'),
            data.get('security_deposit'),
            data.get('mileage_limit_km'),
            data.get('excess_km_charge'),
            data.get('location', ''),
            data.get('status', 'available'),
            data.get('description', '')
        ))
        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/vehicles/<int:vehicle_id>', methods=['PUT'])
@admin_required
def api_update_vehicle(vehicle_id):
    """Update vehicle"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE vehicles 
            SET brand_id = %s, model = %s, year = %s, license_plate = %s, 
                color = %s, transmission = %s, fuel_type = %s, seating_capacity = %s,
                daily_rate = %s, weekly_rate = %s, monthly_rate = %s,
                security_deposit = %s, mileage_limit_km = %s, excess_km_charge = %s,
                location = %s, status = %s, description = %s
            WHERE id = %s
        """, (
            data.get('brand_id'),
            data.get('model'),
            data.get('year'),
            data.get('license_plate'),
            data.get('color'),
            data.get('transmission'),
            data.get('fuel_type'),
            data.get('seating_capacity'),
            data.get('daily_rate'),
            data.get('weekly_rate'),
            data.get('monthly_rate'),
            data.get('security_deposit'),
            data.get('mileage_limit_km'),
            data.get('excess_km_charge'),
            data.get('location', ''),
            data.get('status', 'available'),
            data.get('description', ''),
            vehicle_id
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/vehicles/<int:vehicle_id>', methods=['DELETE'])
@admin_required
def api_delete_vehicle(vehicle_id):
    """Delete vehicle"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM vehicles WHERE id = %s", (vehicle_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - VEHICLE IMAGES
# ============================================================================

@admin_bp.route('/api/vehicles/<int:vehicle_id>/upload-images', methods=['POST'])
@admin_required
def api_upload_vehicle_images(vehicle_id):
    """Upload images for a vehicle"""
    # Verify vehicle exists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM vehicles WHERE id = %s", (vehicle_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Vehicle not found'}), 404
    cursor.close()

    uploaded_files = []

    # Handle primary image
    if 'primary_image' in request.files:
        file = request.files['primary_image']
        if file and file.filename:
            filename, error = save_upload(file, UPLOAD_FOLDER, allowed_extensions=ALLOWED_IMAGE_EXTENSIONS, check_magic_bytes=True)
            if error:
                return jsonify({'success': False, 'message': f'Primary image: {error}'}), 400
            image_path = f"/uploads/vehicles/{filename}"
            uploaded_files.append({'type': 'primary', 'path': image_path})

            # Update vehicle primary_image
            cursor = conn.cursor()
            cursor.execute("UPDATE vehicles SET primary_image = %s WHERE id = %s",
                          (image_path, vehicle_id))
            conn.commit()
            cursor.close()

    # Handle gallery images
    if 'gallery_images' in request.files:
        files = request.files.getlist('gallery_images')
        for idx, file in enumerate(files):
            if file and file.filename:
                filename, error = save_upload(file, UPLOAD_FOLDER, allowed_extensions=ALLOWED_IMAGE_EXTENSIONS, check_magic_bytes=True)
                if error:
                    return jsonify({'success': False, 'message': f'Gallery image {idx+1}: {error}'}), 400
                image_path = f"/uploads/vehicles/{filename}"
                uploaded_files.append({'type': 'gallery', 'path': image_path})

                # Insert into vehicle_images table
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vehicle_images (vehicle_id, image_path, is_primary, sort_order)
                    VALUES (%s, %s, %s, %s)
                """, (vehicle_id, image_path, False, idx))
                conn.commit()
                cursor.close()

    conn.close()

    return jsonify({
        'success': True,
        'message': f'Uploaded {len(uploaded_files)} images',
        'files': uploaded_files
    })


@admin_bp.route('/api/vehicles/<int:vehicle_id>/images')
@admin_required
def api_get_vehicle_images(vehicle_id):
    """Get all images for a vehicle"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM vehicle_images 
            WHERE vehicle_id = %s 
            ORDER BY is_primary DESC, sort_order ASC
        """, (vehicle_id,))
        images = cursor.fetchall()
        
        # Also get primary image from vehicles table
        cursor.execute("SELECT primary_image FROM vehicles WHERE id = %s", (vehicle_id,))
        vehicle = cursor.fetchone()
        
        return jsonify({
            'images': images,
            'primary_image': vehicle['primary_image'] if vehicle else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/vehicle-images/<int:image_id>', methods=['DELETE'])
@admin_required
def api_delete_vehicle_image(image_id):
    """Delete vehicle image"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Get image path
        cursor.execute("SELECT image_path FROM vehicle_images WHERE id = %s", (image_id,))
        image = cursor.fetchone()
        
        if image:
            # Delete file from filesystem
            file_path = image['image_path'].lstrip('/')
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete from database
            cursor.execute("DELETE FROM vehicle_images WHERE id = %s", (image_id,))
            conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - USERS
# ============================================================================

@admin_bp.route('/api/users')
@admin_required
def api_get_users():
    """Get all users"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, first_name, last_name, email, phone, address, city, state,
                   postal_code, country, role, is_active, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        return jsonify(users)
    except Exception as e:
        print(f"Error getting users: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/users', methods=['POST'])
@admin_required
def api_create_user():
    """Create new user"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (data.get('email'),))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Email already exists'}), 400
        
        password = data.get('password')
        if not password:
            return jsonify({'success': False, 'message': 'Password is required'}), 400
        hashed_password = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, password, phone, address, city, state,
                              postal_code, country, role, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            data.get('first_name'),
            data.get('last_name'),
            data.get('email'),
            hashed_password,
            data.get('phone', ''),
            data.get('address', ''),
            data.get('city', ''),
            data.get('state', ''),
            data.get('postal_code', ''),
            data.get('country', 'USA'),
            data.get('role', 'user'),
            data.get('is_active', 1)
        ))
        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/users/<int:user_id>')
@admin_required
def api_get_user(user_id):
    """Get single user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, first_name, last_name, email, phone, address, city, state,
                   postal_code, country, role, is_active, created_at
            FROM users
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if user:
            return jsonify(user)
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def api_update_user(user_id):
    """Update user"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        # Update password if provided
        if data.get('password'):
            hashed_password = generate_password_hash(data['password'])
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
        
        cursor.execute("""
            UPDATE users 
            SET first_name = %s, last_name = %s, email = %s, phone = %s,
                address = %s, city = %s, state = %s, postal_code = %s, country = %s,
                role = %s, is_active = %s
            WHERE id = %s
        """, (
            data.get('first_name'),
            data.get('last_name'),
            data.get('email'),
            data.get('phone', ''),
            data.get('address', ''),
            data.get('city', ''),
            data.get('state', ''),
            data.get('postal_code', ''),
            data.get('country', ''),
            data.get('role', 'user'),
            data.get('is_active', 1),
            user_id
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def api_delete_user(user_id):
    """Delete user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - BOOKINGS
# ============================================================================

@admin_bp.route('/api/bookings')
@admin_required
def api_get_bookings():
    """Get all bookings"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   u.email as user_email,
                   u.phone as user_phone,
                   v.model, v.license_plate, vb.name as brand_name
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY b.created_at DESC
        """)
        bookings = cursor.fetchall()
        return jsonify(bookings)
    except Exception as e:
        print(f"Error getting bookings: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/bookings/<int:booking_id>', methods=['PUT'])
@admin_required
def api_update_booking(booking_id):
    """Update booking status"""
    data = request.get_json()
    new_status = data.get('status')
    
    if not new_status:
        return jsonify({'success': False, 'message': 'Status is required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        # Fetch booking's user_id
        cursor.execute("SELECT user_id FROM bookings WHERE id = %s", (booking_id,))
        booking = cursor.fetchone()
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found'}), 404
        user_id = booking[0]
        
        # Update booking status
        cursor.execute("""
            UPDATE bookings 
            SET status = %s
            WHERE id = %s
        """, (new_status, booking_id))
        
        # Create user notification for active/completed status
        if new_status in ('active', 'completed'):
            title = f"Booking {new_status.capitalize()}"
            message = f"Your booking #{booking_id} status has been updated to {new_status}."
            cursor.execute("""
                INSERT INTO notifications (user_id, type, title, message, link, is_read, created_at)
                VALUES (%s, 'status_update', %s, %s, '/user/bookings', 0, NOW())
            """, (user_id, title, message))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================`r`n# API ROUTES - CONTACT QUERIES
# ============================================================================

@admin_bp.route('/api/queries')
@admin_required
def api_get_queries():
    """Get all contact queries"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT q.*, CONCAT(u.first_name, ' ', u.last_name) as user_name
            FROM contact_queries q
            LEFT JOIN users u ON q.user_id = u.id
            ORDER BY q.created_at DESC
        """)
        queries = cursor.fetchall()
        return jsonify(queries)
    except Exception as e:
        print(f"Error getting queries: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/queries/<int:query_id>/reply', methods=['POST'])
@admin_required
def api_reply_query(query_id):
    """Reply to contact query"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE contact_queries 
            SET status = 'replied', replied_by = %s, reply_message = %s, replied_at = NOW()
            WHERE id = %s
        """, (session['user_id'], data.get('reply_message'), query_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/queries/<int:query_id>', methods=['DELETE'])
@admin_required
def api_delete_query(query_id):
    """Delete contact query"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM contact_queries WHERE id = %s", (query_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - SUBSCRIBERS
# ============================================================================

@admin_bp.route('/api/subscribers')
@admin_required
def api_get_subscribers():
    """Get all subscribers"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM subscribers
            ORDER BY subscribed_at DESC
        """)
        subscribers = cursor.fetchall()
        return jsonify(subscribers)
    except Exception as e:
        print(f"Error getting subscribers: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/subscribers', methods=['POST'])
@admin_required
def api_create_subscriber():
    """Add subscriber manually"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subscribers (email, is_active, subscribed_at)
            VALUES (%s, 1, NOW())
        """, (data.get('email'),))
        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/subscribers/<int:subscriber_id>', methods=['DELETE'])
@admin_required
def api_delete_subscriber(subscriber_id):
    """Delete subscriber"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM subscribers WHERE id = %s", (subscriber_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - PAGE CONTENT
# ============================================================================

@admin_bp.route('/api/page-content')
@admin_required
def api_get_page_content():
    """Get all page content"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM page_contents
            ORDER BY page_name, order_position
        """)
        content = cursor.fetchall()
        return jsonify(content)
    except Exception as e:
        print(f"Error getting page content: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/page-content', methods=['POST'])
@admin_required
def api_create_page_content():
    """Create new page content"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        # Check if section key already exists for this page
        cursor.execute("""
            SELECT id FROM page_contents 
            WHERE page_name = %s AND section_key = %s
        """, (data.get('page_name'), data.get('section_key')))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Section key already exists for this page'}), 400
        
        cursor.execute("""
            INSERT INTO page_contents (
                page_name, section_key, title, content, image_url, 
                order_position, updated_by, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            data.get('page_name'),
            data.get('section_key'),
            data.get('title'),
            data.get('content'),
            data.get('image_url'),
            data.get('order_position', 0),
            session['user_id']
        ))
        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/page-content/<int:content_id>', methods=['PUT'])
@admin_required
def api_update_page_content(content_id):
    """Update page content"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE page_contents 
            SET title = %s, content = %s, image_url = %s, updated_by = %s, updated_at = NOW()
            WHERE id = %s
        """, (
            data.get('title'),
            data.get('content'),
            data.get('image_url'),
            session['user_id'],
            content_id
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/page-content/<int:content_id>', methods=['DELETE'])
@admin_required
def api_delete_page_content(content_id):
    """Delete page content"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM page_contents WHERE id = %s", (content_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/page-content/<int:section_id>/order', methods=['PUT'])
@admin_required
def api_update_section_order(section_id):
    """Update section order"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE page_contents 
            SET order_position = %s, updated_by = %s, updated_at = NOW()
            WHERE id = %s
        """, (data.get('order_position', 0), session['user_id'], section_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - CONTACT DETAILS
# ============================================================================

@admin_bp.route('/api/contact-details')
@admin_required
def api_get_contact_details():
    """Get all contact details"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM contact_details
            ORDER BY order_position
        """)
        details = cursor.fetchall()
        return jsonify(details)
    except Exception as e:
        print(f"Error getting contact details: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/contact-details', methods=['POST'])
@admin_required
def api_create_contact_detail():
    """Create new contact detail"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO contact_details (contact_type, label, value, icon, order_position, is_active, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('contact_type'),
            data.get('label'),
            data.get('value'),
            data.get('icon'),
            data.get('order_position', 0),
            data.get('is_active', 1),
            session['user_id']
        ))
        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/contact-details/<int:detail_id>', methods=['PUT'])
@admin_required
def api_update_contact_detail(detail_id):
    """Update contact detail"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE contact_details 
            SET label = %s, value = %s, icon = %s, order_position = %s, is_active = %s, updated_by = %s
            WHERE id = %s
        """, (
            data.get('label'),
            data.get('value'),
            data.get('icon'),
            data.get('order_position', 0),
            data.get('is_active', 1),
            session['user_id'],
            detail_id
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/contact-details/<int:detail_id>', methods=['DELETE'])
@admin_required
def api_delete_contact_detail(detail_id):
    """Delete contact detail"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM contact_details WHERE id = %s", (detail_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - VERIFICATIONS
# ============================================================================

@admin_bp.route('/api/verifications')
@admin_required
def api_get_verifications():
    """Get all verification requests"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT v.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   u.email, u.phone
            FROM verifications v
            JOIN users u ON v.user_id = u.id
            ORDER BY v.created_at DESC
        """)
        verifications = cursor.fetchall()
        return jsonify(verifications)
    except Exception as e:
        print(f"Error getting verifications: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/verifications/<int:verification_id>/approve', methods=['POST'])
@admin_required
def api_approve_verification(verification_id):
    """Approve verification request"""
    data = request.get_json() if request.is_json else {}
    manual_expiry = data.get('manual_expiry')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get user details from verification
        cursor.execute("""
            SELECT v.user_id, u.email, u.first_name 
            FROM verifications v 
            JOIN users u ON v.user_id = u.id 
            WHERE v.id = %s
        """, (verification_id,))
        result = cursor.fetchone()
        user_id = result['user_id'] if result else None
        user = result if result else None
        
        # Build update query based on whether manual_expiry is provided
        if manual_expiry:
            cursor.execute("""
                UPDATE verifications 
                SET verification_status = 'approved', verified_by = %s, verified_at = NOW(),
                    ocr_extracted_expiry = %s, updated_at = NOW()
                WHERE id = %s
            """, (session['user_id'], manual_expiry, verification_id))
        else:
            cursor.execute("""
                UPDATE verifications 
                SET verification_status = 'approved', verified_by = %s, verified_at = NOW()
                WHERE id = %s
            """, (session['user_id'], verification_id))
        
        # Create notification for user
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, link, created_at)
            VALUES (%s, 'verification', 'Verification Approved', 
                    'Your identity verification has been approved! You can now book vehicles.',
                    '/user/dashboard', NOW())
        """, (user_id,))
        
        conn.commit()
        
        # Send approval email
        if user:
            try:
                EmailService.send_verification_approved(user)
                print(f"📧 Verification approved email sent to {user['email']}")
            except Exception as e:
                print(f"⚠️ Failed to send verification email: {e}")
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/verifications/<int:verification_id>/reject', methods=['POST'])
@admin_required
def api_reject_verification(verification_id):
    """Reject verification request"""
    data = request.get_json()
    reason = data.get('reason', '')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get user details from verification
        cursor.execute("""
            SELECT v.user_id, u.email, u.first_name 
            FROM verifications v 
            JOIN users u ON v.user_id = u.id 
            WHERE v.id = %s
        """, (verification_id,))
        result = cursor.fetchone()
        user_id = result['user_id'] if result else None
        user = result if result else None
        
        # Update verification status
        cursor.execute("""
            UPDATE verifications 
            SET verification_status = 'rejected', rejection_reason = %s, verified_by = %s, verified_at = NOW()
            WHERE id = %s
        """, (reason, session['user_id'], verification_id))
        
        # Create notification for user
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, link, created_at)
            VALUES (%s, 'verification', 'Verification Rejected', 
                    CONCAT('Your identity verification was rejected. Reason: ', %s, '. Please resubmit.'),
                    '/user/verification', NOW())
        """, (user_id, reason))
        
        conn.commit()
        
        # Send rejection email
        if user:
            try:
                EmailService.send_verification_rejected(user, reason)
                print(f"📧 Verification rejected email sent to {user['email']}")
            except Exception as e:
                print(f"⚠️ Failed to send verification email: {e}")
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/verifications/<int:verification_id>/rescan', methods=['POST'])
@admin_required
def api_rescan_verification(verification_id):
    """Re-run OCR with enhanced preprocessing on stored images"""
    from MyFlaskApp.utils.ocr_service import LicenseOCRService
    import os
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get verification record
        cursor.execute("""
            SELECT v.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   u.email, u.phone
            FROM verifications v
            JOIN users u ON v.user_id = u.id
            WHERE v.id = %s
        """, (verification_id,))
        
        verification = cursor.fetchone()
        
        if not verification:
            return jsonify({'success': False, 'message': 'Verification not found'}), 404
        
        # Get upload folder from config
        upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'MyFlaskApp', 'base', 'uploads', 'verifications')
        
        # Process license front image
        ocr_result_license = {'confidence': 0, 'extracted_license': None, 'extracted_expiry': None}
        if verification.get('license_front_image'):
            license_path = os.path.join(upload_folder, verification['license_front_image'])
            if os.path.exists(license_path):
                result = LicenseOCRService.extract_license_info(license_path)
                if result:
                    ocr_result_license = result
        
        # Process ID card image
        ocr_result_id = {'confidence': 0, 'extracted_id': None}
        if verification.get('id_card_image'):
            id_path = os.path.join(upload_folder, verification['id_card_image'])
            if os.path.exists(id_path):
                result = LicenseOCRService.extract_license_info(id_path)
                if result:
                    ocr_result_id = result
        
        # Use the better of the two results (higher confidence)
        best_confidence = max(ocr_result_license.get('confidence', 0), ocr_result_id.get('confidence', 0))
        extracted_license = ocr_result_license.get('extracted_license') or ocr_result_id.get('extracted_id')
        extracted_expiry = ocr_result_license.get('extracted_expiry')
        
        # Update the verification record with new OCR results
        cursor.execute("""
            UPDATE verifications 
            SET ocr_confidence_score = %s,
                ocr_extracted_license = %s,
                ocr_extracted_expiry = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (best_confidence, extracted_license, extracted_expiry, verification_id))
        
        conn.commit()
        
        print(f"[ADMIN] Re-scan completed for verification {verification_id}")
        print(f"  - New confidence: {best_confidence:.2%}")
        print(f"  - Extracted license: {extracted_license}")
        print(f"  - Extracted expiry: {extracted_expiry}")
        
        return jsonify({
            'success': True,
            'new_confidence': best_confidence,
            'extracted_license': extracted_license,
            'extracted_expiry': extracted_expiry
        })
        
    except Exception as e:
        conn.rollback()
        print(f"[ADMIN] Re-scan error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - EXTENSION REQUESTS
# ============================================================================

@admin_bp.route('/api/extensions')
@admin_required
def api_get_extensions():
    """Get all extension requests"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT er.*, 
                   CONCAT(u.first_name, ' ', u.last_name) as user_name,
                   b.booking_reference, v.model, vb.name as brand_name
            FROM extension_requests er
            JOIN users u ON er.user_id = u.id
            JOIN bookings b ON er.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY er.created_at DESC
        """)
        extensions = cursor.fetchall()
        return jsonify(extensions)
    except Exception as e:
        print(f"Error getting extensions: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/extensions/<int:extension_id>/approve', methods=['POST'])
@admin_required
def api_approve_extension(extension_id):
    """Approve extension request"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        # Get extension details
        cursor.execute("""
            SELECT booking_id, requested_new_end_date, additional_fee 
            FROM extension_requests 
            WHERE id = %s
        """, (extension_id,))
        extension = cursor.fetchone()
        
        if not extension:
            return jsonify({'success': False, 'message': 'Extension not found'}), 404
        
        booking_id = extension[0]
        new_end_date = extension[1]
        additional_fee = extension[2]
        
        # Update booking end date
        cursor.execute("""
            UPDATE bookings 
            SET end_date = %s, total_amount = total_amount + %s
            WHERE id = %s
        """, (new_end_date, additional_fee, booking_id))
        
        # Update extension status
        cursor.execute("""
            UPDATE extension_requests 
            SET status = 'approved', approved_by = %s, approved_at = NOW()
            WHERE id = %s
        """, (session['user_id'], extension_id))
        
        conn.commit()
        
        # Create notification for user
        cursor.execute("SELECT user_id FROM bookings WHERE id = %s", (booking_id,))
        result = cursor.fetchone()
        user_id = result[0] if result else None
        
        if user_id:
            cursor.execute("""
                INSERT INTO notifications (user_id, type, title, message, link, created_at)
                VALUES (%s, 'system', 'Extension Approved', 
                        CONCAT('Your rental extension request has been approved. New return date: ', DATE(%s)),
                        '/user/active-rentals', NOW())
            """, (user_id, new_end_date))
            conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/extensions/<int:extension_id>/reject', methods=['POST'])
@admin_required
def api_reject_extension(extension_id):
    """Reject extension request"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        # Get booking_id
        cursor.execute("SELECT booking_id FROM extension_requests WHERE id = %s", (extension_id,))
        result = cursor.fetchone()
        booking_id = result[0] if result else None
        
        # Update extension status
        cursor.execute("""
            UPDATE extension_requests 
            SET status = 'rejected', approved_by = %s, approved_at = NOW()
            WHERE id = %s
        """, (session['user_id'], extension_id))
        conn.commit()
        
        # Create notification for user
        if booking_id:
            cursor.execute("SELECT user_id FROM bookings WHERE id = %s", (booking_id,))
            result = cursor.fetchone()
            user_id = result[0] if result else None
            
            if user_id:
                cursor.execute("""
                    INSERT INTO notifications (user_id, type, title, message, link, created_at)
                    VALUES (%s, 'system', 'Extension Rejected', 
                            'Your rental extension request has been rejected. Please return the vehicle on time.',
                            '/user/active-rentals', NOW())
                """, (user_id,))
                conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# API ROUTES - ANALYTICS
# ============================================================================

@admin_bp.route('/api/analytics/vehicle-usage')
@admin_required
def api_vehicle_usage():
    """Get vehicle usage statistics"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT brand, model, total_bookings, usage_rate
            FROM vehicle_usage_rate
            WHERE total_bookings > 0
            ORDER BY usage_rate DESC
            LIMIT 10
        """)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/analytics/most-rented')
@admin_required
def api_most_rented():
    """Get most rented vehicles"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT brand, model, rental_count, total_revenue, avg_rental_days
            FROM most_rented_vehicles
            LIMIT 10
        """)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/analytics/revenue')
@admin_required
def api_revenue_analytics():
    """Get revenue analytics"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT period, rental_revenue, fine_revenue, total_revenue, total_bookings
            FROM revenue_analytics
            ORDER BY period DESC
            LIMIT 12
        """)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/analytics/daily-bookings')
@admin_required
def api_daily_bookings():
    """Get daily booking summary"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT booking_date, total_bookings, confirmed, active, completed, cancelled, total_revenue
            FROM daily_booking_summary
            ORDER BY booking_date DESC
            LIMIT 30
        """)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/analytics/customer-lifetime')
@admin_required
def api_customer_lifetime():
    """Get customer lifetime value"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT customer_name, email, total_bookings, total_spent, avg_booking_value
            FROM customer_lifetime_value
            WHERE total_bookings > 0
            ORDER BY total_spent DESC
            LIMIT 10
        """)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/analytics/fleet-performance')
@admin_required
def api_fleet_performance():
    """Get fleet performance metrics"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT brand, model, total_rentals, avg_rental_days, total_revenue, revenue_per_day
            FROM fleet_performance
            WHERE total_rentals > 0
            ORDER BY total_revenue DESC
            LIMIT 10
        """)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/analytics/monthly-summary')
@admin_required
def api_monthly_summary():
    """Get monthly summary for current year"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                MONTH(created_at) as month,
                COUNT(*) as total_bookings,
                SUM(total_amount) as revenue,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
            FROM bookings
            WHERE YEAR(created_at) = YEAR(CURDATE())
            GROUP BY MONTH(created_at)
            ORDER BY month ASC
        """)
        data = cursor.fetchall()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


def _admin_notification_target_link(link):
    """Validate and return safe notification link for admin."""
    if not link:
        return url_for('admin_bp.admin_notifications')
    
    # Only allow internal admin links
    allowed_prefixes = ['/admin/', '/static/']
    if any(link.startswith(prefix) for prefix in allowed_prefixes):
        return link
    
    return url_for('admin_bp.admin_notifications')


@admin_bp.route('/notifications')
@admin_required
def admin_notifications():
    """Display admin's notification inbox."""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template(
            'admin_notifications.html',
            notifications=[],
            session=session,
            csrf_token_value=generate_csrf_token()
        )
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Admin sees: system, verification, maintenance notifications
        cursor.execute("""
            SELECT id, title, message, is_read, created_at, link, type
            FROM notifications
            WHERE user_id = %s
            AND type IN ('system', 'verification', 'maintenance')
            ORDER BY created_at DESC
            LIMIT 50
        """, (session['user_id'],))
        notifications_list = cursor.fetchall()
        
        return render_template(
            'admin_notifications.html',
            notifications=notifications_list,
            session=session,
            csrf_token_value=generate_csrf_token()
        )
    except Exception as e:
        print(f"Admin notifications error: {e}")
        flash('Error loading notifications', 'error')
        return render_template(
            'admin_notifications.html',
            notifications=[],
            session=session,
            csrf_token_value=generate_csrf_token()
        )
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/notifications/<int:notification_id>/open')
@admin_required
def admin_open_notification(notification_id):
    """Open a notification target and mark it as read."""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_bp.admin_notifications'))
    
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
            return redirect(url_for('admin_bp.admin_notifications'))
        
        if not notification['is_read']:
            cursor.execute("""
                UPDATE notifications
                SET is_read = TRUE, read_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (notification_id, session['user_id']))
            conn.commit()
        
        return redirect(_admin_notification_target_link(notification.get('link')))
    except Exception as e:
        print(f"Open admin notification error: {e}")
        flash('Error opening notification', 'error')
        return redirect(url_for('admin_bp.admin_notifications'))
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/notifications/read-all', methods=['POST'])
@admin_required
def admin_mark_all_notifications_read():
    """Mark all admin notifications as read."""
    # Validate CSRF token
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    valid, error = validate_csrf_token(token)
    if not valid:
        flash(error, 'error')
        return redirect(url_for('admin_bp.admin_notifications'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin_bp.admin_notifications'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE notifications
            SET is_read = TRUE, read_at = NOW()
            WHERE user_id = %s AND is_read = FALSE
            AND type IN ('system', 'verification', 'maintenance')
        """, (session['user_id'],))
        conn.commit()
        flash('All notifications marked as read', 'success')
        return redirect(url_for('admin_bp.admin_notifications'))
    except Exception as e:
        conn.rollback()
        print(f"Mark all admin notifications read error: {e}")
        flash('Error updating notifications', 'error')
        return redirect(url_for('admin_bp.admin_notifications'))
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/vehicles/<int:vehicle_id>/set-primary', methods=['POST'])
@admin_required
def api_set_primary_image(vehicle_id):
    """Set a vehicle's primary image"""
    data = request.get_json()
    image_path = data.get('image_path')
    
    if not image_path:
        return jsonify({'success': False, 'message': 'No image path provided'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE vehicles SET primary_image = %s WHERE id = %s", 
                      (image_path, vehicle_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/api/vehicle-images/delete-by-path', methods=['DELETE'])
@admin_required
def api_delete_vehicle_image_by_path():
    """Delete vehicle image by path"""
    data = request.get_json()
    image_path = data.get('image_path')
    
    if not image_path:
        return jsonify({'success': False, 'message': 'No image path provided'}), 400
    
    # Remove from filesystem
    file_path = image_path.lstrip('/')
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error removing file {file_path}: {e}")
    
    # Remove from vehicles table if it's the primary image
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE vehicles SET primary_image = NULL WHERE primary_image = %s", (image_path,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
