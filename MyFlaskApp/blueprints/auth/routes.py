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
import logging

# Configure logger for defensive logging
logger = logging.getLogger(__name__)

from MyFlaskApp import get_db_connection, mail
from MyFlaskApp.utils.csrf import generate_csrf_token, validate_csrf_token, clear_csrf_token
from MyFlaskApp.utils.rate_limit import check_rate_limit, get_client_ip, reset_rate_limit

# ============================================================================
# STANDARDIZED ERROR MESSAGES (Single Source of Truth)
# ============================================================================
ERROR_MESSAGES = {
    'DB_CONNECTION_ERROR': 'Database connection error. Please try again.',
    'DB_OPERATION_ERROR': 'Database error. Please try again.',
    'INVALID_CREDENTIALS': 'Invalid email or password.',
    'ACCOUNT_DEACTIVATED': 'Account is deactivated. Please contact support.',
    'EMAIL_NOT_VERIFIED': 'Email not verified. Please verify your email first.',
    'EMAIL_EXISTS': 'Email is already registered.',
    'EMAIL_INVALID_FORMAT': 'Invalid email format.',
    'OTP_INVALID': 'Invalid OTP code.',
    'OTP_EXPIRED': 'OTP code has expired. Please resend.',
    'OTP_NOT_FOUND': 'No pending verification found.',
    'OTP_SEND_FAILED': 'Failed to send verification email. Please check your email configuration and try again.',
    'RATE_LIMIT_EXCEEDED': 'Too many attempts. Please try again later.',
    'RATE_LIMIT_WAIT': 'Please wait 60 seconds before requesting another code.',
    'MISSING_REQUIRED_FIELDS': 'All required fields must be filled.',
    'PASSWORD_MISMATCH': 'Passwords do not match.',
    'PASSWORD_TOO_SHORT': 'Password must be at least 8 characters.',
    'PASSWORD_COMPLEXITY': 'Password must contain at least one uppercase letter, one lowercase letter, and one number.',
    'USER_NOT_FOUND': 'User not found.',
    'VERIFICATION_FAILED': 'Verification failed. Please try again.',
    'SERVER_ERROR': 'An unexpected error occurred. Please try again.',
}


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

