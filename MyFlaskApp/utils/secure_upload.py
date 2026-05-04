"""
Secure File Upload Helper Module
Provides secure file upload validation and processing.

Security Features:
- Allowlist-based extension validation (no allow .exe, .php, etc.)
- Magic byte validation (file signature checking)
- File size limits
- Image dimension validation
- Filename sanitization
- Path traversal protection

Usage:
    from MyFlaskApp.utils.secure_upload import save_upload, validate_upload
    
    # Validate file before saving
    result = validate_upload(file, max_size_mb=5, allowed_extensions={'jpg', 'png'})
    if not result['valid']:
        return jsonify({'error': result['error']}), 400
    
    # Save with automatic sanitization
    filepath = save_upload(file, upload_dir)
"""

import os
import re
import uuid
import io
from PIL import Image
from werkzeug.utils import secure_filename as werkzeug_secure_filename
from typing import Dict, Optional, Tuple, Union, List, Set

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

MAX_FILE_SIZE_MB = 5
MAX_IMAGE_DIMENSION = 4096
MIN_IMAGE_DIMENSION = 50

MAGIC_BYTES = {
    'png': b'\x89PNG\r\n\x1a\n',
    'jpg': b'\xff\xd8\xff',
    'jpeg': b'\xff\xd8\xff',
    'gif': b'GIF87a',
    'gif89': b'GIF89a',
    'webp': b'RIFF',
    'bmp': b'BM',
    'pdf': b'%PDF',
}

class UploadError(Exception):
    """Custom exception for upload errors"""
    pass


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and injection.
    
    Input:
        filename: Original filename
        
    Output:
        Sanitized safe filename
    """
    if not filename:
        return f"file_{uuid.uuid4().hex[:8]}"
    
    basename = os.path.basename(filename)
    
    safe_name = werkzeug_secure_filename(basename)
    
    if not safe_name or safe_name.startswith('.'):
        safe_name = f"file_{uuid.uuid4().hex[:8]}"
    
    name, ext = os.path.splitext(safe_name)
    if ext:
        ext = ext.lower()
    
    return f"{name}{ext}"


def generate_safe_filename(prefix: str = "file", extension: str = "jpg") -> str:
    """
    Generate a safe random filename.
    
    Input:
        prefix: Filename prefix
        extension: File extension (without dot)
        
    Output:
        Safe filename like: prefix_a1b2c3d4.jpg
    """
    safe_ext = extension.lower().lstrip('.')
    random_suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{random_suffix}.{safe_ext}"


def validate_magic_bytes_from_stream(file, expected_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate file content matches expected type via magic bytes.
    Works with both FileStorage objects (in memory) and file paths.
    
    Input:
        file: FileStorage object or file path
        expected_type: Expected file type (png, jpg, gif, webp, pdf)
        
    Output:
        Tuple of (is_valid, error_message)
    """
    try:
        if hasattr(file, 'seek') and hasattr(file, 'read'):
            # FileStorage object - read from memory
            file.seek(0)
            header = file.read(16)
            file.seek(0)
        else:
            # File path - read from disk
            with open(file, 'rb') as f:
                header = f.read(16)
        
        expected_type = expected_type.lower()
        
        if expected_type in ('jpg', 'jpeg'):
            if header[:3] != MAGIC_BYTES['jpg']:
                return False, f"File is not a valid JPEG image"
        elif expected_type == 'png':
            if header[:8] != MAGIC_BYTES['png']:
                return False, f"File is not a valid PNG image"
        elif expected_type == 'gif':
            if header[:6] not in (MAGIC_BYTES['gif'], MAGIC_BYTES['gif89']):
                return False, f"File is not a valid GIF image"
        elif expected_type == 'webp':
            if header[:4] != MAGIC_BYTES['webp']:
                return False, f"File is not a valid WebP image"
        elif expected_type == 'bmp':
            if header[:2] != MAGIC_BYTES['bmp']:
                return False, f"File is not a valid BMP image"
        elif expected_type == 'pdf':
            if header[:4] != MAGIC_BYTES['pdf']:
                return False, f"File is not a valid PDF document"
        else:
            return False, f"Unsupported file type for magic bytes check"
        
        return True, None
    except Exception as e:
        return False, f"Magic bytes validation error: {str(e)}"


def validate_magic_bytes(file_path: str, expected_type: str) -> bool:
    """
    Validate file content matches expected type via magic bytes.
    
    Input:
        file_path: Path to file
        expected_type: Expected file type (png, jpg, gif, webp, pdf)
        
    Output:
        True if magic bytes match
    """
    valid, _ = validate_magic_bytes_from_stream(file_path, expected_type)
    return valid


