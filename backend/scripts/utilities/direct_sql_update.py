#!/usr/bin/env python3
import sqlite3

def update_usecases():
    try:
        conn = sqlite3.connect('storage/metadata.db')
        cursor = conn.cursor()

        # Check current state
        cursor.execute('SELECT COUNT(*) FROM use_cases')
        count = cursor.fetchone()[0]
        print(f'Total use cases: {count}')

        # Check current snapshot_ids
        cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
        snapshot_counts = cursor.fetchall()
        print('Snapshot ID distribution:')
        for sid, cnt in snapshot_counts:
            print(f'  Snapshot {sid}: {cnt} use cases')

        # Update NULL and 0 values to 11
        cursor.execute('UPDATE use_cases SET schema_snapshot_id = 11 WHERE schema_snapshot_id IS NULL OR schema_snapshot_id = 0')
        updated_count = cursor.rowcount
        conn.commit()

        print(f'Updated {updated_count} use cases')

        # Check after update
        cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
        snapshot_counts = cursor.fetchall()
        print('After update - Snapshot ID distribution:')
        for sid, cnt in snapshot_counts:
            print(f'  Snapshot {sid}: {cnt} use cases')

        conn.close()
        print('Database updated successfully!')

    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_usecases()

