# User blueprint
from .routes import user_bp

# Configure template folder for this blueprint
import os
_user_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
user_bp.template_folder = os.path.join(_user_dir, 'user', 'templates')