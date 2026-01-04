import sqlite3
import os

db_path = 'backend/storage/metadata.db'
print(f'Checking database: {db_path}')
print(f'File exists: {os.path.exists(db_path)}')

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    print(f'Found {len(tables)} tables:')
    for table in tables:
        table_name = table[0]
        print(f'Table: {table_name}')

        # Count records
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'  Records: {count}')

        if count > 0:
            # Show first record
            cursor.execute(f'SELECT * FROM {table_name} LIMIT 1')
            sample = cursor.fetchone()
            print(f'  Sample: {sample}')
        print()

    conn.close()
else:
    print('Database file does not exist!')








