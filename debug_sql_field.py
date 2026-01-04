#!/usr/bin/env python3

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def debug_sql_field():
    """Debug the SQL field in messages"""
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

            print("Detailed message analysis:")
            for i, msg in enumerate(messages, 1):
                print(f"\n{i}. ID: {msg.id}")
                print(f"   Role: {msg.role}")
                print(f"   Content: {repr(msg.content)}")
                print(f"   Generated SQL: {repr(msg.generated_sql)}")
                print(f"   SQL is None: {msg.generated_sql is None}")
                print(f"   SQL length: {len(msg.generated_sql) if msg.generated_sql else 0}")

            # Simulate the pairing logic
            print("\nSimulating pairing logic:")
            history = []
            for i in range(len(messages) - 1):
                current = messages[i]
                next_msg = messages[i + 1]

                if (current.role == "user" and next_msg.role == "assistant"):
                    sql_value = next_msg.generated_sql or ""
                    pair = {
                        "question": current.content,
                        "sql": sql_value
                    }
                    history.append(pair)
                    print(f"Pair {i+1}: '{current.content}' -> SQL: '{sql_value}' (len: {len(sql_value)})")

            print(f"\nFinal history length: {len(history)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_sql_field())
