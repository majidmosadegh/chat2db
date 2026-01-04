#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from api.db_models import UseCase, get_db_session

async def update_use_cases():
    async with get_db_session() as session:
        # Get all use cases
        result = await session.execute('SELECT id, name, schema_snapshot_id FROM use_cases')
        use_cases = result.fetchall()

        print('Current use cases:')
        for uc in use_cases:
            print(f'ID: {uc[0]}, Name: {uc[1]}, Snapshot ID: {uc[2]}')

        # Update use cases that don't have schema_snapshot_id set
        await session.execute('UPDATE use_cases SET schema_snapshot_id = 11 WHERE schema_snapshot_id IS NULL')
        await session.commit()

        # Check updated use cases
        result = await session.execute('SELECT id, name, schema_snapshot_id FROM use_cases')
        updated_use_cases = result.fetchall()

        print('\nUpdated use cases:')
        for uc in updated_use_cases:
            print(f'ID: {uc[0]}, Name: {uc[1]}, Snapshot ID: {uc[2]}')

if __name__ == "__main__":
    asyncio.run(update_use_cases())

