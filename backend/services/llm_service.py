"""
Unified LLM Service
Consolidates all LLM operations into a single service with proper caching and reuse
"""
import time
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.db_models import LLMModel
from api.database import decrypt_api_key
from llm import ModelConnector, LLMRequest, Message, MessageRole
from llm.registry import initialize_registry, ConfigRegistryLoader
from llm.exceptions import ModelNotFoundError, ModelGenerationError
from llm.schemas import LLMResponse

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Exception raised when LLM service operations fail"""
    pass


class LLMService:
    """
    Unified LLM service that handles all LLM operations.
    Maintains a single connector instance with proper caching.
    """

    def __init__(self):
        self._connector: Optional[ModelConnector] = None
        self._registry = None
        self._initialized = False

    async def initialize(self, session: AsyncSession) -> None:
        """
        Initialize the LLM service with active models from database.
        This should be called once and reused.
        """
        if self._initialized:
            return

        try:
            # Load all active models from database
            result = await session.execute(
                select(LLMModel).where(LLMModel.is_active == True)
            )
            models = result.scalars().all()

            logger.info(f"LLMService: Loaded {len(models)} active models from database")

            if not models:
                raise LLMServiceError("No active LLM models found in database")

            # Create registry configuration
            config = {"models": []}
            for model in models:
                # Map service_name to provider type
                provider_map = {
                    "OpenAI": "openai",
                    "Ollama": "ollama",
                    "vLLM": "vllm",
                }
                provider = provider_map.get(model.service_name, "custom")

                config["models"].append({
                    "id": str(model.id),
                    "provider": provider,
                    "base_url": model.base_url,
                    "model_name": model.model_name,
                    "api_key": decrypt_api_key(model.api_key) if model.api_key else None,
                    "supports_chat": True,
                    "supports_json": provider == "openai",
                    "max_tokens": model.max_tokens,
                    "is_active": True,
                    "timeout_seconds": 1200.0,  # 20 minutes for complex requests
                })

            # Initialize registry and connector
            loader = ConfigRegistryLoader(config)
            self._registry = initialize_registry(loader)
            await self._registry.load()

            self._connector = ModelConnector(self._registry)
            await self._connector.initialize()

            self._initialized = True
            logger.info("LLMService: Successfully initialized")

        except Exception as e:
            # Safe encoding for Windows
            error_msg = str(e)
            try:
                from core.config import LOG_ENCODING, LOG_ERROR_HANDLING
                error_msg = error_msg.encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            except:
                pass
            logger.error(f"[ERROR] LLMService initialization failed: {error_msg}")
            raise LLMServiceError(f"Failed to initialize LLM service: {e}")

    async def generate_text(
        self,
        session: AsyncSession,
        model_id: int,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate text using the specified LLM model.

        Args:
            session: Database session
            model_id: ID of the LLM model to use
            prompt: The prompt to send to the LLM
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse: Response from the LLM

        Raises:
            LLMServiceError: If generation fails
        """
        if not self._initialized:
            await self.initialize(session)

        start_time = time.time()
        request_id = f"LLM_{model_id}_{int(start_time * 1000)}"

        logger.info(f"LLM_GENERATE_START | ID: {request_id} | Model: {model_id} | PromptLength: {len(prompt)} chars")

        try:
            # Create LLM request
            request = LLMRequest(
                model_id=str(model_id),
                messages=[Message(role=MessageRole.USER, content=prompt)],
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Generate text
            response = await self._connector.generate(request)

            total_time = time.time() - start_time
            logger.info(f"LLM_GENERATE_SUCCESS | ID: {request_id} | ResponseLength: {len(response.text)} chars | TotalTime: {total_time:.2f}s")

            return response

        except (ModelNotFoundError, ModelGenerationError) as e:
            total_time = time.time() - start_time
            # Safe encoding for Windows
            error_msg = str(e)
            try:
                from core.config import LOG_ENCODING, LOG_ERROR_HANDLING
                error_msg = error_msg.encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            except:
                pass
            logger.error(f"[ERROR] LLM_GENERATE_FAILED | ID: {request_id} | Error: {error_msg} | TotalTime: {total_time:.2f}s")
            raise LLMServiceError(f"LLM generation failed: {str(e)}")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using LLMRequest (for advanced usage with messages).

        Args:
            request: LLMRequest with model_id, messages, temperature, etc.

        Returns:
            LLMResponse: Response from the LLM

        Raises:
            LLMServiceError: If generation fails
        """
        if not self._initialized:
            # Need session to initialize, but we don't have it here
            # This is a limitation - caller should ensure service is initialized
            raise LLMServiceError("LLMService not initialized. Call initialize() first with a session.")
        
        start_time = time.time()
        request_id = f"LLM_{request.model_id}_{int(start_time * 1000)}"
        
        logger.info(f"LLM_GENERATE_START | ID: {request_id} | Model: {request.model_id} | Messages: {len(request.messages)}")
        
        try:
            response = await self._connector.generate(request)
            
            total_time = time.time() - start_time
            logger.info(f"LLM_GENERATE_SUCCESS | ID: {request_id} | ResponseLength: {len(response.text)} chars | TotalTime: {total_time:.2f}s")
            
            return response
            
        except (ModelNotFoundError, ModelGenerationError) as e:
            total_time = time.time() - start_time
            error_msg = str(e)
            try:
                from core.config import LOG_ENCODING, LOG_ERROR_HANDLING
                error_msg = error_msg.encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            except:
                pass
            logger.error(f"[ERROR] LLM_GENERATE_FAILED | ID: {request_id} | Error: {error_msg} | TotalTime: {total_time:.2f}s")
            raise LLMServiceError(f"LLM generation failed: {str(e)}")

    async def get_active_models(self, session: AsyncSession) -> List[Dict[str, Any]]:
        """
        Get list of active models with their configurations.

        Args:
            session: Database session

        Returns:
            List of active model configurations
        """
        result = await session.execute(
            select(LLMModel).where(LLMModel.is_active == True)
        )
        models = result.scalars().all()

        return [{
            "id": model.id,
            "name": model.name,
            "service_name": model.service_name,
            "model_name": model.model_name,
            "base_url": model.base_url,
            "max_tokens": model.max_tokens,
            "is_active": model.is_active
        } for model in models]


    def get_connector(self) -> Optional[ModelConnector]:
        """
        Get the internal ModelConnector instance.
        Use this only when you need direct access to connector (e.g., for get_available_models).
        Prefer using generate() or generate_text() methods instead.
        """
        return self._connector if self._initialized else None


# Global instance for reuse
_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create global LLMService instance"""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
