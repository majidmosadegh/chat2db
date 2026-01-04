#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_startup():
    """Test the startup components"""
    try:
        print("Testing state manager startup...")
        from api.chat_orchestrator.state_manager import state_manager

        print("Starting cleanup task...")
        await state_manager.start_cleanup_task()

        print("Getting or creating state...")
        state = state_manager.get_or_create_state("startup_test")

        print("SUCCESS: Startup components working")

        # Cleanup
        await state_manager.stop_cleanup_task()

    except Exception as e:
        print(f"ERROR: Startup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_startup())