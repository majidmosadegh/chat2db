#!/usr/bin/env python3

import asyncio
from fastapi.testclient import TestClient
from api.chat_orchestrator import router
from fastapi import FastAPI
from api.db_models import get_db_session

# Create test app
app = FastAPI()
app.include_router(router, prefix="/api/chat-orchestrator", tags=["chat-orchestrator"])

client = TestClient(app)

# Test the endpoint
response = client.post(
    "/api/chat-orchestrator/chat",
    json={
        "message": "Hello",
        "session_id": "test_dep",
        "snapshot_id": 1
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code >= 400:
    print("Error occurred")
else:
    print("SUCCESS: Chat endpoint works!")