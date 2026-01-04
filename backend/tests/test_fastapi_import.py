#!/usr/bin/env python3

# Test FastAPI router import
try:
    from fastapi import FastAPI
    from api.chat_orchestrator import router

    app = FastAPI()
    app.include_router(router, prefix="/api/chat-orchestrator", tags=["chat-orchestrator"])

    print("SUCCESS: FastAPI app created with chat router")
    print(f"Routes: {len(app.routes)}")

except Exception as e:
    print(f"ERROR: FastAPI import failed: {e}")
    import traceback
    traceback.print_exc()