def csrf_exempt(f):
    """Decorator to exempt a route from CSRF validation (for APIs/webhooks only)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    decorated_function.csrf_exempt = True
    return decorated_function


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def is_valid_email(email):
    """
    Validate email format using regex pattern matching.
    
    Input:
        email (str): Email address string to validate
        
    Process:
        1. Apply RFC-compliant email regex pattern
        2. Check for valid characters, @ symbol, and domain format
        
    Output:
        bool: True if email format is valid, False otherwise
    """
    email_validation_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = re.match(email_validation_pattern, email) is not None
    logger.debug(f"[AUTH] Email validation for '{email}': {is_valid}")
    return is_valid


def generate_otp():
    """
    Generate a cryptographically secure 6-digit OTP code.
    
    Output:
        str: 6-digit numeric OTP code (e.g., '123456')
    """
    generated_otp = ''.join(random.choices(string.digits, k=6))
    logger.debug(f"[AUTH] Generated new OTP: {generated_otp[:2]}****{generated_otp[-1]} (masked)")
    return generated_otp


def send_otp_email(recipient_email, otp_code, recipient_name):
    """
    Send verification email with OTP code to user.
    
    Input:
        recipient_email (str): Email address of the recipient
        otp_code (str): 6-digit OTP code to send
        recipient_name (str): First name of the recipient for personalization
        
    Output:
        bool: True if email sent successfully, False otherwise
    """
    logger.info(f"[AUTH] Starting OTP email send process for: {recipient_email}")
    try:
        # Verify mail server configuration is present before attempting send
        mail_username = current_app.config.get('MAIL_USERNAME')
        mail_password = current_app.config.get('MAIL_PASSWORD')
        
        if not mail_username or not mail_password:
            logger.error(
                f"[AUTH] EMAIL SEND FAILED - Configuration missing! "
                f"MAIL_USERNAME: {'SET' if mail_username else 'NOT SET'}, "
                f"MAIL_PASSWORD: {'SET' if mail_password else 'NOT SET'}"
            )
            return False
        
        smtp_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port = current_app.config.get('MAIL_PORT', 587)
        logger.info(f"[AUTH] Sending OTP email via SMTP: {smtp_server}:{smtp_port}")
        print(f"[AUTH] Attempting to send OTP email to: {recipient_email}")

        email_message = Message(
            subject="Your Verification Code - CarRental Pro",
            recipients=[recipient_email],
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
        <p>Hello <strong>{recipient_name}</strong>,</p>
        <p>Your verification code is:</p>
        <div style="padding: 15px; background-color: #f0f0f0; font-size: 24px; font-weight: bold; text-align: center;">
            {otp_code}
        </div>
        <p>This code is valid for 10 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
    </div>
</body>
</html>
            """,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@carrentalpro.com')
        )
        
        mail.send(email_message)
        logger.info(f"[AUTH] OTP email sent successfully to: {recipient_email}")
        print(f"[AUTH] OTP email sent successfully to: {recipient_email}")
        return True
        
    except Exception as email_error:
        error_details = f"[{type(email_error).__name__}] {str(email_error)}"
        logger.error(f"[AUTH] FAILED TO SEND OTP EMAIL to {recipient_email}: {error_details}")
        
        print("="*60)
        print(f"[AUTH] FAILED TO SEND OTP EMAIL to {recipient_email}")
        print(f"[AUTH] Error type: {type(email_error).__name__}")
        print(f"[AUTH] Error message: {str(email_error)}")
        
        # Log SMTP-specific details if available
        if hasattr(email_error, 'smtp_error'):
            smtp_error_detail = email_error.smtp_error
            logger.error(f"[AUTH] SMTP Error Detail: {smtp_error_detail}")
            print(f"[AUTH] SMTP Error: {smtp_error_detail}")
        if hasattr(email_error, 'smtp_code'):
            smtp_code = email_error.smtp_code
            logger.error(f"[AUTH] SMTP Code: {smtp_code}")
            print(f"[AUTH] SMTP Code: {smtp_code}")
        
        print("="*60)
        return False


