#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_chat_minimal2():
    """Test just the router creation and import"""
    try:
        print("Testing router import...")
        from api.chat_orchestrator import router
        print("SUCCESS: Router imported")

        print("Testing router routes...")
        print(f"Routes: {len(router.routes)}")
        for route in router.routes:
            print(f"  {route.methods} {route.path}")

        print("SUCCESS: Router ready")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_minimal2())