#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.connector import DatabaseConnector
from db.models import Snapshot, DatabaseConnection

async def test_connector():
    """Test the DatabaseConnector directly"""
    try:
        print("Testing DatabaseConnector...")

        # Create connection and snapshot objects
        db_conn = DatabaseConnection(
            id=7,
            db_type="sqlserver",
            host="172.16.31.12",
            port=1433,
            username="Sa",
            encrypted_password="dummy",  # Will be overridden in security.py
            database_name="AI_db",
            is_active=True
        )

        snapshot = Snapshot(
            id=11,
            name="Production_snapshot_fix",
            database_connection_id=7,
            is_active=True
        )

        # Create connector
        connector = DatabaseConnector(snapshot, db_conn)

        # Test connection
        print("Testing connection...")
        connection_ok = await connector.test_connection()
        print(f"Connection test: {'SUCCESS' if connection_ok else 'FAILED'}")

        if connection_ok:
            # Test query execution
            print("Testing query execution...")
            results = await connector.execute_readonly("SELECT TOP 3 * FROM EnergyExchange")
            print(f"Query successful! Retrieved {len(results)} rows")

            # Test table info
            print("Testing table info...")
            tables = await connector.get_table_info()
            print(f"Found {len(tables)} tables")
            if tables:
                print(f"Sample tables: {[t['table_name'] for t in tables[:3]]}")

        return connection_ok

    except Exception as e:
        print(f"Connector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connector())
    print(f"\nFinal result: {'SUCCESS' if success else 'FAILED'}")

