#!/usr/bin/env python3

import asyncio
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_api_session():
    """Test the chat session API endpoint"""
    try:
        # Import the router to test the endpoint
        from chat.router import get_chat_session
        from api.db_models import async_session

        conversation_id = "1fa37470-eb3a-4cab-9510-a80c85edb2ca"

        async with async_session() as session:
            result = await get_chat_session(conversation_id, session)

            print(f"Session: {result.session.conversation_id}")
            print(f"Messages count: {len(result.messages)}")

            for i, msg in enumerate(result.messages, 1):
                print(f"\n{i}. Role: {msg.role}")
                print(f"   Content length: {len(msg.content)}")
                print(f"   Generated SQL: {msg.generated_sql}")
                print(f"   Created: {msg.created_at}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_session())