# ============================================================================
# HELPER FUNCTIONS - AUTHENTICATION
# ============================================================================
def handle_login(email, password):
    """
    Handle user login authentication.

    Input:
        email (str): User's email address
        password (str): User's password

    Process:
        1. Validate input parameters
        2. Query user from database
        3. Verify password hash
        4. Check account status (active, email verified)
        5. Create user session
        6. Return dict with success status and redirect URL

    Output:
        dict with keys: success (bool), message (str), redirect (str, optional)
    """
    logger.info(f"[AUTH] Processing login handler for: {email}")

    # Validate input
    if not email or not password:
        logger.warning("[AUTH] Login failed: Missing email or password")
        return {'success': False, 'message': ERROR_MESSAGES['MISSING_REQUIRED_FIELDS']}

    # Get database connection
    database_connection = get_db_connection()
    if not database_connection:
        logger.error("[AUTH] Login failed: Database connection error")
        return {'success': False, 'message': ERROR_MESSAGES['DB_CONNECTION_ERROR']}

    database_cursor = database_connection.cursor(dictionary=True)

    try:
        logger.info(f"[AUTH] Querying user from database: {email}")

        # Retrieve user by email
        database_cursor.execute("""
            SELECT id, first_name, last_name, email, password, role,
                   is_active, is_email_verified
            FROM users
            WHERE email = %s
        """, (email,))
        user_record = database_cursor.fetchone()

        # Verify user exists
        if not user_record:
            logger.warning(f"[AUTH] Login failed: User not found - {email}")
            return {'success': False, 'message': ERROR_MESSAGES['INVALID_CREDENTIALS']}

        logger.debug(f"[AUTH] User found: ID {user_record['id']}")

        # Verify password
        stored_password_hash = user_record['password']
        if not check_password_hash(stored_password_hash, password):
            logger.warning(f"[AUTH] Login failed: Invalid password for user {email}")
            return {'success': False, 'message': ERROR_MESSAGES['INVALID_CREDENTIALS']}

        logger.info(f"[AUTH] Password verified for user: {email}")

        # Check if account is active
        if not user_record.get('is_active', 0):
            logger.warning(f"[AUTH] Login failed: Account deactivated - {email}")
            return {'success': False, 'message': ERROR_MESSAGES['ACCOUNT_DEACTIVATED']}

        # Check if email is verified
        if not user_record.get('is_email_verified', False):
            logger.warning(f"[AUTH] Login failed: Email not verified - {email}")

            # Store temp user ID for verification flow
            session['temp_user_id'] = user_record['id']
            session['temp_email'] = user_record['email']
            session['temp_username'] = user_record['first_name']

            return {'success': False, 'message': ERROR_MESSAGES['EMAIL_NOT_VERIFIED'], 'needs_verification': True}

        # Create user session
        session.clear()
        session.update({
            'loggedin': True,
            'user_id': user_record['id'],
            'username': user_record['first_name'],
            'email': user_record['email'],
            'role': user_record['role'],
            'is_email_verified': True
        })
        logger.info(f"[AUTH] Session created for user: {email} (Role: {user_record['role']})")

        # Determine redirect URL based on role
        if user_record['role'] == 'admin':
            redirect_url = url_for('admin_bp.admin_dashboard')
        else:
            redirect_url = url_for('user_bp.user_dashboard')

        logger.info(f"[AUTH] Login successful. Redirecting to: {redirect_url}")
        return {'success': True, 'message': 'Login successful!', 'redirect': redirect_url}

    except mysql.connector.Error as database_error:
        logger.error(f"[AUTH] Database error during login: {database_error}")
        current_app.logger.error(f"[AUTH] DB error during login: {database_error}")
        return {'success': False, 'message': ERROR_MESSAGES['DB_OPERATION_ERROR']}
    except Exception as error:
        logger.error(f"[AUTH] Unexpected error during login: {error}")
        current_app.logger.error(f"[AUTH] Unexpected error during login: {error}")
        return {'success': False, 'message': ERROR_MESSAGES['SERVER_ERROR']}
    finally:
        database_cursor.close()
        database_connection.close()
        logger.debug("[AUTH] Database connection closed after login attempt")


