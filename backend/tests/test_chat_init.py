#!/usr/bin/env python3

# Test chat_orchestrator __init__.py
try:
    print("Testing chat_orchestrator __init__.py")
    from api.chat_orchestrator import router
    print("SUCCESS: chat_orchestrator imported")
    print(f"Router has {len(router.routes)} routes")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()