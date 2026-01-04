#!/usr/bin/env python3

import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_app_import():
    """Test importing the main FastAPI app"""
    try:
        print("Testing main app import...")

        from main import app
        print("✓ Main app imported successfully")

        # Get all routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)

        print(f"✓ Found {len(routes)} routes:")
        for route in routes[:15]:  # Show first 15
            print(f"  - {route}")

        # Check if chat routes are included
        chat_routes = [r for r in routes if 'chat' in r.lower()]
        print(f"✓ Found {len(chat_routes)} chat-related routes:")
        for route in chat_routes:
            print(f"  - {route}")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_app_import()










