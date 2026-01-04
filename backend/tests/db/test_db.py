import asyncio
import aiosqlite
from config.config import DATABASE_URL
import os

async def test_db():
    try:
        # Extract the database path from the URL
        db_path = DATABASE_URL.replace('sqlite+aiosqlite:///', '')
        print(f'Database path: {db_path}')

        # Check if file exists
        if os.path.exists(db_path):
            print('✅ Database file exists')
        else:
            print('❌ Database file does not exist')
            return

        # Test connection
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute('SELECT 1')
            result = await cursor.fetchone()
            print(f'✅ Database connection successful, test query result: {result}')

            # Check if tables exist
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            table_names = [table[0] for table in tables]
            print(f'📋 Tables in database: {table_names}')

    except Exception as e:
        print(f'❌ Database connection failed: {e}')

if __name__ == "__main__":
    asyncio.run(test_db())
