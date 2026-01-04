#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_tool_executor():
    """Test tool executor creation"""
    try:
        from api.chat_orchestrator.tool_executor import ToolExecutor

        te = ToolExecutor("test_session")
        print("SUCCESS: ToolExecutor created")

        # Try to create a simple context
        context = {
            "active_snapshot": {"id": 1, "name": "test"},
            "data_dictionary": [],
            "relationships": [],
            "llm_context": {"model_name": "test"}
        }

        print("SUCCESS: Test completed")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tool_executor())