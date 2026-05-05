"""
Rate Limiting Helper Module
Provides rate limiting for brute force protection.

Security Features:
- In-memory rate limiting with configurable limits
- IP-based and user-based rate limiting
- Sliding window algorithm
- Configurable time windows and attempt limits

Usage:
    from MyFlaskApp.utils.rate_limit import check_rate_limit, RateLimiter

    # Simple check (5 attempts per 60 seconds)
    if not check_rate_limit('login_attempt', 'user_identifier'):
        return jsonify({'error': 'Too many attempts'}), 429

    # With decorator
    @app.route('/login', methods=['POST'])
    @rate_limit('login', max_attempts=5, window_seconds=60)
    def login():
        ...
"""

import time
from typing import Dict, Optional, Tuple
from functools import wraps
from flask import request, jsonify, current_app
import threading

_attempt_store: Dict[str, Dict] = {}
_store_lock = threading.Lock()


def _cleanup_expired():
    """Remove expired entries from the store"""
    current_time = time.time()
    expired_keys = []
    
    for key, data in _attempt_store.items():
        if current_time > data['reset_time']:
            expired_keys.append(key)
    
    for key in expired_keys:
        _attempt_store.pop(key, None)


def check_rate_limit(
    key: str,
    identifier: str,
    max_attempts: int = 5,
    window_seconds: int = 60,
    cleanup: bool = True
) -> Tuple[bool, Optional[int]]:
    """
    Check if identifier has exceeded rate limit.
    
    Input:
        key: Rate limit key (e.g., 'login_attempt', 'otp_request')
        identifier: Unique identifier (IP address, user email, user ID)
        max_attempts: Maximum attempts allowed in window
        window_seconds: Time window in seconds
        cleanup: Whether to clean up expired entries
        
    Output:
        Tuple of (is_allowed, remaining_attempts)
    """
    if cleanup and len(_attempt_store) > 1000:
        _cleanup_expired()
    
    composite_key = f"{key}:{identifier}"
    current_time = time.time()
    
    with _store_lock:
        if composite_key in _attempt_store:
            data = _attempt_store[composite_key]
            
            if current_time > data['reset_time']:
                _attempt_store[composite_key] = {
                    'attempts': 1,
                    'reset_time': current_time + window_seconds,
                    'first_attempt': current_time
                }
                return True, max_attempts - 1
            
            if data['attempts'] >= max_attempts:
                wait_time = int(data['reset_time'] - current_time)
                return False, 0
            
            data['attempts'] += 1
            remaining = max_attempts - data['attempts']
            return True, remaining
        else:
            _attempt_store[composite_key] = {
                'attempts': 1,
                'reset_time': current_time + window_seconds,
                'first_attempt': current_time
            }
            return True, max_attempts - 1


def reset_rate_limit(key: str, identifier: str) -> None:
    """Reset rate limit for identifier"""
    composite_key = f"{key}:{identifier}"
    with _store_lock:
        _attempt_store.pop(composite_key, None)


def get_rate_limit_info(
    key: str,
    identifier: str
) -> Optional[Dict]:
    """Get current rate limit info for identifier"""
    composite_key = f"{key}:{identifier}"
    
    with _store_lock:
        if composite_key in _attempt_store:
            data = _attempt_store[composite_key]
            current_time = time.time()
            
            if current_time <= data['reset_time']:
                return {
                    'attempts': data['attempts'],
                    'reset_time': data['reset_time'],
                    'remaining': max(0, 5 - data['attempts']),
                    'wait_seconds': int(data['reset_time'] - current_time)
                }
    
    return None


def rate_limit(
    key: str,
    max_attempts: int = 5,
    window_seconds: int = 60,
    identifier_func: Optional[callable] = None
):
    """
    Decorator to apply rate limiting to a route.
    
    Input:
        key: Rate limit key
        max_attempts: Maximum attempts allowed
        window_seconds: Time window in seconds
        identifier_func: Optional function to get custom identifier
        
    Usage:
        @app.route('/login', methods=['POST'])
        @rate_limit('login', max_attempts=5, window_seconds=60)
        def login():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if identifier_func:
                identifier = identifier_func()
            else:
                identifier = request.remote_addr or 'unknown'
            
            allowed, remaining = check_rate_limit(key, identifier, max_attempts, window_seconds)
            
            if not allowed:
                current_app.logger.warning(
                    f"[RATE_LIMIT] Rate limit exceeded for {key}:{identifier}"
                )
                return jsonify({
                    'success': False,
                    'message': 'Too many attempts. Please try again later.',
                    'retry_after': window_seconds
                }), 429
            
            response = f(*args, **kwargs)
            
            if isinstance(response, tuple) and len(response) >= 2:
                resp, status_code = response[0], response[1]
                if hasattr(resp, 'json'):
                    resp_json = resp.get_json()
                    if resp_json is not None:
                        resp_json['rate_limit'] = {
                            'remaining': remaining,
                            'limit': max_attempts
                        }
            
            return response
        
        return decorated_function
    return decorator


def get_client_ip() -> str:
    """Get client IP address, considering proxy headers"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'