#!/usr/bin/env python3

# Test if services can be imported
try:
    from services.db_connector import DirectDatabaseConnector
    print("SUCCESS: DatabaseConnector imported")
except Exception as e:
    print(f"ERROR: DatabaseConnector import failed: {e}")

try:
    from services.llm_client import LLMClient
    print("SUCCESS: LLMClient imported")
except Exception as e:
    print(f"ERROR: LLMClient import failed: {e}")

try:
    from services.prompt_builder import PromptBuilder
    print("SUCCESS: PromptBuilder imported")
except Exception as e:
    print(f"ERROR: PromptBuilder import failed: {e}")

# Test creating a simple context manager
try:
    from api.chat_orchestrator.context_manager import ContextManager
    cm = ContextManager("test_session", None)
    print("SUCCESS: ContextManager created")
except Exception as e:
    print(f"ERROR: ContextManager creation failed: {e}")
    import traceback
    traceback.print_exc()