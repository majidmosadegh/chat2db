#!/usr/bin/env python3

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_final_conversation_history():
    """Final test of conversation history fix"""
    try:
        from api.db_models import async_session
        from chat.engine.conversation_state import ConversationStateManager

        conversation_id = "1fa37470-eb3a-4cab-9510-a80c85edb2ca"

        async with async_session() as session:
            manager = ConversationStateManager(session=session)
            history = await manager.get_conversation_history(conversation_id)

            print(f"Conversation history now returns: {len(history)} items")
            print("This should be 1 item (only the one with SQL)")

            if len(history) == 1:
                print("SUCCESS: Conversation history is now properly filtered!")
                print("Only SQL queries are included in history for better LLM context.")
            else:
                print(f"ISSUE: Expected 1 item, got {len(history)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_final_conversation_history())
