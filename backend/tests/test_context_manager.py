#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_context_manager():
    """Test context manager directly"""
    try:
        from api.db_models import async_session

        async with async_session() as session:
            from api.chat_orchestrator.context_manager import ContextManager

            cm = ContextManager("test_session", 1)
            print("SUCCESS: ContextManager created")

            # Try to get active snapshot
            try:
                snapshot = await cm.get_active_snapshot(session)
                print(f"SUCCESS: Got snapshot: {snapshot}")
            except Exception as e:
                print(f"WARNING: Could not get snapshot: {e}")

        print("SUCCESS: Test completed")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_context_manager())