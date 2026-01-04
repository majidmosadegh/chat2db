#!/usr/bin/env python3

import sqlite3
import os

def test_database():
    db_path = os.path.join('storage', 'metadata.db')
    print(f'Checking database: {db_path}')
    print(f'Exists: {os.path.exists(db_path)}')

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f'Tables: {[t[0] for t in tables]}')

            # Check if llm_models table has data
            try:
                cursor.execute('SELECT COUNT(*) FROM llm_models')
                count = cursor.fetchone()[0]
                print(f'LLM models count: {count}')
            except sqlite3.OperationalError as e:
                print(f'llm_models table error: {e}')

            conn.close()
            print('Database is accessible')

        except Exception as e:
            print(f'Database error: {e}')
    else:
        print('Database file not found')

if __name__ == "__main__":
    test_database()










