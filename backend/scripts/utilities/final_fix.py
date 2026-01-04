#!/usr/bin/env python3
import sqlite3
import sys

print("Starting database fix...", flush=True)

try:
    # Connect to database
    conn = sqlite3.connect('storage/metadata.db')
    cursor = conn.cursor()
    print("Connected to database", flush=True)

    # Check current state
    cursor.execute('SELECT COUNT(*) FROM use_cases')
    total_count = cursor.fetchone()[0]
    print(f'Total use cases: {total_count}', flush=True)

    # Check snapshot distribution
    cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
    snapshot_counts = cursor.fetchall()
    print('Current snapshot distribution:', flush=True)
    for sid, cnt in snapshot_counts:
        print(f'  Snapshot {sid}: {cnt} use cases', flush=True)

    # Update all use cases to snapshot_id = 11
    print("Updating all use cases to snapshot_id = 11...", flush=True)
    cursor.execute('UPDATE use_cases SET schema_snapshot_id = 11')
    updated_count = cursor.rowcount
    conn.commit()
    print(f'Updated {updated_count} use cases', flush=True)

    # Verify
    cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
    final_counts = cursor.fetchall()
    print('Final snapshot distribution:', flush=True)
    for sid, cnt in final_counts:
        print(f'  Snapshot {sid}: {cnt} use cases', flush=True)

    conn.close()
    print("✅ Database fix completed successfully!", flush=True)

except Exception as e:
    print(f'❌ Error: {e}', flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

