#!/usr/bin/env python3
from sqlalchemy import create_engine, text
import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from api.database import decrypt_password

def get_connection_info():
    # Get the encrypted password from database
    import sqlite3
    conn = sqlite3.connect('storage/metadata.db')
    cursor = conn.cursor()
    cursor.execute('SELECT password_encrypted FROM database_connections WHERE id = 7')
    encrypted_password = cursor.fetchone()[0]
    conn.close()

    password = decrypt_password(encrypted_password)

    return {
        'db_type': 'sqlserver',
        'host': '172.16.31.12',
        'port': 1433,
        'username': 'Sa',
        'password': password,
        'database_name': 'AI_db'
    }

def test_sync_connection():
    try:
        info = get_connection_info()
        print(f"Testing sync connection to {info['host']}:{info['port']}/{info['database_name']}")

        # Build connection string
        from api.database import build_connection_string
        connection_string = build_connection_string(**info)
        print(f"Connection string: {connection_string}")

        # Create sync engine
        engine = create_engine(connection_string, echo=True)

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"Connection successful! Test result: {row}")

        engine.dispose()
        print("SUCCESS: Connection successful!")

    except Exception as e:
        print(f"ERROR: Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sync_connection()
