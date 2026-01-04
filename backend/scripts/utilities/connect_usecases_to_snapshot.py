#!/usr/bin/env python3
import sqlite3

def connect_usecases():
    conn = sqlite3.connect('storage/metadata.db')
    cursor = conn.cursor()

    # بررسی وضعیت فعلی
    cursor.execute('SELECT COUNT(*) FROM use_cases')
    total_count = cursor.fetchone()[0]
    print(f'کل use caseها: {total_count}')

    # بررسی توزیع snapshot_id فعلی
    cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
    distribution = cursor.fetchall()
    print('توزیع فعلی snapshot_id:')
    for sid, count in distribution:
        print(f'  Snapshot {sid}: {count} use case')

    # اتصال همه use caseها به snapshot 11
    cursor.execute('UPDATE use_cases SET schema_snapshot_id = 11')
    updated = cursor.rowcount
    conn.commit()

    print(f'✅ {updated} use case به snapshot 11 متصل شد')

    # بررسی نهایی
    cursor.execute('SELECT schema_snapshot_id, COUNT(*) FROM use_cases GROUP BY schema_snapshot_id')
    final_distribution = cursor.fetchall()
    print('توزیع نهایی:')
    for sid, count in final_distribution:
        print(f'  Snapshot {sid}: {count} use case')

    conn.close()
    print('اتمام عملیات!')

if __name__ == "__main__":
    connect_usecases()
