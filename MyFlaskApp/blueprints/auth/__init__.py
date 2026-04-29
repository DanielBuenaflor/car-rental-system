# Auth blueprint
from .routes import auth_bp

# Configure template folder for this blueprint
import os
_auth_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
auth_bp.template_folder = os.path.join(_auth_dir, 'authentication', 'templates')