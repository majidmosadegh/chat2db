#!/usr/bin/env python3
import sqlite3
import sys

def fix_usecases():
    print("Starting to fix use cases...", flush=True)
    try:
        conn = sqlite3.connect('storage/metadata.db')
        cursor = conn.cursor()
        print("Connected to database", flush=True)

        # Check current state
        cursor.execute('SELECT COUNT(*) FROM use_cases')
        total_count = cursor.fetchone()[0]
        print(f'Total use cases: {total_count}', flush=True)

        # Check current snapshot_ids
        cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
        snapshot_counts = cursor.fetchall()
        print('Current snapshot ID distribution:', flush=True)
        for sid, cnt in snapshot_counts:
            print(f'  Snapshot {sid}: {cnt} use cases', flush=True)

        # Update all use cases to have schema_snapshot_id = 11
        print("Running UPDATE query...", flush=True)
        cursor.execute('UPDATE use_cases SET schema_snapshot_id = 11 WHERE schema_snapshot_id IS NULL OR schema_snapshot_id != 11')
        updated_count = cursor.rowcount
        conn.commit()
        print(f'Updated {updated_count} use cases to snapshot_id = 11', flush=True)

        # Verify the update
        cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
        updated_counts = cursor.fetchall()
        print('After update - Snapshot ID distribution:', flush=True)
        for sid, cnt in updated_counts:
            print(f'  Snapshot {sid}: {cnt} use cases', flush=True)

        print('✅ Use cases successfully linked to snapshot 11!', flush=True)

    except Exception as e:
        print(f'❌ Error: {e}', flush=True)
        import traceback
        traceback.print_exc()
        conn.rollback()

    finally:
        conn.close()

if __name__ == "__main__":
    fix_usecases()