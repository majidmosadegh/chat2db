#!/usr/bin/env python3
import pymssql
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
        'host': '172.16.31.12',
        'port': 1433,
        'user': 'Sa',
        'password': password,
        'database': 'AI_db'
    }

def test_pymssql_connection():
    try:
        info = get_connection_info()
        print(f"Testing pymssql connection to {info['host']}:{info['port']}/{info['database']}")
        print(f"Username: {info['user']}")

        # Connect using pymssql
        conn = pymssql.connect(**info)
        cursor = conn.cursor()

        # Test query
        cursor.execute("SELECT 1 as test")
        row = cursor.fetchone()
        print(f"Connection successful! Test result: {row}")

        # Get some table info
        cursor.execute("SELECT TOP 5 TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        tables = cursor.fetchall()
        print(f"Available tables: {[t[0] for t in tables]}")

        cursor.close()
        conn.close()
        print("SUCCESS: pymssql connection successful!")

    except Exception as e:
        print(f"ERROR: pymssql connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pymssql_connection()
