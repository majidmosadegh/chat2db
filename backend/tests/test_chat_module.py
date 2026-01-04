#!/usr/bin/env python3

# Test if the new chat module can be imported without issues
print("Testing chat module imports...")

try:
    from chat import router
    print("SUCCESS: Chat router imported successfully")
    print(f"Router routes: {len(router.routes)}")
    for route in router.routes:
        print(f"  - {route.methods} {route.path}")
except Exception as e:
    print(f"ERROR: Chat router import failed: {e}")
    import traceback
    traceback.print_exc()

# Test if the schemas can be imported
try:
    from chat.schemas import ChatRequest, ChatResponse, ChatLanguage
    print("SUCCESS: Chat schemas imported successfully")
except Exception as e:
    print(f"ERROR: Chat schemas import failed: {e}")

# Test if the core components can be imported
try:
    from chat.context_loader import ContextLoader
    from chat.prompt_builder import PromptBuilder
    from chat.sql_guard import SQLGuard
    from chat.executor import SQLExecutor
    from chat.orchestrator import ChatOrchestrator
    print("SUCCESS: Chat components imported successfully")
except Exception as e:
    print(f"ERROR: Chat components import failed: {e}")

# Test SQL guard functionality
try:
    guard = SQLGuard()
    # Test valid SQL
    valid_sql = guard.validate_sql("SELECT * FROM users LIMIT 10")
    print(f"SUCCESS: SQL validation works - valid SQL: {valid_sql}")

    # Test invalid SQL
    try:
        guard.validate_sql("DELETE FROM users")
        print("ERROR: SQL guard should have rejected DELETE statement")
    except Exception as e:
        print(f"SUCCESS: SQL guard correctly rejected dangerous SQL: {e}")

except Exception as e:
    print(f"ERROR: SQL guard test failed: {e}")

print("Chat module testing completed.")
