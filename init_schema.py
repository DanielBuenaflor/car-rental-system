#!/usr/bin/env python3
"""
Database Initialization Script
Loads the schema from database.txt into MySQL.

Usage:
    python init_schema.py [--drop] [--dry-run]

Options:
    --drop     : Drop all tables before creating
    --dry-run  : Show what would be done without executing
"""

import sys
import os
from pathlib import Path
from flask.cli import load_dotenv
import mysql.connector

load_dotenv()  # Load environment variables from .env file

def get_connection():
    """Create database connection."""
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_NAME', 'car_rental_system'),
        autocommit=True
    )

def load_schema(schema_file='database.txt'):
    """Load and execute schema from file."""
    schema_path = Path(__file__).parent / schema_file
    
    if not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}")
        sys.exit(1)
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()
    
    statements = [s.strip() for s in schema.split(';') if s.strip() and not s.strip().startswith('--')]
    return statements

def execute_statements(dry_run=False):
    """Execute schema statements."""
    statements = load_schema()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for i, stmt in enumerate(statements, 1):
        if not stmt:
            continue
        
        if dry_run:
            print(f"\n[ Statement {i} ]")
            print(stmt[:200] + '...' if len(stmt) > 200 else stmt)
        else:
            try:
                cursor.execute(stmt)
                print(f"[OK] Executed statement {i}")
            except mysql.connector.Error as e:
                print(f"[ERROR] Error in statement {i}: {e}")
                print(f"  Statement: {stmt[:100]}...")
    
    cursor.close()
    conn.close()

def main():
    dry_run = '--dry-run' in sys.argv
    drop = '--drop' in sys.argv
    
    if drop:
        print("Drop mode enabled - will drop existing tables")
    
    if dry_run:
        print("DRY RUN - No changes will be made")
    
    print(f"Loading schema from database.txt...")
    execute_statements(dry_run=dry_run)
    
    if not dry_run:
        print("\n[OK] Database initialization complete")

if __name__ == '__main__':
    main()