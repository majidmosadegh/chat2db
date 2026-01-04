"""
Helper functions for LLM operations
Provides unified interface for LLM service usage across the application
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm_service import get_llm_service, LLMServiceError
from llm.schemas import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


async def generate_with_llm_service(
    session: AsyncSession,
    request: LLMRequest
) -> LLMResponse:
    """
    Generate text using LLMService (unified interface).
    
    This function ensures all LLM calls go through LLMService for consistency.
    
    Args:
        session: Database session (needed for LLMService initialization)
        request: LLMRequest with model_id, messages, etc.
    
    Returns:
        LLMResponse: Response from the LLM
    
    Raises:
        LLMServiceError: If generation fails
    """
    llm_service = get_llm_service()
    
    # Ensure service is initialized
    if not llm_service._initialized:
        await llm_service.initialize(session)
    
    return await llm_service.generate(request)

