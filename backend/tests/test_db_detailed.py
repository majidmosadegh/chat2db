#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from chat.executor import SQLExecutor
from api.db_models import get_db_session

async def test_db_connection_detailed():
    try:
        async for session in get_db_session():
            executor = SQLExecutor(session)

            print('Getting connection info for snapshot 11...')
            connection_info = await executor._get_connection_info(11)
            print('Connection info:')
            for key, value in connection_info.items():
                if key == 'password':
                    print(f'  {key}: [HIDDEN]')
                else:
                    print(f'  {key}: {value}')

            print('\nTesting connection...')
            result = await executor.test_connection(11)
            print('Connection test result:', result)

            break
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_db_connection_detailed())
