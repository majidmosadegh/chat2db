#!/usr/bin/env python3
import sqlite3

def check_usecases():
    try:
        conn = sqlite3.connect('storage/metadata.db')
        cursor = conn.cursor()

        # Check use cases table
        cursor.execute('SELECT id, name, schema_snapshot_id FROM use_cases')
        rows = cursor.fetchall()

        print('Use cases in database:')
        for row in rows:
            print(f'ID: {row[0]}, Name: {row[1]}, Snapshot ID: {row[2]}')

        # Check if table exists and what columns it has
        cursor.execute("PRAGMA table_info(use_cases)")
        columns = cursor.fetchall()
        print('\nUse cases table columns:')
        for col in columns:
            print(f'  {col[1]} ({col[2]})')

        conn.close()

    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    check_usecases()

