#!/usr/bin/env python3

# Test Pydantic imports
try:
    from fastapi import APIRouter
    from typing import Dict, Any, List, Optional
    from pydantic import BaseModel
    print("SUCCESS: Basic imports")

    # Test model creation
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

    print("SUCCESS: Pydantic models created")

    # Test instance creation
    msg = ChatMessage(message="test")
    resp = ChatResponse(session_id="test", response="test", intent_type="test")
    print("SUCCESS: Model instances created")

    # Test router creation
    router = APIRouter()
    print("SUCCESS: Router created")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()