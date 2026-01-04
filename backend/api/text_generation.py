# DEPRECATED: This module is replaced by llm.py
# All LLM generation functionality should use the unified llm.py endpoint
# This file will be removed in the next cleanup phase

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/generate")
async def generate_text():
    """DEPRECATED: Use /api/llm/generate instead"""
    return JSONResponse(
        status_code=410,
        content={
            "error": "This endpoint is deprecated",
            "message": "Use /api/llm/generate instead",
            "migration_guide": "Update your API calls to use the unified LLM endpoint"
        }
    )
