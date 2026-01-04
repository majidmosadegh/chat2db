#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from chat.orchestrator import ChatOrchestrator
from chat.schemas import ChatRequest, ChatLanguage
from db import DatabaseConnector
from api.db_models import get_db_session

async def test_chat_integration():
    """Test the complete chat integration with new architecture"""
    try:
        print("Testing chat integration with new DB architecture...")

        # Create a mock connector for testing
        # We'll create a simple connector that doesn't actually connect to DB
        class MockDatabaseConnector:
            async def execute_readonly(self, sql, limit=100):
                # Return mock data
                if "COUNT" in sql.upper():
                    return [{"total": 42}]
                else:
                    return [
                        {"id": 1, "name": "Test User 1"},
                        {"id": 2, "name": "Test User 2"}
                    ]

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
        connector = MockDatabaseConnector()

        # Test the execution
        result = await orchestrator.execute_chat(request, connector)

        print("✅ Chat execution successful!")
        print(f"Question: {result.question}")
        print(f"SQL: {result.sql}")
        print(f"Row count: {result.row_count}")
        print(f"Status: {result.execution_status}")
        print(f"Sample rows: {result.rows[:2] if result.rows else 'None'}")

        return True

    except Exception as e:
        print(f"❌ Chat integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_chat_integration())
    if success:
        print("\n🎉 All chat integration tests passed!")
    else:
        print("\n💥 Chat integration tests failed!")
