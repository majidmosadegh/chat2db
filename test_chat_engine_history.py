#!/usr/bin/env python3

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_chat_engine_history():
    """Test chat engine conversation history"""
    try:
        from chat.engine.chat_engine import ChatEngine
        from db import DatabaseConnector
        from api.db_models import async_session

        async with async_session() as session:
            # Create connector (simplified for testing)
            connector = DatabaseConnector(session)

            # Create chat engine
            engine = ChatEngine(session, connector)

            # Test conversation history for the same conversation
            conversation_id = "1fa37470-eb3a-4cab-9510-a80c85edb2ca"
            history = await engine.conversation_manager.get_conversation_history(conversation_id)

            print(f"Conversation history items: {len(history)}")
            for i, item in enumerate(history, 1):
                print(f"{i}. Question length: {len(item['question'])}")
                print(f"   SQL length: {len(item['sql'])}")
                print(f"   SQL preview: {item['sql'][:50] if item['sql'] else 'None'}")

            print("\n✅ Test completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_engine_history())
