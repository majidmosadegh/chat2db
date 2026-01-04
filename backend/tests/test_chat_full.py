#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_chat_full():
    """Test the full chat execution with proper error handling"""
    try:
        from api.chat_orchestrator.router import chat_with_orchestrator, ChatMessage
        from api.db_models import async_session

        # Create a test message
        message = ChatMessage(
            message="Hello",
            session_id="test_session_full",
            snapshot_id=1
        )

        print("1. Created ChatMessage")

        # Get a database session
        async with async_session() as session:
            print("2. Created database session")

            try:
                print("3. Calling chat_with_orchestrator...")
                result = await chat_with_orchestrator(message, session)
                print("4. SUCCESS: Chat function completed")
                print(f"5. Result: {result}")
            except Exception as e:
                print(f"4. ERROR in chat execution: {e}")
                import traceback
                traceback.print_exc()

        print("SUCCESS: Test completed")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_full())