def get_file_extension(filename: str) -> Optional[str]:
    """
    Get safe file extension from filename.
    
    Input:
        filename: Filename
        
    Output:
        Lowercase extension without dot, or None
    """
    if not filename or '.' not in filename:
        return None
    
    ext = filename.rsplit('.', 1)[1].lower().strip()
    return ext if ext else None


def validate_extension(filename: str, allowed_extensions: Set[str], allowlist_mode: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate file extension against allowlist/blocklist.
    
    Input:
        filename: Filename to validate
        allowed_extensions: Set of allowed/blocked extensions
        allowlist_mode: If True, only these extensions allowed. If False, these are blocked.
        
    Output:
        Tuple of (is_valid, error_message)
    """
    ext = get_file_extension(filename)
    
    if not ext:
        return False, "File has no extension"
    
    ext = ext.lower()
    
    if allowlist_mode:
        if ext not in allowed_extensions:
            return False, f"Extension .{ext} not allowed. Allowed: {', '.join(allowed_extensions)}"
    else:
        if ext in allowed_extensions:
            return False, f"Extension .{ext} is not permitted"
    
    return True, None


def validate_file_size(file_or_path: Union[object, str], max_size_mb: int = MAX_FILE_SIZE_MB) -> Tuple[bool, Optional[str]]:
    """
    Validate file size is within limits.
    
    Input:
        file_or_path: FileStorage object or file path
        max_size_mb: Maximum file size in MB
        
    Output:
        Tuple of (is_valid, error_message)
    """
    max_bytes = max_size_mb * 1024 * 1024
    
    if hasattr(file_or_path, 'seek') and hasattr(file_or_path, 'tell'):
        file_or_path.seek(0, 2)
        size = file_or_path.tell()
        file_or_path.seek(0)
    else:
        try:
            size = os.path.getsize(file_or_path)
        except Exception:
            return False, "Cannot determine file size"
    
    if size > max_bytes:
        return False, f"File too large. Maximum size: {max_size_mb}MB"
    
    if size == 0:
        return False, "File is empty"
    
    return True, None


def validate_image_dimensions(file_or_path: Union[object, str], 
                            max_dimension: int = MAX_IMAGE_DIMENSION,
                            min_dimension: int = MIN_IMAGE_DIMENSION) -> Tuple[bool, Optional[str]]:
    """
    Validate image dimensions are within acceptable range.
    Note: This requires the file to be a valid image.
    Uses PIL to verify the image can be opened and read.
    
    Input:
        file_or_path: FileStorage object or file path
        max_dimension: Maximum width or height
        min_dimension: Minimum width or height
        
    Output:
        Tuple of (is_valid, error_message)
    """
    try:
        if hasattr(file_or_path, 'seek'):
            # FileStorage object - read into BytesIO to avoid stream issues
            file_or_path.seek(0)
            file_data = file_or_path.read()
            file_or_path.seek(0)
            img = Image.open(io.BytesIO(file_data))
        else:
            img = Image.open(file_or_path)
        
        # Try to load the image to verify it's valid
        # This will raise an exception if the image is invalid
        img.load()
        
        width, height = img.size
        
        img.close()
        
        if width > max_dimension or height > max_dimension:
            return False, f"Image too large. Maximum dimension: {max_dimension}px"
        
        if width < min_dimension or height < min_dimension:
            return False, f"Image too small. Minimum dimension: {min_dimension}px"
        
        # Reset file pointer after reading
        if hasattr(file_or_path, 'seek'):
            file_or_path.seek(0)
        
        return True, None
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"


def validate_upload(file, 
                 allowed_extensions: Optional[Set[str]] = None,
                 max_size_mb: int = MAX_FILE_SIZE_MB,
                 check_dimensions: bool = True,
                 check_magic_bytes: bool = True) -> Dict[str, Union[bool, str, None]]:
    """
    Comprehensive file upload validation.
    
    Input:
        file: Werkzeug FileStorage object
        allowed_extensions: Set of allowed extensions (default: ALLOWED_IMAGE_EXTENSIONS)
        max_size_mb: Maximum file size in MB
        check_dimensions: Validate image dimensions
        check_magic_bytes: Validate file magic bytes
        
    Output:
        Dictionary with keys: valid, error, extension, size
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_IMAGE_EXTENSIONS
    
    if not file or not file.filename:
        return {'valid': False, 'error': 'No file provided', 'extension': None, 'size': 0}
    
    filename = file.filename
    
    valid, error = validate_extension(filename, allowed_extensions)
    if not valid:
        return {'valid': False, 'error': error, 'extension': None, 'size': 0}
    
    ext = get_file_extension(filename)
    
    valid, error = validate_file_size(file, max_size_mb)
    if not valid:
        return {'valid': False, 'error': error, 'extension': ext, 'size': 0}
    
    # Check magic bytes to verify file content matches extension
    if check_magic_bytes and ext in MAGIC_BYTES:
        valid, error = validate_magic_bytes_from_stream(file, ext)
        if not valid:
            return {'valid': False, 'error': error, 'extension': ext, 'size': 0}
    
    if check_dimensions and ext in {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}:
        valid, error = validate_image_dimensions(file)
        if not valid:
            return {'valid': False, 'error': error, 'extension': ext, 'size': 0}
    
    # Reset file pointer after validation so it can be saved later
    if hasattr(file, 'seek'):
        try:
            file.seek(0)
        except Exception:
            pass
    
    return {'valid': True, 'error': None, 'extension': ext, 'size': None}


def save_upload(file, 
               upload_dir: str,
               allowed_extensions: Optional[Set[str]] = None,
               max_size_mb: int = MAX_FILE_SIZE_MB,
               prefix: str = "file",
               check_dimensions: bool = True,
               check_magic_bytes: bool = True,
               generate_unique_name: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    Save uploaded file with full validation and sanitization.
    
    Input:
        file: Werkzeug FileStorage object
        upload_dir: Directory to save file
        allowed_extensions: Set of allowed extensions
        max_size_mb: Maximum file size in MB
        prefix: Filename prefix if generating unique name
        check_dimensions: Validate image dimensions
        check_magic_bytes: Validate magic bytes
        generate_unique_name: Generate unique name instead of using original
        
    Output:
        Tuple of (saved_filename, error_message)
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_IMAGE_EXTENSIONS
    
    validation = validate_upload(file, allowed_extensions, max_size_mb, check_dimensions, check_magic_bytes)
    if not validation['valid']:
        return None, validation['error']
    
    os.makedirs(upload_dir, exist_ok=True)
    
    ext = validation['extension']
    
    if generate_unique_name:
        filename = generate_safe_filename(prefix, ext)
    else:
        filename = sanitize_filename(file.filename)
        if get_file_extension(filename) != ext:
            name = os.path.splitext(filename)[0]
            filename = f"{name}.{ext}"
    
    filepath = os.path.join(upload_dir, filename)
    
    temp_path = filepath + '.tmp'
    try:
        # Reset file pointer to beginning before saving
        if hasattr(file, 'seek'):
            file.seek(0)
        
        file.save(temp_path)
        
        os.rename(temp_path, filepath)
        return filename, None
        
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None, f"Error saving file: {str(e)}"


def save_base64_upload(base64_data: str,
                      upload_dir: str,
                      allowed_extensions: Optional[Set[str]] = None,
                      max_size_mb: int = MAX_FILE_SIZE_MB,
                      prefix: str = "file",
                      check_magic_bytes: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    Save base64-encoded image with validation.
    
    Input:
        base64_data: Base64 encoded string (may include data URI prefix)
        upload_dir: Directory to save file
        allowed_extensions: Set of allowed extensions
        max_size_mb: Maximum file size in MB
        prefix: Filename prefix
        
    Output:
        Tuple of (saved_filename, error_message)
    """
    import base64
    if not base64_data:
        return None, "No data provided"
    
    try:
        if ',' in base64_data:
            header, base64_data = base64_data.split(',', 1)
            
            if 'image/png' in header or 'png' in header:
                ext = 'png'
            elif 'image/jpeg' in header or 'jpeg' in header or 'jpg' in header:
                ext = 'jpg'
            elif 'image/gif' in header:
                ext = 'gif'
            elif 'image/webp' in header:
                ext = 'webp'
            else:
                ext = 'jpg'
        else:
            ext = 'jpg'
        
        if ext not in allowed_extensions:
            return None, f"Extension .{ext} not allowed"
        
        import base64 as b64_module
        image_bytes = b64_module.b64decode(base64_data)
        
        size = len(image_bytes)
        if size > max_size_mb * 1024 * 1024:
            return None, f"File too large. Maximum: {max_size_mb}MB"
        
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = generate_safe_filename(prefix, ext)
        filepath = os.path.join(upload_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        if check_magic_bytes(ext):
            if not validate_magic_bytes(filepath, ext):
                os.remove(filepath)
                return None, "Invalid image content"
        
        return filename, None
        
    except b64_module.binascii.Error:
        return None, "Invalid base64 data"
    except Exception as e:
        return None, f"Error saving image: {str(e)}"