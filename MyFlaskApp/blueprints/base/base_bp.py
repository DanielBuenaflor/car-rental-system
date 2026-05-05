from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for, flash, current_app
from MyFlaskApp import get_db_connection

# Create blueprint for base/public routes
base_bp = Blueprint('base_bp', __name__,
                    template_folder='templates',
                    static_folder='static',
                    static_url_path='/base_static')


# ========== PUBLIC ROUTES ==========

@base_bp.route('/')
def index():
    """Home page - Redirect admin to dashboard"""
    if session.get('loggedin') and session.get('role') == 'admin':
        return redirect(url_for('admin_bp.admin_dashboard'))

    conn = get_db_connection()
    if not conn:
        return render_template('base/templates/base.html', all_vehicles=[], testimonials=[], session=session)

    cursor = conn.cursor(dictionary=True)
    try:
        # Get ALL available vehicles
        cursor.execute("""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.status = 'available'
            ORDER BY vb.name, v.model
        """)
        all_vehicles = cursor.fetchall()

        # Get testimonials with vehicle info
        cursor.execute("""
            SELECT t.*, CONCAT(u.first_name, ' ', u.last_name) as name,
                   v.brand_id, vb.name as brand_name, v.model
            FROM testimonials t
            JOIN users u ON t.user_id = u.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            LEFT JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY t.created_at DESC
            LIMIT 3
        """)
        testimonials = cursor.fetchall()

        return render_template('base/templates/base.html',
                               all_vehicles=all_vehicles,
                               testimonials=testimonials,
                               session=session)
    except Exception as e:
        current_app.logger.error(f"Home page error: {e}")
        return render_template('base/templates/base.html', all_vehicles=[], testimonials=[], session=session)
    finally:
        cursor.close()
        conn.close()

