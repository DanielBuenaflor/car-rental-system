"""
Input Sanitization Helper Module
Provides input validation and sanitization for XSS prevention.

Security Features:
- HTML escaping for XSS prevention
- SQL injection prevention (parameterized queries recommended)
- Input length validation
- Special character filtering

Usage:
    from MyFlaskApp.utils.sanitize import sanitize_input, validate_length, is_safe_html

    # Sanitize user input
    safe_input = sanitize_input(user_input)
    
    # Validate length
    if not validate_length(input_str, min_len=1, max_len=100):
        return jsonify({'error': 'Invalid length'})
        
    # Check for dangerous HTML
    if not is_safe_html(input_str):
        return jsonify({'error': 'Invalid content'})
"""

import re
import html
from typing import Optional, Tuple


DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'on\w+\s*=',
    r'<iframe[^>]*>.*?</iframe>',
    r'<object[^>]*>.*?</object>',
    r'<embed[^>]*>',
    r'eval\s*\(',
    r'expression\s*\(',
    r'data:text/html',
]

_dangerous_regex = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in DANGEROUS_PATTERNS]


def sanitize_input(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize user input by escaping HTML characters.
    
    Input:
        value: Input string to sanitize
        max_length: Optional maximum length
        
    Output:
        Sanitized string safe for display
    """
    if not value:
        return ''
    
    sanitized = html.escape(str(value))
    
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def sanitize_html(value: str, allow_tags: Optional[list] = None) -> Tuple[bool, str]:
    """
    Check and sanitize HTML content.
    
    Input:
        value: HTML content to sanitize
        allow_tags: Optional list of allowed tags
        
    Output:
        Tuple of (is_safe, sanitized_content)
    """
    if not value:
        return True, ''
    
    value_str = str(value)
    
    for pattern in _dangerous_regex:
        if pattern.search(value_str):
            return False, ''
    
    if allow_tags:
        for tag in allow_tags:
            tag_pattern = re.compile(f'<{tag}[^>]*>', re.IGNORECASE)
            value_str = tag_pattern.sub(f'<{tag}>', value_str)
    
    return True, html.escape(value_str)


def is_safe_html(value: str) -> bool:
    """
    Check if content contains dangerous HTML patterns.
    
    Input:
        value: Content to check
        
    Output:
        True if content is safe, False if dangerous patterns found
    """
    if not value:
        return True
    
    value_str = str(value)
    
    for pattern in _dangerous_regex:
        if pattern.search(value_str):
            return False
    
    return True


def validate_length(value: str, min_length: int = 0, max_length: Optional[int] = None) -> bool:
    """
    Validate input length.
    
    Input:
        value: String to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        
    Output:
        True if length is valid
    """
    if not value:
        return min_length == 0
    
    length = len(value)
    
    if length < min_length:
        return False
    
    if max_length and length > max_length:
        return False
    
    return True


def validate_alphanumeric(value: str, allow_spaces: bool = True) -> bool:
    """
    Validate input contains only alphanumeric characters.
    
    Input:
        value: String to validate
        allow_spaces: Whether to allow spaces
        
    Output:
        True if alphanumeric only
    """
    if not value:
        return False
    
    if allow_spaces:
        return bool(re.match(r'^[a-zA-Z0-9\s]+$', value))
    else:
        return bool(re.match(r'^[a-zA-Z0-9]+$', value))


def sanitize_filename(value: str) -> str:
    """
    Sanitize filename to remove dangerous characters.
    
    Input:
        value: Filename to sanitize
        
    Output:
        Safe filename
    """
    if not value:
        return 'file'
    
    safe = re.sub(r'[^\w\s\-\.]', '', value)
    safe = re.sub(r'[\s]+', '_', safe)
    safe = safe[:255]
    
    return safe or 'file'


def strip_whitespace(value: str) -> str:
    """
    Strip leading/trailing whitespace and normalize internal whitespace.
    
    Input:
        value: String to clean
        
    Output:
        Cleaned string
    """
    if not value:
        return ''
    
    cleaned = ' '.join(str(value).split())
    return cleaned


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format.
    
    Input:
        phone: Phone number string
        
    Output:
        True if valid format
    """
    if not phone:
        return False
    
    phone_pattern = r'^[\d\s\-\+\(\)]{7,20}$'
    return bool(re.match(phone_pattern, phone))


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Input:
        url: URL string
        
    Output:
        True if valid URL format
    """
    if not url:
        return False
    
    url_pattern = r'^https?://[^\s]+$'
    return bool(re.match(url_pattern, url, re.IGNORECASE))


class InputValidator:
    """
    Fluent input validation helper.
    
    Usage:
        validator = InputValidator(user_input)
        result = validator.required().min_length(3).max_length(100).sanitize()
    """
    
    def __init__(self, value: str):
        self.value = value
        self._errors = []
    
    def required(self, message: str = 'Field is required') -> 'InputValidator':
        """Add required field check"""
        if not self.value or not self.value.strip():
            self._errors.append(message)
        return self
    
    def min_length(self, length: int, message: str = None) -> 'InputValidator':
        """Add minimum length check"""
        if self.value and len(self.value) < length:
            msg = message or f'Minimum length is {length}'
            self._errors.append(msg)
        return self
    
    def max_length(self, length: int, message: str = None) -> 'InputValidator':
        """Add maximum length check"""
        if self.value and len(self.value) > length:
            msg = message or f'Maximum length is {length}'
            self._errors.append(msg)
        return self
    
    def is_email(self, message: str = 'Invalid email format') -> 'InputValidator':
        """Add email format check"""
        if self.value:
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, self.value):
                self._errors.append(message)
        return self
    
    def is_alphanumeric(self, message: str = 'Only letters and numbers allowed') -> 'InputValidator':
        """Add alphanumeric check"""
        if self.value and not self.value.isalnum():
            self._errors.append(message)
        return self
    
    def sanitize(self) -> Tuple[bool, Optional[str]]:
        """Validate and return result"""
        if self._errors:
            return False, '; '.join(self._errors)
        return True, self.value
    
    def get_value(self) -> str:
        """Get the value"""
        return self.value