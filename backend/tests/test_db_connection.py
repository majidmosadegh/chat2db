#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from chat.executor import SQLExecutor
from api.db_models import get_db_session

async def test_db_connection():
    try:
        async for session in get_db_session():
            executor = SQLExecutor(session)

            print('Testing database connection for snapshot 11...')
            result = await executor.test_connection()
            print('Connection test result:', result)

            if result:
                # Try a simple query
                execution_result = await executor.execute_query(11, 'SELECT 1 as test')
                print('Simple query result:', execution_result)
            break
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_db_connection())
