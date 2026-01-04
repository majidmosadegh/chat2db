#!/usr/bin/env python3

# Test if the chat orchestrator components can be imported
try:
    from api.chat_orchestrator.context_manager import ContextManager
    print("SUCCESS: ContextManager imported")
except Exception as e:
    print(f"ERROR: ContextManager import failed: {e}")

try:
    from api.chat_orchestrator.intent_router import IntentRouter
    print("SUCCESS: IntentRouter imported")
except Exception as e:
    print(f"ERROR: IntentRouter import failed: {e}")

try:
    from api.chat_orchestrator.tool_executor import ToolExecutor
    print("SUCCESS: ToolExecutor imported")
except Exception as e:
    print(f"ERROR: ToolExecutor import failed: {e}")

try:
    from api.chat_orchestrator.state_manager import state_manager
    print("SUCCESS: state_manager imported")
except Exception as e:
    print(f"ERROR: state_manager import failed: {e}")

# Test creating components
try:
    from api.chat_orchestrator.state_manager import state_manager
    state = state_manager.get_or_create_state("test_session")
    print("SUCCESS: State manager works")
except Exception as e:
    print(f"ERROR: State manager failed: {e}")

try:
    from api.chat_orchestrator.intent_router import IntentRouter
    router = IntentRouter("test_session")
    print("SUCCESS: IntentRouter created")
except Exception as e:
    print(f"ERROR: IntentRouter creation failed: {e}")