@base_bp.route('/fleet')
def browse_fleet():
    """Browse available vehicles - Admin cannot access"""
    # If admin is logged in, redirect to admin dashboard
    if session.get('loggedin') and session.get('role') == 'admin':
        flash('Admin accounts cannot browse vehicles', 'info')
        return redirect(url_for('admin_bp.admin_dashboard'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('base/templates/fleet.html', vehicles=[], brands=[], session=session)

    cursor = conn.cursor(dictionary=True)
    try:
        # Get all available vehicles with brand info
        cursor.execute("""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.status = 'available'
            ORDER BY vb.name, v.model
        """)
        vehicles = cursor.fetchall()

        # Get all brands for filter
        cursor.execute("SELECT * FROM vehicle_brands ORDER BY name")
        brands = cursor.fetchall()

        return render_template('base/templates/fleet.html',
                               vehicles=vehicles,
                               brands=brands,
                               session=session)
    except Exception as e:
        current_app.logger.error(f"Fleet page error: {e}")
        flash('Error loading vehicles', 'error')
        return render_template('base/templates/fleet.html', vehicles=[], brands=[], session=session)
    finally:
        cursor.close()
        conn.close()

@base_bp.route('/testimonials')
def testimonials():
    """View testimonials - Admin can view all, users see approved only"""
    # Get page number for pagination
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    conn = get_db_connection()
    if not conn:
        return render_template('base/templates/testimonials.html', testimonials=[], session=session)
    
    cursor = conn.cursor(dictionary=True)
    try:
        is_admin = session.get('loggedin') and session.get('role') == 'admin'
        
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM testimonials")
        total_result = cursor.fetchone()
        total_testimonials = total_result['total'] if total_result else 0
        
        # Calculate pagination
        total_pages = (total_testimonials + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get paginated testimonials
        cursor.execute("""
            SELECT t.*, CONCAT(u.first_name, ' ', u.last_name) as name,
                   v.brand_id, vb.name as brand_name, v.model
            FROM testimonials t
            JOIN users u ON t.user_id = u.id
            LEFT JOIN vehicles v ON t.vehicle_id = v.id
            LEFT JOIN vehicle_brands vb ON v.brand_id = vb.id
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        testimonials = cursor.fetchall()
        
        # Get user's testimonial count (if logged in and not admin)
        user_testimonial_count = 0
        if session.get('loggedin') and not is_admin:
            cursor.execute("""
                SELECT COUNT(*) as count FROM testimonials
                WHERE user_id = %s
            """, (session['user_id'],))
            count_result = cursor.fetchone()
            user_testimonial_count = count_result['count'] if count_result else 0
        
        return render_template('base/templates/testimonials.html', 
                               testimonials=testimonials,
                               user_testimonial_count=user_testimonial_count,
                               current_page=page,
                               total_pages=total_pages,
                               session=session)
    except Exception as e:
        print(f"Error loading testimonials: {e}")
        return render_template('base/templates/testimonials.html', testimonials=[], session=session)
    finally:
        cursor.close()
        conn.close()


@base_bp.route('/terms')
def terms():
    """Terms and Conditions page"""
    return render_template('terms.html', session=session)


@base_bp.route('/privacy')
def privacy():
    """Privacy Policy page"""
    return render_template('privacy.html', session=session)


@base_bp.route('/api/vehicles/filter', methods=['POST'])
def filter_vehicles():
    """API endpoint for filtering vehicles"""
    data = request.get_json()

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # Build query with filters
        query = """
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.status = 'available'
        """
        params = []

        # Search by brand/model
        if data.get('search'):
            query += " AND (vb.name LIKE %s OR v.model LIKE %s)"
            search_term = f"%{data['search']}%"
            params.extend([search_term, search_term])

        # Filter by transmission
        if data.get('transmission'):
            query += " AND v.transmission = %s"
            params.append(data['transmission'])

        # Filter by fuel type
        if data.get('fuel_type'):
            query += " AND v.fuel_type = %s"
            params.append(data['fuel_type'])

        # Filter by seating capacity
        if data.get('seating_capacity'):
            seats = int(data['seating_capacity'])
            if seats >= 7:
                query += " AND v.seating_capacity >= %s"
            else:
                query += " AND v.seating_capacity = %s"
            params.append(seats)

        # Filter by price range
        if data.get('min_price'):
            query += " AND v.daily_rate >= %s"
            params.append(float(data['min_price']))

        if data.get('max_price'):
            query += " AND v.daily_rate <= %s"
            params.append(float(data['max_price']))

        # Filter by date availability
        if data.get('start_date') and data.get('end_date'):
            query += """ AND v.id NOT IN (
                SELECT vehicle_id FROM bookings
                WHERE status IN ('confirmed', 'active')
                AND (
                    (start_date BETWEEN %s AND %s)
                    OR (end_date BETWEEN %s AND %s)
                    OR (%s BETWEEN start_date AND end_date)
                    OR (%s BETWEEN start_date AND end_date)
                )
            )"""
            params.extend([
                data['start_date'], data['end_date'],
                data['start_date'], data['end_date'],
                data['start_date'], data['end_date']
            ])

        query += " ORDER BY vb.name, v.model"

        cursor.execute(query, params)
        vehicles = cursor.fetchall()

        return jsonify({'vehicles': vehicles})

    except Exception as e:
        print(f"Filter error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# GET VEHICLE REVIEWS
# ============================================================================
@base_bp.route('/api/vehicle/<int:vehicle_id>/reviews')
def api_vehicle_reviews(vehicle_id):
    """API endpoint to get testimonials for a specific vehicle"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT t.*, CONCAT(u.first_name, ' ', u.last_name) as user_name
            FROM testimonials t
            JOIN users u ON t.user_id = u.id
            WHERE t.vehicle_id = %s
            ORDER BY t.created_at DESC
            LIMIT 2
        """, (vehicle_id,))
        reviews = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'reviews': reviews
        })
    except Exception as e:
        print(f"Reviews error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# VEHICLE DETAILS ROUTE
# ============================================================================
@base_bp.route('/api/vehicle/<int:vehicle_id>')
def api_vehicle_detail(vehicle_id):
    """API endpoint for vehicle details"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database error'}), 500

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
            return jsonify({'success': False, 'error': 'Vehicle not found'}), 404

        # Get vehicle images
        cursor.execute("""
            SELECT * FROM vehicle_images
            WHERE vehicle_id = %s
            ORDER BY is_primary DESC, sort_order ASC
        """, (vehicle_id,))
        images = cursor.fetchall()

        # Get similar vehicles
        cursor.execute("""
            SELECT v.*, vb.name as brand_name
            FROM vehicles v
            JOIN vehicle_brands vb ON v.brand_id = vb.id
            WHERE v.id != %s AND v.status = 'available'
            AND (v.brand_id = %s OR v.fuel_type = %s)
            LIMIT 4
        """, (vehicle_id, vehicle['brand_id'], vehicle['fuel_type']))
        similar_vehicles = cursor.fetchall()

        # Get average rating from testimonials
        cursor.execute("""
            SELECT AVG(rating) as avg_rating, COUNT(*) as review_count
            FROM testimonials
            WHERE vehicle_id = %s
        """, (vehicle_id,))
        rating_data = cursor.fetchone()
        avg_rating = round(rating_data['avg_rating'], 1) if rating_data and rating_data['avg_rating'] else 0
        review_count = rating_data['review_count'] if rating_data and rating_data['review_count'] else 0

        return jsonify({
            'success': True,
            'vehicle': vehicle,
            'images': images,
            'similar_vehicles': similar_vehicles,
            'avg_rating': avg_rating,
            'review_count': review_count
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# CHECK VEHICLE AVAILABILITY
# ============================================================================
@base_bp.route('/api/vehicle/<int:vehicle_id>/check-availability')
def check_vehicle_availability(vehicle_id):
    """Check if vehicle is available for selected dates"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'available': False, 'message': 'Please select both dates'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check for overlapping bookings
        cursor.execute("""
            SELECT id, start_date, end_date, status 
            FROM bookings 
            WHERE vehicle_id = %s 
            AND status IN ('confirmed', 'active', 'pending')
            AND (
                (start_date BETWEEN %s AND %s)
                OR (end_date BETWEEN %s AND %s)
                OR (%s BETWEEN start_date AND end_date)
                OR (%s BETWEEN start_date AND end_date)
            )
        """, (vehicle_id, start_date, end_date, start_date, end_date, start_date, end_date))
        
        conflicts = cursor.fetchall()
        
        if conflicts:
            return jsonify({
                'available': False, 
                'message': 'Vehicle is already booked for these dates'
            })
        else:
            return jsonify({
                'available': True, 
                'message': 'Vehicle is available for these dates'
            })
    
    except Exception as e:
        print(f"Availability check error: {e}")
        return jsonify({'available': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# GET VEHICLE BOOKINGS (for calendar)
# ============================================================================
@base_bp.route('/api/vehicle/<int:vehicle_id>/bookings')
def get_vehicle_bookings(vehicle_id):
    """Get all bookings for a vehicle for the next N months"""
    from datetime import datetime, timedelta
    
    try:
        months = int(request.args.get('months', 1))
    except ValueError:
        months = 1
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Calculate date range (today to today + months)
        today = datetime.now().date()
        end_date = today + timedelta(days=months * 30)
        
        # Get all bookings for this vehicle in the date range
        cursor.execute("""
            SELECT id, start_date, end_date, status 
            FROM bookings 
            WHERE vehicle_id = %s 
            AND status IN ('confirmed', 'active', 'pending')
            AND (
                (start_date <= %s AND end_date >= %s)
                OR (start_date <= %s AND end_date >= %s)
                OR (start_date >= %s AND end_date <= %s)
            )
            ORDER BY start_date
        """, (vehicle_id, end_date, today, end_date, today, today, end_date))
        
        bookings = cursor.fetchall()
        
        # Convert to list of booked date ranges
        booked_dates = []
        for booking in bookings:
            start = booking['start_date'].date() if isinstance(booking['start_date'], datetime) else booking['start_date']
            end = booking['end_date'].date() if isinstance(booking['end_date'], datetime) else booking['end_date']
            
            # Generate all dates in the range
            current = start
            while current <= end:
                booked_dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
        
        # Generate all dates in the range
        all_dates = []
        current = today
        while current <= end_date:
            all_dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        # Available dates are those not in booked_dates
        available_dates = [d for d in all_dates if d not in booked_dates]
        
        return jsonify({
            'booked_dates': list(set(booked_dates)),
            'available_dates': available_dates,
            'range': {
                'start': today.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            }
        })
    
    except Exception as e:
        print(f"Get bookings error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()