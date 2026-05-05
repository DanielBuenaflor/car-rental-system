"""
CSRF Protection Helper Module
Provides token-based CSRF protection for form submissions.

Usage:
    from MyFlaskApp.utils.csrf import generate_csrf_token, validate_csrf_token
    
    # In route handler - generate token for session
    token = generate_csrf_token()
    
    # In route handler - validate token
    if not validate_csrf_token(submitted_token):
        return jsonify({'error': 'Invalid CSRF token'}), 403
"""

import secrets
import time
from typing import Optional, Tuple
from flask import session, current_app, request, jsonify

TOKEN_LENGTH = 32
TOKEN_VALIDITY_SECONDS = 3600

_csrf_tokens = {}


def generate_csrf_token() -> str:
    """
    Generate a CSRF token for the current session.
    
    Output:
        CSRF token string
    """
    token = secrets.token_hex(TOKEN_LENGTH)
    timestamp = int(time.time())
    
    session['csrf_token'] = token
    session['csrf_token_time'] = timestamp
    
    return token


def validate_csrf_token(submitted_token: str, validity_seconds: int = TOKEN_VALIDITY_SECONDS) -> Tuple[bool, Optional[str]]:
    """
    Validate a submitted CSRF token.
    
    Input:
        submitted_token: Token from form/request
        validity_seconds: How long token is valid (default: 1 hour)
        
    Output:
        Tuple of (is_valid, error_message)
    """
    if not submitted_token:
        return False, "CSRF token missing"
    
    stored_token = session.get('csrf_token')
    if not stored_token:
        return False, "No CSRF token in session"
    
    if stored_token != submitted_token:
        current_app.logger.warning("CSRF token mismatch")
        return False, "Invalid CSRF token"
    
    token_time = session.get('csrf_token_time', 0)
    current_time = int(time.time())
    
    if current_time - token_time > validity_seconds:
        current_app.logger.warning("CSRF token expired")
        return False, "CSRF token expired"
    
    return True, None


def clear_csrf_token() -> None:
    """
    Clear CSRF token from session (call after successful validation).
    """
    session.pop('csrf_token', None)
    session.pop('csrf_token_time', None)


def get_csrf_token_input(token: Optional[str] = None) -> str:
    """
    Get HTML input element for CSRF token.
    
    Input:
        token: CSRF token (if None, gets from session)
        
    Output:
        HTML input string
    """
    if token is None:
        token = session.get('csrf_token', '')
    
    return f'<input type="hidden" name="csrf_token" value="{token}">'


def require_csrf(f):
    """
    Decorator to require CSRF validation on a route.
    
    Usage:
        @app.route('/submit', methods=['POST'])
        @require_csrf
        def submit():
            ...
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        valid, error = validate_csrf_token(token)
        
        if not valid:
            return jsonify({'success': False, 'message': error}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function