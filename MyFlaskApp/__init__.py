from flask import Flask, send_from_directory, request, after_this_request
from flask.cli import load_dotenv
from flask import session
import mysql.connector
from flask_mail import Mail
import os

mail = Mail() 
load_dotenv()  # Load environment variables from .env file

dbConfig = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'car_rental_system')
}

def create_app():
    app = Flask(__name__, 
                template_folder='.',           # Look in current directory for templates
                static_folder='static')
    
    secret_key = os.environ.get('SECRET_KEY')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    if not secret_key and not debug:
        raise RuntimeError(
            "SECRET_KEY environment variable is required in production. "
            "Set SECRET_KEY or run with FLASK_DEBUG=True for development."
        )
    app.config['SECRET_KEY'] = secret_key or 'dev-secret-key-change-in-production'
    # Set secret_key for session signing
    app.secret_key = app.config['SECRET_KEY']
    
    # Configure session with permanent cookie
    app.config['SESSION_COOKIE_NAME'] = 'car_rental_session'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
    
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@carrentalpro.com')
    app.config['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # Change this - uploads folder is now inside base
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'base', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Increased to 100MB to handle compressed base64 images
    
    mail.init_app(app)
    
    # Validate email configuration on startup
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        print("="*60)
        print("EMAIL CONFIGURATION MISSING!")
        print(f"MAIL_USERNAME: {'SET' if app.config.get('MAIL_USERNAME') else 'NOT SET'}")
        print(f"MAIL_PASSWORD: {'SET' if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
        print("Verification emails will NOT be sent!")
        print("="*60)
    else:
        print("Email configuration loaded successfully")
        print(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}:{app.config.get('MAIL_PORT')}")
        print(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
        print(f"MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")
    
    # Route to serve uploaded files from base/uploads
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # Register blueprints
    from MyFlaskApp.blueprints.base.base_bp import base_bp
    from MyFlaskApp.blueprints.auth.routes import auth_bp
    from MyFlaskApp.user.user_bp import user_bp
    from MyFlaskApp.blueprints.admin.routes import admin_bp
    from MyFlaskApp.payment.payment_bp import payment_bp
    from MyFlaskApp.payment.webhooks import webhook_bp
    from MyFlaskApp.api.locations_bp import locations_bp

    app.register_blueprint(webhook_bp, url_prefix='/webhooks')
    app.register_blueprint(base_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    app.register_blueprint(locations_bp)
    
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
        
        if not debug:
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Content-Security-Policy'] = "default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com https://*.openstreetmap.org; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com; img-src 'self' data: blob: https://*.openstreetmap.org https://unpkg.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; connect-src 'self' https://*.openstreetmap.org https://unpkg.com;"
        
        response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        
        return response
    
    return app

def get_db_connection():
    try:
        connection = mysql.connector.connect(**dbConfig)
        return connection
    except mysql.connector.Error as e:
        print(f"Error connecting to database: {e}")
        return None