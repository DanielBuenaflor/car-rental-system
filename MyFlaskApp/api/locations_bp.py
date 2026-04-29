from flask import Blueprint, jsonify, request
from MyFlaskApp import get_db_connection

locations_bp = Blueprint('locations_bp', __name__)


# ========== PUBLIC LOCATION ENDPOINTS ==========

@locations_bp.route('/api/locations', methods=['GET'])
def get_locations():
    """Get all active rental locations"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, name, address, latitude, longitude, branch_type, 
                   operating_hours, contact_phone, is_active
            FROM rental_locations
            WHERE is_active = TRUE
            ORDER BY branch_type, name
        """)
        locations = cursor.fetchall()
        return jsonify({'locations': locations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@locations_bp.route('/api/locations/<int:location_id>', methods=['GET'])
def get_location(location_id):
    """Get single location details"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, name, address, latitude, longitude, branch_type, 
                   operating_hours, contact_phone, is_active
            FROM rental_locations
            WHERE id = %s AND is_active = TRUE
        """, (location_id,))
        location = cursor.fetchone()
        
        if not location:
            return jsonify({'error': 'Location not found'}), 404
            
        return jsonify({'location': location})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@locations_bp.route('/api/locations/pricing', methods=['POST'])
def get_location_pricing():
    """Calculate pricing between two locations (for one-way fees)"""
    data = request.get_json()
    from_location_id = data.get('from_location_id')
    to_location_id = data.get('to_location_id')
    
    if not from_location_id or not to_location_id:
        return jsonify({'error': 'Both from_location_id and to_location_id are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if same location (no fee)
        if from_location_id == to_location_id:
            return jsonify({
                'one_way_fee': 0,
                'same_location': True
            })
        
        # Look for specific route pricing
        cursor.execute("""
            SELECT fee_amount FROM location_pricing
            WHERE from_location_id = %s AND to_location_id = %s
        """, (from_location_id, to_location_id))
        pricing = cursor.fetchone()
        
        if pricing:
            return jsonify({
                'one_way_fee': float(pricing['fee_amount']),
                'same_location': False
            })
        
        # If no specific pricing found, return 0 (can be configured later)
        return jsonify({
            'one_way_fee': 0,
            'same_location': False,
            'note': 'No specific pricing configured'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ========== GPS TRACKING ENDPOINTS ==========

@locations_bp.route('/api/vehicles/<int:vehicle_id>/location', methods=['GET'])
def get_vehicle_location(vehicle_id):
    """Get vehicle's current location"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, model, license_plate, current_lat, current_lng, 
                   last_location_update, gps_device_id, status
            FROM vehicles
            WHERE id = %s
        """, (vehicle_id,))
        vehicle = cursor.fetchone()
        
        if not vehicle:
            return jsonify({'error': 'Vehicle not found'}), 404
        
        return jsonify({
            'vehicle_id': vehicle['id'],
            'model': vehicle['model'],
            'license_plate': vehicle['license_plate'],
            'latitude': vehicle['current_lat'],
            'longitude': vehicle['current_lng'],
            'last_update': vehicle['last_location_update'],
            'status': vehicle['status']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@locations_bp.route('/api/vehicles/<int:vehicle_id>/tracking', methods=['GET'])
def get_vehicle_tracking_history(vehicle_id):
    """Get vehicle location history"""
    limit = request.args.get('limit', 50, type=int)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, latitude, longitude, speed_kmh, heading, 
                   location_address, recorded_at
            FROM vehicle_location_history
            WHERE vehicle_id = %s
            ORDER BY recorded_at DESC
            LIMIT %s
        """, (vehicle_id, limit))
        history = cursor.fetchall()
        
        return jsonify({
            'vehicle_id': vehicle_id,
            'history': history
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@locations_bp.route('/api/gps/update', methods=['POST'])
def update_gps_location():
    """Update vehicle GPS location - for GPS device integration"""
    data = request.get_json()
    
    vehicle_id = data.get('vehicle_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    speed = data.get('speed_kmh')
    heading = data.get('heading')
    address = data.get('location_address')
    
    if not all([vehicle_id, latitude, longitude]):
        return jsonify({'error': 'vehicle_id, latitude, and longitude are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Update vehicle's current location
        cursor.execute("""
            UPDATE vehicles 
            SET current_lat = %s, 
                current_lng = %s, 
                last_location_update = NOW()
            WHERE id = %s
        """, (latitude, longitude, vehicle_id))
        
        # Insert into location history
        cursor.execute("""
            INSERT INTO vehicle_location_history 
            (vehicle_id, latitude, longitude, speed_kmh, heading, location_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (vehicle_id, latitude, longitude, speed, heading, address))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Location updated successfully',
            'vehicle_id': vehicle_id
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@locations_bp.route('/api/gps/simulate', methods=['POST'])
def simulate_gps_update():
    """Simulate GPS update for testing - accepts manual coordinates"""
    data = request.get_json()
    
    vehicle_id = data.get('vehicle_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if not all([vehicle_id, latitude, longitude]):
        return jsonify({'error': 'vehicle_id, latitude, and longitude are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Update vehicle's current location
        cursor.execute("""
            UPDATE vehicles 
            SET current_lat = %s, 
                current_lng = %s, 
                last_location_update = NOW()
            WHERE id = %s
        """, (latitude, longitude, vehicle_id))
        
        # Insert into location history
        cursor.execute("""
            INSERT INTO vehicle_location_history 
            (vehicle_id, latitude, longitude, speed_kmh, heading, location_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (vehicle_id, latitude, longitude, 0, 0, 'Manual simulation'))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Simulated location updated',
            'vehicle_id': vehicle_id,
            'location': {'lat': latitude, 'lng': longitude}
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ========== ACTIVE RENTAL TRACKING ==========

@locations_bp.route('/api/rentals/active/locations', methods=['GET'])
def get_active_rental_locations():
    """Get all currently rented vehicle locations (for admin map)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT v.id as vehicle_id, v.model, v.license_plate, v.color,
                   v.current_lat, v.current_lng, v.last_location_update,
                   v.status as vehicle_status,
                   b.id as booking_id, b.start_date, b.end_date,
                   CONCAT(u.first_name, ' ', u.last_name) as customer_name,
                   u.phone as customer_phone
            FROM vehicles v
            JOIN bookings b ON v.id = b.vehicle_id
            JOIN users u ON b.user_id = u.id
            WHERE b.status = 'active'
            ORDER BY v.id
        """)
        rentals = cursor.fetchall()
        
        return jsonify({'active_rentals': rentals})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@locations_bp.route('/api/rentals/<int:booking_id>/track', methods=['GET'])
def track_rental(booking_id):
    """Track a specific rental - for user's active booking"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.id, b.start_date, b.end_date, b.pickup_location, b.return_location,
                   b.status as booking_status,
                   v.id as vehicle_id, v.model, v.license_plate, v.color,
                   v.current_lat, v.current_lng, v.last_location_update
            FROM bookings b
            JOIN vehicles v ON b.vehicle_id = v.id
            WHERE b.id = %s AND b.status = 'active'
        """, (booking_id,))
        rental = cursor.fetchone()
        
        if not rental:
            return jsonify({'error': 'Active rental not found'}), 404
        
        return jsonify({'rental': rental})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()