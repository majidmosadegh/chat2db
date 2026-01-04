import sqlite3

conn = sqlite3.connect('backend/storage/metadata.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print(f"Found {len(tables)} tables:")
for table in tables:
    table_name = table[0]
    print(f"Table: {table_name}")

    # Count records
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  Records: {count}")

    if count > 0:
        print(f"  Has data: YES")
    else:
        print(f"  Has data: NO")
    print()

conn.close()








