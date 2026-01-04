#!/usr/bin/env python3

# Standalone test of chat module components that don't require relative imports

print("Testing chat module components...")

# Test schemas
try:
    from chat.schemas import ChatRequest, ChatResponse, ChatLanguage
    print("SUCCESS: Chat schemas imported successfully")

    # Test enum
    assert ChatLanguage.ENGLISH == "en"
    assert ChatLanguage.PERSIAN == "fa"
    print("SUCCESS: Chat language enum works correctly")

    # Test models
    request = ChatRequest(snapshot_id=1, model_id=1, language=ChatLanguage.ENGLISH, question="Show me users")
    assert request.question == "Show me users"
    print("SUCCESS: ChatRequest model works correctly")

except Exception as e:
    print(f"ERROR: Schemas test failed: {e}")
    import traceback
    traceback.print_exc()

# Test SQL guard (doesn't need imports)
try:
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from chat.sql_guard import SQLGuard

    guard = SQLGuard()

    # Test valid SQL
    valid_sql = guard.validate_sql("SELECT * FROM users LIMIT 10")
    print(f"SUCCESS: SQL validation works - valid SQL: {valid_sql}")

    # Test invalid SQL
    try:
        guard.validate_sql("DELETE FROM users")
        print("ERROR: SQL guard should have rejected DELETE statement")
    except Exception as e:
        print(f"SUCCESS: SQL guard correctly rejected dangerous SQL: {type(e).__name__}")

    # Test another dangerous SQL
    try:
        guard.validate_sql("INSERT INTO users VALUES (1, 'test')")
        print("ERROR: SQL guard should have rejected INSERT statement")
    except Exception as e:
        print(f"SUCCESS: SQL guard correctly rejected INSERT SQL: {type(e).__name__}")

except Exception as e:
    print(f"ERROR: SQL guard test failed: {e}")
    import traceback
    traceback.print_exc()

print("Chat module standalone testing completed.")
