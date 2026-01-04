import time
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm_service import LLMService, LLMServiceError
from ..schemas import LLMResponse

# Configure logging for LLM gateway
logger = logging.getLogger(__name__)


class LLMGatewayError(Exception):
    """Exception raised when LLM gateway operations fail"""
    pass


class LLMGateway:
    """Abstracts model providers and handles LLM API calls"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def call_llm(
        self,
        model_id: int,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Call LLM with prompt and parameters.

        Args:
            model_id: ID of the LLM model to use
            prompt: The prompt to send to the LLM
            temperature: Temperature for generation (default: 0.1 for SQL)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse: Response from the LLM

        Raises:
            LLMGatewayError: If the call fails
        """
        start_time = time.time()
        request_id = f"LLM_{model_id}_{int(start_time * 1000)}"

        logger.info(f"🤖 LLM_CALL_START | ID: {request_id} | Model: {model_id} | PromptLength: {len(prompt)} chars | Temp: {temperature} | MaxTokens: {max_tokens}")
        logger.debug(f"📝 LLM_PROMPT_PREVIEW | ID: {request_id} | Prompt: '{prompt[:100]}{'...' if len(prompt) > 100 else ''}'")

        # Test mode disabled - always use real LLM

        try:
            # Use unified LLM service directly
            logger.debug(f"📝 Calling unified LLM service for model {model_id}")

            llm_service = LLMService()
            await llm_service.initialize(self.session)
            response = await llm_service.generate_text(
                session=self.session,
                model_id=model_id,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

            total_time = time.time() - start_time
            processing_time = int(total_time * 1000)

            logger.info(f"✅ LLM_RESPONSE_SUCCESS | ID: {request_id} | ResponseLength: {len(response.text)} chars | TotalTime: {total_time:.2f}s")
            logger.debug(f"📤 LLM_RESPONSE_PREVIEW | ID: {request_id} | Response: '{response.text[:200]}{'...' if len(response.text) > 200 else ''}'")
            logger.debug(f"📊 LLM_TOKEN_USAGE | ID: {request_id} | Usage: {response.usage} | Latency: {response.latency_ms}ms | ProcessingTime: {processing_time}ms")

            return LLMResponse(
                raw_text=response.text,
                model_used=f"model_{model_id}",
                processing_time_ms=processing_time,
                success=True
            )

        except LLMServiceError as e:
            total_time = time.time() - start_time
            processing_time = int(total_time * 1000)

            logger.error(f"❌ LLM_CALL_FAILED | ID: {request_id} | ErrorType: {type(e).__name__} | TotalTime: {total_time:.2f}s | Message: {str(e)}")

            raise LLMGatewayError(f"LLM call failed: {str(e)}")

        except Exception as e:
            total_time = time.time() - start_time
            processing_time = int(total_time * 1000)

            logger.error(f"💥 Unexpected error in LLM call {request_id} after {total_time:.2f}s")
            logger.error(f"❌ Error: {str(e)}", exc_info=True)

            return LLMResponse(
                raw_text="",
                model_used=f"model_{model_id}",
                processing_time_ms=processing_time,
                success=False,
                error_message=str(e)
            )

    async def close(self):
        """Close resources"""
        # LLM service handles its own lifecycle
        pass
