# Admin blueprint
from .routes import admin_bp

# Configure template folder for this blueprint
import os
_admin_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
admin_bp.template_folder = os.path.join(_admin_dir, 'admin', 'templates')