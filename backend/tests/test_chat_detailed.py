#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_chat_detailed():
    """Test the full chat flow step by step"""
    try:
        from api.chat_orchestrator.router import ChatMessage
        from api.db_models import async_session

        # Create a test message
        message = ChatMessage(
            message="Hello",
            session_id="test_session",
            snapshot_id=1
        )

        print("1. ChatMessage created")

        # Get a database session
        async with async_session() as session:
            print("2. Database session created")

            # Import components step by step
            print("3. Importing components...")
            from api.chat_orchestrator.context_manager import ContextManager
            from api.chat_orchestrator.intent_router import IntentRouter
            from api.chat_orchestrator.state_manager import state_manager

            print("4. Creating components...")
            cm = ContextManager("test_session", 1)
            ir = IntentRouter("test_session")

            print("5. Testing intent routing...")
            try:
                result = await ir.route_message("Hello", state_manager.get_or_create_state("test_session"))
                print(f"6. Intent routing success: {result}")
            except Exception as e:
                print(f"6. Intent routing failed: {e}")
                return

            print("7. Testing context manager...")
            try:
                snapshot = await cm.get_active_snapshot(session)
                print(f"8. Context manager success: {snapshot is not None}")
            except Exception as e:
                print(f"8. Context manager failed: {e}")
                return

            print("9. All components working!")

        print("SUCCESS: All tests passed")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_detailed())