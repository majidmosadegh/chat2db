from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from .db_models import get_db_session
from services.llm_service import LLMService, LLMServiceError


router = APIRouter()


class LLMRequest(BaseModel):
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 2048


class LLMResponse(BaseModel):
    response: str
    model_used: str


@router.post("/generate", response_model=LLMResponse)
async def generate_text(
    request: LLMRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Generate text using the active LLM model"""
    try:
        # Get active model for response info
        from sqlalchemy import select
        from .db_models import LLMModel
        result = await session.execute(select(LLMModel).where(LLMModel.is_active == True))
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=400, detail="No active LLM model found")

        # Use unified LLM service directly
        llm_service = LLMService()
        await llm_service.initialize(session)
        response = await llm_service.generate_text(
            session=session,
            model_id=model.id,
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        return LLMResponse(response=response.text, model_used=model.name)

    except LLMServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
