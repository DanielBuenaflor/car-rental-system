"""
Secure Database Helper Module
Provides parameterized query execution to prevent SQL injection.

Usage:
    from MyFlaskApp.utils.secure_db import execute_query, execute_one, fetch_all
    
    # Fetch all results
    results = fetch_all("SELECT * FROM users WHERE role = %s", ('admin',))
    
    # Fetch single result
    user = execute_one("SELECT * FROM users WHERE id = %s", (user_id,))
    
    # Execute INSERT/UPDATE/DELETE
    execute_query("UPDATE users SET name = %s WHERE id = %s", (name, user_id))
"""

import mysql.connector
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from MyFlaskApp import get_db_connection

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass


def validate_params(params: Any) -> Tuple:
    """
    Ensure params is a tuple for parameterized queries.
    
    Input:
        params: Single value or tuple of values
        
    Output:
        Tuple of parameters
    """
    if params is None:
        return ()
    if isinstance(params, (list, set, frozenset)):
        return tuple(params)
    if isinstance(params, tuple):
        return params
    return (params,)


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input to prevent injection via application logic.
    Note: This does NOT prevent SQL injection - use parameterized queries!
    
    Input:
        value: Input string
        max_length: Optional max length limit
        
    Output:
        Sanitized string
    """
    if not value:
        return ""
    
    sanitized = str(value).strip()
    
    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')
    
    # Remove common injection patterns (defense in depth)
    dangerous_patterns = ['--', ';--', '/*', '*/', 'xp_', 'sp_', 'EXEC', 'DROP', 'DELETE FROM', 'TRUNCATE']
    for pattern in dangerous_patterns:
        if pattern.upper() in sanitized.upper():
            logger.warning(f"Potential injection pattern detected: {pattern}")
            # Replace but don't remove completely to allow false positives
            sanitized = sanitized.replace(pattern, pattern.replace('_', ' underscore '))
    
    if max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def build_safe_where(conditions: List[str], params: List[Any], allow_empty: bool = False) -> Tuple[str, Tuple, int]:
    """
    Build safe WHERE clause with parameterized conditions.
    
    Input:
        conditions: List of SQL condition strings (with %s placeholders)
        params: List of parameter values corresponding to conditions
        allow_empty: If False, require at least one condition
        
    Output:
        Tuple of (WHERE clause string, parameters tuple, condition_count)
    """
    if not conditions and not allow_empty:
        raise DatabaseError("At least one condition required")
    
    if not conditions:
        return ("", (), 0)
    
    where_clause = "WHERE " + " AND ".join(conditions)
    param_tuple = validate_params(params)
    
    return (where_clause, param_tuple, len(conditions))


def fetch_all(query: str, params: Optional[Union[Tuple, List, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute SELECT query and fetch all results.
    
    Input:
        query: SQL query with %s placeholders
        params: Parameter values (single value, tuple, or list)
        
    Output:
        List of dictionaries containing row data
        
    Raises:
        DatabaseError: On database error
    """
    conn = get_db_connection()
    if not conn:
        raise DatabaseError("Database connection failed")
    
    cursor = conn.cursor(dictionary=True)
    param_tuple = validate_params(params)
    
    try:
        cursor.execute(query, param_tuple)
        results = cursor.fetchall()
        logger.debug(f"fetch_all: {cursor.rowcount} rows returned")
        return results
    except mysql.connector.Error as e:
        logger.error(f"Database error in fetch_all: {e}")
        raise DatabaseError(f"Query execution failed: {e}")
    finally:
        cursor.close()
        conn.close()


def fetch_one(query: str, params: Optional[Union[Tuple, List, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Execute SELECT query and fetch first result.
    
    Input:
        query: SQL query with %s placeholders
        params: Parameter values
        
    Output:
        Dictionary containing row data, or None if no results
    """
    conn = get_db_connection()
    if not conn:
        raise DatabaseError("Database connection failed")
    
    cursor = conn.cursor(dictionary=True)
    param_tuple = validate_params(params)
    
    try:
        cursor.execute(query, param_tuple)
        result = cursor.fetchone()
        logger.debug(f"fetch_one: {'found' if result else 'not found'}")
        return result
    except mysql.connector.Error as e:
        logger.error(f"Database error in fetch_one: {e}")
        raise DatabaseError(f"Query execution failed: {e}")
    finally:
        cursor.close()
        conn.close()


def execute_query(query: str, params: Optional[Union[Tuple, List, Any]] = None, commit: bool = True) -> int:
    """
    Execute INSERT/UPDATE/DELETE query.
    
    Input:
        query: SQL query with %s placeholders
        params: Parameter values
        commit: Whether to commit the transaction
        
    Output:
        Number of affected rows
        
    Raises:
        DatabaseError: On database error
    """
    conn = get_db_connection()
    if not conn:
        raise DatabaseError("Database connection failed")
    
    cursor = conn.cursor()
    param_tuple = validate_params(params)
    
    try:
        cursor.execute(query, param_tuple)
        
        if commit:
            conn.commit()
        
        affected = cursor.rowcount
        logger.debug(f"execute_query: {affected} rows affected")
        return affected
    except mysql.connector.Error as e:
        logger.error(f"Database error in execute_query: {e}")
        if conn:
            conn.rollback()
        raise DatabaseError(f"Query execution failed: {e}")
    finally:
        cursor.close()
        conn.close()


def execute_many(query: str, params_list: List[Tuple], commit: bool = True) -> int:
    """
    Execute INSERT query with multiple parameter sets (batch insert).
    
    Input:
        query: SQL query with %s placeholders
        params_list: List of parameter tuples
        commit: Whether to commit
        
    Output:
        Number of total affected rows
    """
    conn = get_db_connection()
    if not conn:
        raise DatabaseError("Database connection failed")
    
    cursor = conn.cursor()
    
    try:
        cursor.executemany(query, params_list)
        
        if commit:
            conn.commit()
        
        affected = cursor.rowcount
        logger.debug(f"execute_many: {affected} rows affected")
        return affected
    except mysql.connector.Error as e:
        logger.error(f"Database error in execute_many: {e}")
        if conn:
            conn.rollback()
        raise DatabaseError(f"Batch execution failed: {e}")
    finally:
        cursor.close()
        conn.close()


def get_last_insert_id() -> Optional[int]:
    """
    Get the last inserted AUTO_INCREMENT ID.
    
    Output:
        ID of last inserted row, or None
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT LAST_INSERT_ID()")
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()
        conn.close()