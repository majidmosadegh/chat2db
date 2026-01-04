import asyncio
import aiosqlite
import os

async def check_db():
    db_path = 'storage/metadata.db'
    print(f'Checking database: {db_path}')

    if not os.path.exists(db_path):
        print('❌ Database file does not exist!')
        return

    async with aiosqlite.connect(db_path) as conn:
        # Get all tables
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()

        print(f'📋 Found {len(tables)} tables:')
        for table in tables:
            table_name = table[0]
            print(f'  - {table_name}')

            # Count records in each table
            cursor = await conn.execute(f'SELECT COUNT(*) FROM {table_name}')
            count = await cursor.fetchone()
            print(f'    Records: {count[0]}')

            # Show sample data if exists
            if count[0] > 0:
                try:
                    cursor = await conn.execute(f'SELECT * FROM {table_name} LIMIT 1')
                    sample = await cursor.fetchone()
                    print(f'    Sample: {sample}')
                except:
                    print('    Sample: (error reading data)')

if __name__ == "__main__":
    asyncio.run(check_db())








