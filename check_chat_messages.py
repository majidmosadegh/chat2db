#!/usr/bin/env python3

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def check_chat_messages():
    """Check ChatMessage records in database"""
    try:
        from api.db_models import async_session, ChatMessage
        from sqlalchemy import select

        async with async_session() as session:
            # Count total messages
            result = await session.execute(
                select(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(20)
            )
            messages = result.scalars().all()

            print(f"Total recent ChatMessage records: {len(messages)}")
            print()

            if messages:
                for i, msg in enumerate(messages, 1):
                    print(f"{i}. ID: {msg.id}")
                    print(f"   Conversation ID: {msg.conversation_id}")
                    print(f"   Session ID: {msg.session_id}")
                    print(f"   Role: {msg.role}")
                    print(f"   Content: {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")
                    print(f"   Generated SQL: {msg.generated_sql[:50] if msg.generated_sql else 'None'}{'...' if msg.generated_sql and len(msg.generated_sql) > 50 else ''}")
                    print(f"   Created: {msg.created_at}")
                    print()
            else:
                print("❌ No ChatMessage records found!")
                print("This explains why conversation history is empty!")

    except Exception as e:
        print(f"❌ Error checking chat messages: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_chat_messages())
