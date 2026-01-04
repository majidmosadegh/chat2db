#!/usr/bin/env python3

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def check_conversation_history():
    """Check conversation history for a specific conversation"""
    try:
        from api.db_models import async_session, ChatMessage
        from sqlalchemy import select

        # Check a specific conversation ID from the previous output
        conversation_id = "1fa37470-eb3a-4cab-9510-a80c85edb2ca"

        async with async_session() as session:
            # Get messages for this conversation
            result = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at)
            )
            messages = result.scalars().all()

            print(f"Messages for conversation {conversation_id}: {len(messages)}")
            print()

            for i, msg in enumerate(messages, 1):
                print(f"{i}. Role: {msg.role}")
                print(f"   Content length: {len(msg.content)} chars")
                print(f"   SQL length: {len(msg.generated_sql) if msg.generated_sql else 0} chars")
                print()

            # Now test the conversation_state_manager logic
            print("Testing conversation_state_manager logic...")
            from chat.engine.conversation_state import ConversationStateManager

            manager = ConversationStateManager(session=session)
            history = await manager.get_conversation_history(conversation_id)

            print(f"Conversation history returned: {len(history)} items")
            for item in history:
                print(f"  Question: {item['question'][:50]}...")
                print(f"  SQL: {item['sql'][:50]}...")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_conversation_history())
