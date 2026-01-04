#!/usr/bin/env python3

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def debug_sql_field_simple():
    """Debug the SQL field in messages (simple version)"""
    try:
        from api.db_models import async_session, ChatMessage
        from sqlalchemy import select

        conversation_id = "1fa37470-eb3a-4cab-9510-a80c85edb2ca"

        async with async_session() as session:
            result = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at)
            )
            messages = result.scalars().all()

            print("Message analysis:")
            for i, msg in enumerate(messages, 1):
                print(f"{i}. Role: {msg.role}")
                print(f"   Content length: {len(msg.content)}")
                print(f"   Generated SQL: {msg.generated_sql}")
                print(f"   SQL is None: {msg.generated_sql is None}")
                print(f"   SQL or empty: '{msg.generated_sql or ''}'")
                print()

            # Simulate the pairing logic
            print("Pairing simulation:")
            history = []
            for i in range(len(messages) - 1):
                current = messages[i]
                next_msg = messages[i + 1]

                print(f"Checking {i}: {current.role} -> {next_msg.role}")

                if (current.role == "user" and next_msg.role == "assistant"):
                    sql_value = next_msg.generated_sql or ""
                    pair = {
                        "question": current.content,
                        "sql": sql_value
                    }
                    history.append(pair)
                    print(f"  -> ADDED: SQL length = {len(sql_value)}")

            print(f"\nTotal pairs found: {len(history)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_sql_field_simple())
