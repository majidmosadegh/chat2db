#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_chat_simple_final():
    """Test the chat function with minimal setup and error handling"""
    try:
        print("Testing chat endpoint...")

        # Test the router import
        from api.chat_orchestrator import router
        print("Router imported successfully")

        # Test the function directly
        from api.chat_orchestrator.router import chat_with_orchestrator, ChatMessage
        from api.db_models import async_session

        message = ChatMessage(
            message="Hello",
            session_id="test_session_final",
            snapshot_id=1
        )

        async with async_session() as session:
            result = await chat_with_orchestrator(message, session)
            print(f"Function executed successfully: {result}")

        print("SUCCESS: All tests passed")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_simple_final())