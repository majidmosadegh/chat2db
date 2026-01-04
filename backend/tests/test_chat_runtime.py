#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_chat_runtime():
    """Test the chat endpoint at runtime"""
    try:
        # Import FastAPI TestClient
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        # Create app
        app = FastAPI()

        # Import and include router at runtime (like main.py does)
        try:
            from api import chat_orchestrator
            app.include_router(chat_orchestrator.router, prefix="/api/chat-orchestrator", tags=["chat-orchestrator"])
            print("SUCCESS: Chat orchestrator router included at runtime")
        except Exception as e:
            print(f"ERROR: Failed to include chat router: {e}")
            return

        # Create test client
        client = TestClient(app)

        # Test the endpoint
        response = client.post(
            "/api/chat-orchestrator/chat",
            json={"message": "test", "session_id": "test"}
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            print("SUCCESS: Chat endpoint works!")
        else:
            print(f"ERROR: Chat endpoint failed with status {response.status_code}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_runtime())