#!/usr/bin/env python3

# Test minimal router creation
try:
    from fastapi import APIRouter
    from typing import Dict, Any, List, Optional
    from pydantic import BaseModel

    # Pydantic models for API
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

    router = APIRouter()

    @router.get("/test")
    def test_endpoint():
        """Simple test endpoint"""
        return {"message": "Chat orchestrator is working", "status": "ok"}

    @router.post("/chat")
    def chat_with_orchestrator_simple(request: ChatMessage):
        """Very simple version for testing"""
        try:
            return ChatResponse(
                session_id=request.session_id or "simple_test",
                response=f"I received your message: {request.message[:50]}...",
                intent_type="echo"
            )
        except Exception as e:
            return ChatResponse(
                session_id="error",
                response=f"Error: {str(e)}",
                intent_type="error"
            )

    print("SUCCESS: Minimal router created")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()