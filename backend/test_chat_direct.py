#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_chat_direct():
    """Test the chat function directly without HTTP"""
    try:
        print("Testing chat functionality directly...")

        # Test the router import
        from api.chat_orchestrator import router
        print("✓ Router imported successfully")

        # Test the function directly
        from api.chat_orchestrator.router import chat_with_orchestrator, ChatMessageRequest
        from api.db_models import async_session
        print("✓ Chat functions imported successfully")

        message = ChatMessageRequest(
            message="Hello, can you show me some data?",
            session_id="test_session_direct",
            snapshot_id=1
        )
        print("✓ ChatMessageRequest created")

        async with async_session() as session:
            print("✓ Database session created")
            result = await chat_with_orchestrator(message, session)
            print(f"✓ Function executed successfully")
            print(f"Response: {result.response}")
            print(f"Intent: {result.intent_type}")

        print("SUCCESS: Chat functionality works!")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_direct())












