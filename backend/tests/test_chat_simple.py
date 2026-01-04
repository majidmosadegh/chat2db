#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from chat.orchestrator import ChatOrchestrator
from chat.schemas import ChatRequest, ChatLanguage

async def test_chat_simple():
    """Simple test of chat orchestrator"""
    try:
        print("Testing chat orchestrator...")

        # Create test request
        request = ChatRequest(
            snapshot_id=11,
            model_id=4,
            language=ChatLanguage.ENGLISH,
            question="Show me all users"
        )

        # Create orchestrator
        orchestrator = ChatOrchestrator()

        # Create mock connector
        class MockConnector:
            async def execute_readonly(self, sql, limit=100):
                return [{"id": 1, "name": "Test User"}]

        connector = MockConnector()

        # Test execution
        result = await orchestrator.execute_chat(request, connector)

        print("SUCCESS: Chat execution completed")
        print(f"SQL: {result.sql}")
        print(f"Rows: {len(result.rows)}")
        print(f"Status: {result.execution_status}")

        return result.execution_status == "success"

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_chat_simple())
    print(f"Test result: {'PASSED' if success else 'FAILED'}")