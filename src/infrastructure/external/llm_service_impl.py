"""
LLM Service Implementation.
Concrete implementation of ILLMService using the existing LLM infrastructure.
"""

import time
import logging
from typing import List

from ...application.interfaces.service_interfaces import ILLMService
from ...domain.entities.llm_model import LLMModel
from ...domain.value_objects.llm_prompt import LLMPrompt, LLMResponse

# Import existing LLM infrastructure
from ....llm import ModelConnector, LLMRequest, Message, MessageRole
from ....llm.registry import initialize_registry, ConfigRegistryLoader
from ....llm.exceptions import ModelNotFoundError, ModelGenerationError
from ....api.database import decrypt_api_key

logger = logging.getLogger(__name__)


class LLMServiceImpl(ILLMService):
    """Concrete implementation of LLM service using existing infrastructure."""

    def __init__(self):
        self._connector: ModelConnector = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure the LLM service is initialized."""
        if self._initialized:
            return

        # Initialize with default registry - in real implementation,
        # this should be passed through dependency injection
        try:
            # This is a simplified implementation
            # In real code, we'd get active models from repository
            config = {"models": []}  # Empty for now

            loader = ConfigRegistryLoader(config)
            registry = initialize_registry(loader)
            await registry.load()

            self._connector = ModelConnector(registry)
            await self._connector.initialize()
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            raise

    async def generate_text(
        self,
        model: LLMModel,
        prompt: LLMPrompt
    ) -> LLMResponse:
        """Generate text using the specified LLM model."""
        await self._ensure_initialized()

        try:
            # Create registry config for this model
            config = {
                "models": [{
                    "id": model.id,
                    "provider": model.provider,
                    "base_url": model.base_url,
                    "model_name": model.model_name,
                    "api_key": decrypt_api_key(model.api_key) if model.api_key else None,
                    "supports_chat": model.supports_chat,
                    "supports_json": model.supports_json,
                    "max_tokens": model.max_tokens,
                    "is_active": True,
                    "timeout_seconds": 1200.0,
                }]
            }

            # Initialize registry for this specific model
            loader = ConfigRegistryLoader(config)
            registry = initialize_registry(loader)
            await registry.load()

            connector = ModelConnector(registry)
            await connector.initialize()

            # Prepare messages
            messages = []
            if prompt.system_message:
                messages.append(Message(role=MessageRole.SYSTEM, content=prompt.system_message))

            for user_msg in prompt.user_messages:
                messages.append(Message(role=MessageRole.USER, content=user_msg))

            # Create LLM request
            llm_request = LLMRequest(
                model_id=model.id,
                messages=messages,
                temperature=prompt.temperature,
                max_tokens=prompt.max_tokens
            )

            # Generate text
            start_time = time.time()
            response = await connector.generate(llm_request)
            latency_ms = int((time.time() - start_time) * 1000)

            return LLMResponse(
                text=response.text,
                model_id=model.id,
                latency_ms=latency_ms,
                usage=response.usage if hasattr(response, 'usage') else None
            )

        except (ModelNotFoundError, ModelGenerationError) as e:
            logger.error(f"LLM generation failed for model {model.id}: {e}")
            raise

    async def validate_model(self, model: LLMModel) -> bool:
        """Validate that a model configuration is working."""
        try:
            # Try a simple prompt to validate the model
            test_prompt = LLMPrompt.create_simple("Say 'OK' if you can read this.")
            await self.generate_text(model, test_prompt)
            return True
        except Exception:
            return False

    async def get_available_models(self) -> List[LLMModel]:
        """Get list of available models."""
        # In real implementation, this would query the repository
        # For now, return empty list
        return []

    async def estimate_tokens(self, text: str, model: LLMModel) -> int:
        """Estimate token count for text with given model."""
        # Simple estimation - 1 token per 4 characters
        # In real implementation, use proper tokenizer
        return len(text) // 4









