#!/usr/bin/env python3
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pymssql
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from db.security import decrypt_password

async def test_direct_pymssql():
    """Test pymssql connection directly"""
    try:
        # Get connection info from database
        import sqlite3
        conn = sqlite3.connect('storage/metadata.db')
        cursor = conn.cursor()
        cursor.execute('SELECT password_encrypted FROM database_connections WHERE id = 7')
        encrypted_password = cursor.fetchone()[0]
        conn.close()

        password = decrypt_password(encrypted_password)

        print("Testing direct pymssql connection...")

        def _connect_sync():
            return pymssql.connect(
                host='172.16.31.12',
                port=1433,
                user='Sa',
                password=password,
                database='AI_db'
            )

        # Test connection in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            db_conn = await loop.run_in_executor(executor, _connect_sync)

            def _query_sync():
                cursor = db_conn.cursor(as_dict=True)
                cursor.execute("SELECT TOP 5 * FROM EnergyExchange")
                results = cursor.fetchall()
                cursor.close()
                db_conn.close()
                return results

            results = await loop.run_in_executor(executor, _query_sync)

            print(f"Query successful! Retrieved {len(results)} rows")
            if results:
                print("Sample row:", results[0])

            return True

    except Exception as e:
        print(f"Direct pymssql test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_direct_pymssql())
    print(f"Test result: {'SUCCESS' if success else 'FAILED'}")
