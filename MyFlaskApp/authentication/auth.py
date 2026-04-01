# ============================================================================
# IMPORTS
# ============================================================================
from flask import (
    Blueprint, request, session, url_for, render_template,
    jsonify, redirect, current_app, flash
)
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import mysql.connector
import random
import string
import re

from MyFlaskApp import get_db_connection, mail


# ============================================================================
# BLUEPRINT CONFIGURATION
# ============================================================================
auth_bp = Blueprint(
    'auth_bp', 
    __name__, 
    template_folder='templates',
    static_folder='static', 
    static_url_path="/auth_statics"
)


# ============================================================================
# DECORATORS
# ============================================================================
def login_required(f):
    """Decorator to require user login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('loggedin'):
            flash('Please login to access this page', 'error')
            return redirect(url_for('auth_bp.login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def is_valid_email(email):
    """Validate email format using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def generate_otp():
    """Generate a 6-digit OTP code"""
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(email, otp_code, username):
    """Send verification email with OTP code"""
    try:
        msg = Message(
            subject="Your Verification Code - CarRental Pro",
            recipients=[email],
            html=f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Verification Code</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif;">
    <div style="max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd;">
        <h2>CarRental Pro - Account Verification</h2>
        <p>Hello <strong>{username}</strong>,</p>
        <p>Your verification code is:</p>
        <div style="padding: 15px; background-color: #f0f0f0; font-size: 24px; font-weight: bold; text-align: center;">
            {otp_code}
        </div>
        <p>This code is valid for 10 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
    </div>
</body>
</html>
            """
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        return False


# ============================================================================
# MAIN ROUTES
# ============================================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    # Get all vehicles for the base template
    conn = get_db_connection()
    all_vehicles = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT v.*, vb.name as brand_name 
                FROM vehicles v
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE v.status = 'available'
            """)
            all_vehicles = cursor.fetchall()
        except Exception as e:
            print(f"Error loading vehicles: {e}")
        finally:
            cursor.close()
            conn.close()
    
    if request.method == 'POST':
        # Check if it's JSON request or form data
        if request.is_json:
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
        else:
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            
        return handle_login(email, password)
    return render_template('login.html', session=session, all_vehicles=all_vehicles)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    # Get all vehicles for the base template
    conn = get_db_connection()
    all_vehicles = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT v.*, vb.name as brand_name 
                FROM vehicles v
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE v.status = 'available'
            """)
            all_vehicles = cursor.fetchall()
        except Exception as e:
            print(f"Error loading vehicles: {e}")
        finally:
            cursor.close()
            conn.close()
    
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
        
        return handle_signup(data)
    return render_template('register.html', session=session, all_vehicles=all_vehicles)


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP code"""
    data = request.get_json()
    otp_code = data.get('otp_code', '').strip()
    user_id = session.get('temp_user_id')
    
    if not otp_code or not user_id:
        return jsonify(success=False, message='Invalid verification request')
    
    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message='Database error')
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get OTP record
        cursor.execute("""
            SELECT id, otp_code, expires_at, is_verified
            FROM otp_verification
            WHERE user_id = %s AND is_verified = FALSE
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        otp_record = cursor.fetchone()
        
        if not otp_record:
            return jsonify(success=False, message='No pending verification found')
        
        # Check expiration
        if datetime.now() > otp_record['expires_at']:
            return jsonify(success=False, message='OTP code has expired. Please resend.')
        
        # Verify OTP
        if otp_record['otp_code'] != otp_code:
            return jsonify(success=False, message='Invalid OTP code')
        
        # Mark OTP as verified
        cursor.execute("""
            UPDATE otp_verification 
            SET is_verified = TRUE 
            WHERE id = %s
        """, (otp_record['id'],))
        
        # Activate user account
        cursor.execute("""
            UPDATE users 
            SET is_email_verified = TRUE, is_active = 1
            WHERE id = %s
        """, (user_id,))
        
        conn.commit()
        
        # Get updated user data
        cursor.execute("""
            SELECT id, first_name, last_name, email, role, is_active
            FROM users 
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
        
        # Create session
        session.clear()
        session.update({
            'loggedin': True,
            'user_id': user['id'],
            'username': user['first_name'],
            'email': user['email'],
            'role': user['role'],
            'is_email_verified': True
        })
        
        redirect_url = url_for('user_bp.user_dashboard')
        return jsonify(success=True, message='Email verified successfully!', redirect=redirect_url)
        
    except Exception as e:
        current_app.logger.error(f"OTP verification error: {e}")
        return jsonify(success=False, message='Verification failed. Please try again.')
    finally:
        cursor.close()
        conn.close()


@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP with rate limiting"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    user_id = session.get('temp_user_id')
    
    if not email or not user_id:
        return jsonify(success=False, message='Invalid request')
    
    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message='Database error')
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check rate limiting
        cursor.execute("""
            SELECT last_sent, attempts 
            FROM email_rate_limit 
            WHERE email = %s 
            AND last_sent > DATE_SUB(NOW(), INTERVAL 1 HOUR)
        """, (email,))
        rate_limit = cursor.fetchone()
        
        if rate_limit:
            if rate_limit['attempts'] >= 3:
                return jsonify(success=False, message='Too many attempts. Please try again later.')
            
            if datetime.now() - rate_limit['last_sent'] < timedelta(seconds=60):
                return jsonify(success=False, message='Please wait 60 seconds before requesting another code.')
        
        # Get user details
        cursor.execute("""
            SELECT first_name, email 
            FROM users 
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify(success=False, message='User not found')
        
        # Generate new OTP
        otp_code = generate_otp()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        cursor.execute("""
            INSERT INTO otp_verification (user_id, email, otp_code, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, email, otp_code, expires_at))
        
        # Update rate limit
        if rate_limit:
            cursor.execute("""
                UPDATE email_rate_limit 
                SET attempts = attempts + 1, last_sent = NOW()
                WHERE email = %s
            """, (email,))
        else:
            cursor.execute("""
                INSERT INTO email_rate_limit (email, last_sent, attempts)
                VALUES (%s, NOW(), 1)
            """, (email,))
        
        conn.commit()
        
        # Send email
        if send_otp_email(email, otp_code, user['first_name']):
            return jsonify(success=True, message='New verification code sent to your email.')
        else:
            return jsonify(success=False, message='Failed to send email. Please try again.')
            
    except Exception as e:
        current_app.logger.error(f"Resend OTP error: {e}")
        return jsonify(success=False, message='Server error. Please try again.')
    finally:
        cursor.close()
        conn.close()


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Logout user"""
    try:
        session.clear()
        
        if request.method == 'POST':
            return jsonify({
                "success": True,
                "message": "You have been successfully logged out.",
                "redirect_url": "/"
            }), 200
        else:
            flash('You have been logged out', 'success')
            return redirect(url_for('base_bp.index'))
            
    except Exception as e:
        if request.method == 'POST':
            return jsonify({
                "success": False,
                "message": "An unexpected error occurred. Please try again."
            }), 500
        else:
            flash('Error during logout', 'error')
            return redirect(url_for('base_bp.index'))


# ============================================================================
# HANDLER FUNCTIONS
# ============================================================================
def handle_login(email, password):
    """Handle login form submission"""
    # Validation
    if not email or not password:
        return jsonify(success=False, message='Email and password are required.')

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message='Database connection error.')
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get user by email
        cursor.execute("""
            SELECT id, first_name, last_name, email, password, role, is_active, is_email_verified
            FROM users 
            WHERE email = %s
        """, (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify(success=False, message='Invalid email or password.')

        # Check email verification
        if not user.get('is_email_verified', False):
            session['temp_user_id'] = user['id']
            session['temp_email'] = user['email']
            session['temp_username'] = user['first_name']
            return jsonify(
                success=False, 
                message='Email not verified. Please verify your email first.', 
                needs_verification=True
            )

        # Check account status
        if not user['is_active']:
            return jsonify(success=False, message='Account is deactivated. Please contact support.')

        # Verify password
        if not check_password_hash(user['password'], password):
            return jsonify(success=False, message='Invalid email or password.')

        # Create session
        session.clear()
        session.update({
            'loggedin': True,
            'user_id': user['id'],
            'username': user['first_name'],
            'email': user['email'],
            'role': user['role'],
            'is_email_verified': user['is_email_verified']
        })

        # Determine redirect URL based on role
        if user['role'] == 'admin':
            redirect_url = url_for('admin_bp.admin_dashboard')
        else:
            redirect_url = url_for('user_bp.user_dashboard')
        
        return jsonify(success=True, message='Login successful!', redirect=redirect_url)

    except mysql.connector.Error as e:
        current_app.logger.error(f"DB error during login: {e}")
        return jsonify(success=False, message='Database error. Please try again.')
    finally:
        cursor.close()
        conn.close()


def handle_signup(data):
    """Handle registration form submission with OTP"""
    # Extract data
    first_name = data.get('firstname', '').strip()
    last_name = data.get('lastname', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('contact_number', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    # Validate required fields
    if not all([first_name, last_name, email, phone, password]):
        return jsonify(success=False, message='All required fields must be filled.')

    # Validate password match
    if password != confirm_password:
        return jsonify(success=False, message='Passwords do not match.')

    # Validate email format
    if not is_valid_email(email):
        return jsonify(success=False, message='Invalid email format.')
    
    # Validate password strength
    if len(password) < 8:
        return jsonify(success=False, message='Password must be at least 8 characters.')
    
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$'
    if not re.match(password_pattern, password):
        return jsonify(
            success=False, 
            message='Password must contain at least one uppercase letter, one lowercase letter, and one number.'
        )

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message='Database connection error.')
    
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify(success=False, message='Email is already registered.')

        # Create user
        hashed_pw = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, password, phone, role, is_active, is_email_verified, created_at)
            VALUES (%s, %s, %s, %s, %s, 'user', 0, 0, NOW())
        """, (first_name, last_name, email, hashed_pw, phone))
        
        user_id = cursor.lastrowid
        
        # Create OTP
        otp_code = generate_otp()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        cursor.execute("""
            INSERT INTO otp_verification (user_id, email, otp_code, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, email, otp_code, expires_at))
        
        conn.commit()
        
        # Send verification email
        email_sent = send_otp_email(email, otp_code, first_name)
        
        if not email_sent:
            current_app.logger.error(f"Failed to send OTP email to {email}")
        
        # Store temporary session data
        session['temp_user_id'] = user_id
        session['temp_email'] = email
        session['temp_username'] = first_name
        
        return jsonify(
            success=True, 
            message='Verification code sent to your email. Please verify to complete registration.', 
            needs_verification=True
        )

    except mysql.connector.Error as e:
        conn.rollback()
        current_app.logger.error(f"Signup DB Error: {e}")
        return jsonify(success=False, message='Database error. Please try again.')
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Signup General Error: {e}")
        return jsonify(success=False, message='An unexpected error occurred.')
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# AJAX ROUTES
# ============================================================================
@auth_bp.route('/check-email/<email>')
def check_email(email):
    """Check if email is already registered (AJAX endpoint)"""
    email = email.lower()
    
    if not is_valid_email(email):
        return jsonify(available=False, message='Invalid email format')
    
    conn = get_db_connection()
    if not conn:
        return jsonify(available=False, message='Database connection error')
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        exists = result is not None
        
        return jsonify(
            available=not exists,
            message='Email available' if not exists else 'Email already registered'
        )
    except Exception as e:
        current_app.logger.error(f"Check email error: {e}")
        return jsonify(available=False, message='Check failed')
    finally:
        cursor.close()
        conn.close()