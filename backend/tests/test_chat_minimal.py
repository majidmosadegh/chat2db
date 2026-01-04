#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_chat_minimal():
    try:
        from api.chat_orchestrator.router import ChatMessage
        from api.db_models import get_db_session
        from sqlalchemy.ext.asyncio import AsyncSession

        # Create a test message
        message = ChatMessage(
            message="Hello",
            session_id="test_session",
            snapshot_id=1
        )

        print("SUCCESS: ChatMessage created")

        # Get a database session
        async with get_db_session() as session:
            print("SUCCESS: Database session created")

            # Try to import and create components
            from api.chat_orchestrator.context_manager import ContextManager
            from api.chat_orchestrator.intent_router import IntentRouter
            from api.chat_orchestrator.state_manager import state_manager

            cm = ContextManager("test_session", 1)
            ir = IntentRouter("test_session")

            print("SUCCESS: Components created")

            # Try to get active snapshot (this might fail if no snapshot exists)
            try:
                snapshot = await cm.get_active_snapshot(session)
                print(f"SUCCESS: Got snapshot: {snapshot}")
            except Exception as e:
                print(f"WARNING: Could not get active snapshot: {e}")

            # Try intent routing
            try:
                result = await ir.route_message("Hello", state_manager.get_or_create_state("test_session"))
                print(f"SUCCESS: Intent routing worked: {result}")
            except Exception as e:
                print(f"ERROR: Intent routing failed: {e}")

        print("SUCCESS: Test completed")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_minimal())