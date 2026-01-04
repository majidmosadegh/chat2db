#!/usr/bin/env python3

# Test router import step by step
try:
    print("1. Importing FastAPI...")
    from fastapi import APIRouter, Depends, HTTPException, Body
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Dict, Any, List, Optional
    from pydantic import BaseModel
    from loguru import logger
    print("SUCCESS: Basic imports")

    print("2. Importing db_models...")
    from api.db_models import get_db_session
    print("SUCCESS: db_models imported")

    print("3. Creating router...")
    router = APIRouter()
    print("SUCCESS: Router created")

    print("4. Importing chat models...")
    class ChatMessage(BaseModel):
        message: str
        session_id: Optional[str] = None
        snapshot_id: Optional[int] = None
        context_override: Optional[Dict[str, Any]] = None

    class ChatResponse(BaseModel):
        session_id: str
        response: str
        intent_type: str
        execution_result: Optional[Dict[str, Any]] = None
        context_info: Optional[Dict[str, Any]] = None
        suggestions: Optional[List[str]] = None
    print("SUCCESS: Chat models created")

    print("5. Testing router.add_api_route...")
    def test_function():
        return {"test": "ok"}

    router.add_api_route("/test", test_function, methods=["GET"])
    print("SUCCESS: Route added")

    print("6. Adding chat route...")
    async def chat_with_orchestrator(request: ChatMessage):
        return ChatResponse(
            session_id=request.session_id or "test",
            response="Test response",
            intent_type="test"
        )

    router.add_api_route("/chat", chat_with_orchestrator, methods=["POST"])
    print("SUCCESS: Chat route added")

    print(f"Total routes: {len(router.routes)}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()