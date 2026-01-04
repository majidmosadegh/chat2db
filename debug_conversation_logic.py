#!/usr/bin/env python3

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def debug_conversation_logic():
    """Debug the conversation history logic"""
    try:
        from api.db_models import async_session, ChatMessage
        from sqlalchemy import select

        conversation_id = "1fa37470-eb3a-4cab-9510-a80c85edb2ca"

        async with async_session() as session:
            # Load messages like conversation_state_manager does
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(10 * 2)  # max_history_entries * 2
            )
            result = await session.execute(stmt)
            messages = result.scalars().all()

            print(f"Raw messages loaded: {len(messages)}")
            for msg in messages:
                print(f"  {msg.role}: {len(msg.content)} chars, SQL: {len(msg.generated_sql or '')} chars")

            # Build history like the code does
            history = []
            messages_sorted = sorted(messages, key=lambda m: m.created_at)

            print(f"\nSorted messages: {len(messages_sorted)}")
            for msg in messages_sorted:
                print(f"  {msg.role}: {msg.content[:30]}..., SQL: {len(msg.generated_sql or '')}")

            print(f"\nBuilding pairs...")
            for i in range(len(messages_sorted) - 1):
                current = messages_sorted[i]
                next_msg = messages_sorted[i + 1]

                print(f"Checking pair {i}: {current.role} -> {next_msg.role}")

                if (current.role == "user" and next_msg.role == "assistant"):
                    pair = {
                        "question": current.content,
                        "sql": next_msg.generated_sql or ""
                    }
                    history.append(pair)
                    print(f"  Added pair: question='{current.content}', sql='{next_msg.generated_sql or ''}'")

            print(f"\nFinal history: {len(history)} items")
            for item in history:
                print(f"  Q: {item['question'][:30]}...")
                print(f"  S: {item['sql'][:30]}...")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_conversation_logic())
