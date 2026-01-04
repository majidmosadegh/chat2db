#!/usr/bin/env python3

# Test full router import
try:
    print("Testing full router import...")
    from api.chat_orchestrator import router
    print(f"SUCCESS: Router imported with {len(router.routes)} routes")

    # List all routes
    for i, route in enumerate(router.routes):
        print(f"  Route {i+1}: {route.methods} {route.path}")

except Exception as e:
    print(f"ERROR: Full router import failed: {e}")
    import traceback
    traceback.print_exc()