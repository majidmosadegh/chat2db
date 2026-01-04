#!/usr/bin/env python3
"""
Test chat routes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from main import app

    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    chat_routes = [r for r in routes if 'chat' in r]
    print('SUCCESS: Chat routes found:', chat_routes)

except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()