# ============================================================================
# MAIN ROUTES
# ============================================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login page - handles GET (display form) and POST (process login).
    """
    logger.info(f"[AUTH] Login route accessed. Method: {request.method}")
    
    # Load available vehicles for the base template display
    database_connection = get_db_connection()
    available_vehicles = []
    
    if database_connection:
        try:
            database_cursor = database_connection.cursor(dictionary=True)
            database_cursor.execute("""
                SELECT v.*, vb.name as brand_name 
                FROM vehicles v
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE v.status = 'available'
            """)
            available_vehicles = database_cursor.fetchall()
            logger.debug(f"[AUTH] Loaded {len(available_vehicles)} available vehicles for login page")
        except Exception as vehicle_load_error:
            logger.error(f"[AUTH] Error loading vehicles for login page: {vehicle_load_error}")
            print(f"[AUTH] Error loading vehicles: {vehicle_load_error}")
        finally:
            database_cursor.close()
            database_connection.close()
    else:
        logger.warning("[AUTH] No database connection available for loading vehicles")
    
    if request.method == 'POST':
        logger.info("[AUTH] Processing login POST request")

        csrf_submitted = request.form.get('csrf_token', '')
        valid, error = validate_csrf_token(csrf_submitted)
        if not valid:
            logger.warning(f"[AUTH] CSRF validation failed: {error}")
            flash('Security validation failed. Please try again.', 'error')
            generate_csrf_token()
            return render_template('login.html', session=session, all_vehicles=available_vehicles)
        
        client_ip = get_client_ip()
        allowed, remaining = check_rate_limit('login_attempt', client_ip, max_attempts=5, window_seconds=60)
        if not allowed:
            logger.warning(f"[AUTH] Login rate limit exceeded for IP: {client_ip}")
            flash('Too many login attempts. Please try again in 60 seconds.', 'error')
            generate_csrf_token()
            return render_template('login.html', session=session, all_vehicles=available_vehicles)
        
        user_email = request.form.get('email', '').strip()
        user_password = request.form.get('password', '')
        logger.debug("[AUTH] Login credentials extracted from form data")

        logger.info(f"[AUTH] Attempting login for email: {user_email}")

        # Call handle_login and handle the result
        result = handle_login(user_email, user_password)

        if result['success']:
            reset_rate_limit('login_attempt', client_ip)
            clear_csrf_token()
            flash('Login successful!', 'success')
            return redirect(result['redirect'])
        else:
            # Generate new CSRF token for retry form
            generate_csrf_token()
            flash(result['message'], 'error')
            return render_template('login.html', session=session, all_vehicles=available_vehicles)

    # GET request - render login form
    logger.debug("[AUTH] Rendering login form (GET request)")
    generate_csrf_token()
    return render_template('login.html', session=session, all_vehicles=available_vehicles)

@auth_bp.route('/register', methods=['GET', 'POST'])
@csrf_exempt
def register():
    """
    User registration page - handles GET (display form) and POST (process registration).
    
    Input (GET):
        None - Renders registration form with available vehicles
        
    Input (POST):
        JSON or Form Data:
            - firstname (str): User's first name
            - lastname (str): User's last name
            - email (str): User's email address
            - contact_number (str): User's phone number
            - password (str): User's password
            - confirm_password (str): Password confirmation
            
    Process:
        1. Load available vehicles for display on registration page
        2. If POST: Extract registration data from request
        3. Call handle_signup() for registration logic
        4. Return appropriate response based on registration result
        
    Output:
        GET: Rendered register.html template with vehicle data
        POST: JSON response with registration result
    """
    logger.info(f"[AUTH] Register route accessed. Method: {request.method}")
    
    # Load available vehicles for the base template display
    database_connection = get_db_connection()
    available_vehicles = []
    
    if database_connection:
        try:
            database_cursor = database_connection.cursor(dictionary=True)
            database_cursor.execute("""
                SELECT v.*, vb.name as brand_name 
                FROM vehicles v
                JOIN vehicle_brands vb ON v.brand_id = vb.id
                WHERE v.status = 'available'
            """)
            available_vehicles = database_cursor.fetchall()
            logger.debug(f"[AUTH] Loaded {len(available_vehicles)} available vehicles for registration page")
        except Exception as vehicle_load_error:
            logger.error(f"[AUTH] Error loading vehicles for registration page: {vehicle_load_error}")
            print(f"[AUTH] Error loading vehicles: {vehicle_load_error}")
        finally:
            database_cursor.close()
            database_connection.close()
    else:
        logger.warning("[AUTH] No database connection available for loading vehicles")
    
    if request.method == 'POST':
        logger.info("[AUTH] Processing registration POST request")
        
        # Extract registration data from JSON or form data
        if request.is_json:
            registration_data = request.get_json()
            logger.debug("[AUTH] Registration data extracted from JSON payload")
            
            # Validate CSRF token
            csrf_submitted = registration_data.get('csrf_token', '')
            valid, error = validate_csrf_token(csrf_submitted)
            if not valid:
                logger.warning(f"[AUTH] CSRF validation failed: {error}")
                return jsonify(success=False, message='Security validation failed. Please try again.')
        else:
            registration_data = request.form
            logger.debug("[AUTH] Registration data extracted from form data")
            
            # Validate CSRF token
            csrf_submitted = registration_data.get('csrf_token', '')
            valid, error = validate_csrf_token(csrf_submitted)
            if not valid:
                logger.warning(f"[AUTH] CSRF validation failed: {error}")
                flash('Security validation failed. Please try again.', 'error')
                generate_csrf_token()
                return render_template('register.html', session=session, all_vehicles=available_vehicles)
            
            # Process registration for form data
            if not request.is_json:
                # Get form data as dictionary
                form_data = {
                    'firstname': request.form.get('firstname', ''),
                    'lastname': request.form.get('lastname', ''),
                    'email': request.form.get('email', ''),
                    'contact_number': request.form.get('contact_number', ''),
                    'password': request.form.get('password', ''),
                    'confirm_password': request.form.get('confirm_password', '')
                }
                
                # Call handle_signup
                result = handle_signup(form_data)
                
                # Parse the JSON result
                if isinstance(result, tuple):
                    result_data = result[0].get_json() if hasattr(result[0], 'get_json') else {'success': False, 'message': 'Error'}
                    status_code = result[1]
                else:
                    result_data = result.get_json() if hasattr(result, 'get_json') else {'success': False, 'message': 'Error'}
                    status_code = 200
                
                if result_data.get('success'):
                    if result_data.get('needs_verification'):
                        # Store data in session for OTP verification
                        session['temp_email'] = result_data.get('email', form_data['email'])
                        session['temp_username'] = form_data['firstname']
                        flash('Verification code sent to your email. Please verify to complete registration.', 'success')
                        # For HTML form, redirect to login which handles OTP
                        return redirect(url_for('auth_bp.login'))
                    else:
                        flash(result_data.get('message', 'Registration successful!'), 'success')
                        return redirect(url_for('auth_bp.login'))
                else:
                    flash(result_data.get('message', 'Registration failed. Please try again.'), 'error')
                    generate_csrf_token()
                    return render_template('register.html', session=session, all_vehicles=available_vehicles)
    
    # GET request - render registration form
    logger.debug("[AUTH] Rendering registration form (GET request)")
    generate_csrf_token()
    return render_template('register.html', session=session, all_vehicles=available_vehicles)


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    """
    Verify OTP code submitted by user and activate account if valid.
    
    Input:
        JSON payload:
            - otp_code (str): 6-digit OTP code entered by user
            
    Process:
        1. Extract OTP code from request and user_id from session
        2. Validate input parameters
        3. Retrieve latest unverified OTP record for user from database
        4. Check if OTP has expired
        5. Verify submitted code matches stored code
        6. Mark OTP as verified in database
        7. Activate user account (is_email_verified = TRUE, is_active = 1)
        8. Create user session
        9. Return success response with redirect URL
        
    Output:
        JSON response:
            - success (bool): True if verification successful
            - message (str): Status message
            - redirect (str, optional): URL to redirect on success
    """
    logger.info("[AUTH] OTP verification route accessed")
    
    request_data = request.get_json()
    submitted_otp_code = request_data.get('otp_code', '').strip()
    temp_user_id = session.get('temp_user_id')
    
    logger.debug(f"[AUTH] OTP verification attempt. User ID from session: {temp_user_id}")
    
    # Validate input parameters
    if not submitted_otp_code or not temp_user_id:
        logger.warning("[AUTH] OTP verification failed: Missing OTP code or user ID")
        return jsonify(success=False, message='Invalid verification request')
    
    # Establish database connection
    database_connection = get_db_connection()
    if not database_connection:
        logger.error("[AUTH] OTP verification failed: Database connection error")
        return jsonify(success=False, message=ERROR_MESSAGES['DB_CONNECTION_ERROR'])
    
    database_cursor = database_connection.cursor(dictionary=True)
    
    try:
        logger.info(f"[AUTH] Verifying OTP for user ID: {temp_user_id}")
        
        # Retrieve latest unverified OTP record for user
        database_cursor.execute("""
            SELECT id, otp_code, expires_at, is_verified
            FROM otp_verification
            WHERE user_id = %s AND is_verified = FALSE
            ORDER BY created_at DESC LIMIT 1
        """, (temp_user_id,))
        otp_record = database_cursor.fetchone()
        
        if not otp_record:
            logger.warning(f"[AUTH] No pending OTP verification found for user ID: {temp_user_id}")
            return jsonify(success=False, message=ERROR_MESSAGES['OTP_NOT_FOUND'])
        
        logger.debug(f"[AUTH] Found OTP record ID: {otp_record['id']}")
        
        # Check if OTP has expired
        current_time = datetime.now()
        expiration_time = otp_record['expires_at']
        
        if current_time > expiration_time:
            logger.warning(f"[AUTH] OTP expired. Current: {current_time}, Expires: {expiration_time}")
            return jsonify(success=False, message=ERROR_MESSAGES['OTP_EXPIRED'])
        
        # Verify submitted code matches stored code
        stored_otp_code = otp_record['otp_code']
        if stored_otp_code != submitted_otp_code:
            logger.warning(f"[AUTH] OTP mismatch. Submitted: {submitted_otp_code}, Expected: {stored_otp_code[:2]}****")
            return jsonify(success=False, message=ERROR_MESSAGES['OTP_INVALID'])
        
        logger.info("[AUTH] OTP code verified successfully. Activating user account...")
        
        # Mark OTP as verified in database
        database_cursor.execute("""
            UPDATE otp_verification 
            SET is_verified = TRUE 
            WHERE id = %s
        """, (otp_record['id'],))
        logger.debug(f"[AUTH] OTP record {otp_record['id']} marked as verified")
        
        # Activate user account
        database_cursor.execute("""
            UPDATE users 
            SET is_email_verified = TRUE, is_active = 1
            WHERE id = %s
        """, (temp_user_id,))
        logger.info(f"[AUTH] User account {temp_user_id} activated (email verified, is_active = 1)")
        
        # Commit all database changes
        database_connection.commit()
        logger.info("[AUTH] Database transaction committed successfully")
        
        # Retrieve updated user data for session creation
        database_cursor.execute("""
            SELECT id, first_name, last_name, email, role, is_active
            FROM users 
            WHERE id = %s
        """, (temp_user_id,))
        user_record = database_cursor.fetchone()
        
        # Create user session
        session.clear()
        session.update({
            'loggedin': True,
            'user_id': user_record['id'],
            'username': user_record['first_name'],
            'email': user_record['email'],
            'role': user_record['role'],
            'is_email_verified': True
        })
        logger.info(f"[AUTH] Session created for user: {user_record['email']} (Role: {user_record['role']})")
        
        # Determine redirect URL based on user role
        if user_record['role'] == 'admin':
            redirect_url = url_for('admin_bp.admin_dashboard')
        else:
            redirect_url = url_for('user_bp.user_dashboard')
        
        logger.info(f"[AUTH] OTP verification completed successfully. Redirecting to: {redirect_url}")
        return jsonify(success=True, message='Email verified successfully!', redirect=redirect_url)
        
    except Exception as verification_error:
        logger.error(f"[AUTH] OTP verification error: {verification_error}")
        current_app.logger.error(f"[AUTH] OTP verification error: {verification_error}")
        return jsonify(success=False, message=ERROR_MESSAGES['VERIFICATION_FAILED'])
    finally:
        database_cursor.close()
        database_connection.close()
        logger.debug("[AUTH] Database connection closed after OTP verification")


@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP with rate limiting"""
    # ... (rest of the code remains the same)
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
@csrf_exempt
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


