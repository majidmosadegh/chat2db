#!/usr/bin/env python3

# Test the router function directly
import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_router():
    try:
        from api.chat_orchestrator.router import ChatMessage

        # Create a test message
        message = ChatMessage(
            message="Hello",
            session_id="test_session",
            snapshot_id=1
        )

        print("SUCCESS: ChatMessage created")
        print(f"Message: {message.message}")
        print(f"Session ID: {message.session_id}")
        print(f"Snapshot ID: {message.snapshot_id}")

        # Now try to import the components
        print("\nTesting component imports...")
        from api.chat_orchestrator.context_manager import ContextManager
        from api.chat_orchestrator.intent_router import IntentRouter
        from api.chat_orchestrator.tool_executor import ToolExecutor
        from api.chat_orchestrator.state_manager import state_manager

        print("SUCCESS: All components imported")

        # Try to create components
        print("\nTesting component creation...")
        cm = ContextManager("test_session", 1)
        ir = IntentRouter("test_session")
        te = ToolExecutor("test_session")

        print("SUCCESS: All components created")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_router())