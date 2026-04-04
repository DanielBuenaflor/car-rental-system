from flask import Flask, send_from_directory
from flask.cli import load_dotenv
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
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@carrentalpro.com')
    app.config['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # Change this - uploads folder is now inside base
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'base', 'uploads')
    
    mail.init_app(app)
    
    # Route to serve uploaded files from base/uploads
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # Register blueprints
    from MyFlaskApp.base.base_bp import base_bp
    from MyFlaskApp.authentication.auth import auth_bp
    from MyFlaskApp.user.user_bp import user_bp
    from MyFlaskApp.admin.admin_bp import admin_bp
    from MyFlaskApp.payment.payment_bp import payment_bp
    from MyFlaskApp.payment.webhooks import webhook_bp

    app.register_blueprint(webhook_bp, url_prefix='/webhooks')
    app.register_blueprint(base_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    
    return app

def get_db_connection():
    try:
        connection = mysql.connector.connect(**dbConfig)
        return connection
    except mysql.connector.Error as e:
        print(f"Error connecting to database: {e}")
        return None