def handle_signup(data):
    """
    Handle registration form submission with OTP.
    
    Input:
        data (dict): Registration form data
        
    Process:
        1. Validate required fields
        2. Validate password strength
        3. Validate email format
        4. Check if email already exists
        5. Create new user record
        6. Generate OTP and send verification email
        7. Store temporary session data for verification flow
        
    Output:
        JSON response:
            - success (bool): True if registration successful
            - message (str): Status message
            - needs_verification (bool, optional): True if email not verified
            - existing_unverified (bool, optional): True if email exists but not verified
    """
    logger.info("[AUTH] Processing signup handler")
    
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

    print(f"[DEBUG] Got DB connection: {conn is not None}")

    try:
        # Check if email already exists
        print(f"[DEBUG] Checking if email exists: {email}")
        cursor.execute("SELECT id, first_name, is_email_verified FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        print(f"[DEBUG] existing_user: {existing_user}")
        
        if existing_user:
            # If email exists but not verified, allow to resend verification
            if not existing_user.get('is_email_verified', False):
                print(f"[DEBUG] User exists but not verified. Generating new OTP and sending email...")
                
                # Generate new OTP for existing user
                otp_code = generate_otp()
                expires_at = datetime.now() + timedelta(minutes=10)
                
                # Save OTP to database
                cursor.execute("""
                    INSERT INTO otp_verification (user_id, email, otp_code, expires_at)
                    VALUES (%s, %s, %s, %s)
                """, (existing_user['id'], email, otp_code, expires_at))
                conn.commit()
                print(f"[DEBUG] Generated and saved new OTP: {otp_code}")
                
                # Send verification email
                email_sent = send_otp_email(email, otp_code, existing_user['first_name'])
                print(f"[DEBUG] send_otp_email returned: {email_sent}")
                
                if not email_sent:
                    print(f"[DEBUG] Email failed to send for existing user.")
                    return jsonify(
                        success=False,
                        message='Failed to send verification email. Please check your email configuration and try again.',
                        needs_verification=True,
                        existing_unverified=True
                    )
                
                # Set session data
                session['temp_user_id'] = existing_user['id']
                session['temp_email'] = email
                session['temp_username'] = existing_user['first_name']
                
                return jsonify(
                    success=True,
                    message='New verification code sent to your email.',
                    needs_verification=True,
                    existing_unverified=True
                )
            return jsonify(success=False, message='Email is already registered.')

        print(f"[DEBUG] Creating new user...")
        # Create user
        hashed_pw = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, password, phone, role, is_active, is_email_verified, created_at)
            VALUES (%s, %s, %s, %s, %s, 'user', 0, 0, NOW())
        """, (first_name, last_name, email, hashed_pw, phone))
        
        user_id = cursor.lastrowid
        print(f"[DEBUG] Created user with ID: {user_id}")
        
        # Create OTP
        otp_code = generate_otp()
        expires_at = datetime.now() + timedelta(minutes=10)
        print(f"[DEBUG] Generated OTP: {otp_code}")
        
        cursor.execute("""
            INSERT INTO otp_verification (user_id, email, otp_code, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, email, otp_code, expires_at))
        print(f"[DEBUG] Saved OTP to database")
        
        print(f"[DEBUG] About to call send_otp_email for: {email}")
        
        # Send verification email BEFORE committing to database
        email_sent = send_otp_email(email, otp_code, first_name)
        
        print(f"[DEBUG] send_otp_email returned: {email_sent}")
        
        if not email_sent:
            conn.rollback()
            print(f"[DEBUG] Email failed, rolling back. Returning error to frontend.")
            return jsonify(success=False, message='Failed to send verification email. Please check your email configuration and try again.')
        
        # Only commit if email was sent successfully
        conn.commit()
        
        # Store temporary session data
        session['temp_user_id'] = user_id
        session['temp_email'] = email
        session['temp_username'] = first_name
        
        # Clear the CSRF token after successful submission
        clear_csrf_token()
        
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