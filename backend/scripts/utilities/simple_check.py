import sqlite3

conn = sqlite3.connect('storage/metadata.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM use_cases')
count = cursor.fetchone()[0]
print(f'Use cases count: {count}')

cursor.execute('SELECT id, name, schema_snapshot_id FROM use_cases LIMIT 2')
rows = cursor.fetchall()
print('Sample rows:')
for row in rows:
    print(f'  {row}')

# Update the snapshot_id
print('Updating schema_snapshot_id to 11...')
cursor.execute('UPDATE use_cases SET schema_snapshot_id = 11')
updated = cursor.rowcount
conn.commit()
print(f'Updated {updated} rows')

# Check after update
cursor.execute('SELECT id, name, schema_snapshot_id FROM use_cases LIMIT 2')
rows = cursor.fetchall()
print('After update:')
for row in rows:
    print(f'  {row}')

conn.close()
print('Done!')