#!/usr/bin/env python3
import sqlite3
import json

def check_database():
    try:
        conn = sqlite3.connect('storage/metadata.db')
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables found: {tables}")

        # Check use_cases table
        if ('use_cases',) in tables:
            cursor.execute("SELECT COUNT(*) FROM use_cases")
            count = cursor.fetchone()[0]
            print(f"Use cases count: {count}")

            if count > 0:
                cursor.execute("SELECT id, name, business_goal FROM use_cases LIMIT 5")
                use_cases = cursor.fetchall()
                print("Sample use cases:")
                for uc in use_cases:
                    print(f"  ID: {uc[0]}, Name: {uc[1]}, Goal: {uc[2][:50]}...")
        else:
            print("use_cases table does not exist")

        conn.close()
        print("Database check completed successfully")

    except Exception as e:
        print(f"Error checking database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database()

