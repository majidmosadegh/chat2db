"""
Universal LLM Model Connector

This module provides the main entry point for LLM operations across all providers.
It acts as a facade that handles model resolution, provider dispatch, and response
normalization.
"""

import logging
import asyncio
import logging
from typing import Dict, Type, Optional

from .schemas import LLMRequest, LLMResponse
from .registry import ModelRegistry, get_registry
from .providers.base import BaseProvider
from .providers.openai import OpenAIProvider
from .providers.vllm import VLLMProvider
from .providers.ollama import OllamaProvider
from .providers.custom_http import CustomHTTPProvider
from .exceptions import (
    ModelNotFoundError,
    ProviderNotSupportedError,
    InvalidRequestError,
    ModelGenerationError,
)

# Configure logging for ModelConnector
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class ModelConnector:
    """Universal LLM Model Connector.

    This is the main entry point for all LLM operations. It provides a unified
    interface for generating text across different LLM providers.

    Usage:
        connector = ModelConnector()
        await connector.initialize()  # Load model registry

        request = LLMRequest(
            model_id="gpt-4",
            messages=[Message(role=MessageRole.USER, content="Hello!")]
        )
        response = await connector.generate(request)
    """

    def __init__(self, registry: Optional[ModelRegistry] = None):
        """Initialize the model connector.

        Args:
            registry: Optional model registry. If not provided, uses global registry.
        """
        self.registry = registry or get_registry()
        self._providers: Dict[str, BaseProvider] = {}
        self._provider_classes: Dict[str, Type[BaseProvider]] = {
            "openai": OpenAIProvider,
            "vllm": VLLMProvider,
            "ollama": OllamaProvider,
            "custom": CustomHTTPProvider,
        }
        self._initialized = False

        logger.info("ModelConnector initialized")

    async def initialize(self) -> None:
        """Initialize the connector by loading the model registry."""
        if not self.registry.is_loaded():
            await self.registry.load()

        self._initialized = True
        logger.info("ModelConnector initialized with registry")

    def _ensure_initialized(self) -> None:
        """Ensure the connector is initialized."""
        if not self._initialized:
            raise RuntimeError("ModelConnector not initialized. Call initialize() first.")

    def _get_provider(self, model_id: str) -> BaseProvider:
        """Get or create provider instance for the given model."""
        if model_id in self._providers:
            return self._providers[model_id]

        # Get model definition
        try:
            model_def = self.registry.get_model(model_id)
        except ModelNotFoundError:
            raise

        # Get provider class
        provider_type = model_def.provider
        if provider_type not in self._provider_classes:
            raise ProviderNotSupportedError(provider_type, model_id)

        provider_class = self._provider_classes[provider_type]

        # Create provider instance
        try:
            provider = provider_class(model_def)
            self._providers[model_id] = provider
            logger.debug(f"Created provider instance for model {model_id} ({provider_type})")
            return provider
        except Exception as e:
            logger.error(f"Failed to create provider for model {model_id}: {e}")
            raise ModelGenerationError(
                f"Provider initialization failed: {str(e)}",
                provider=provider_type,
                model_id=model_id,
            ) from e

    def _validate_request(self, request: LLMRequest) -> None:
        """Validate the incoming request."""
        if not request.model_id:
            raise InvalidRequestError("model_id is required")

        # Check if model exists in registry
        try:
            model_def = self.registry.get_model(request.model_id)
        except ModelNotFoundError:
            raise

        # Validate request against model capabilities
        if request.json_schema and not model_def.supports_json:
            raise InvalidRequestError(
                f"Model {request.model_id} does not support JSON schema responses"
            )

        # Validate message content
        for i, message in enumerate(request.messages):
            if not message.content.strip():
                raise InvalidRequestError(f"Message {i} has empty content")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using the specified LLM model.

        This is the main entry point for LLM generation. It handles:
        - Request validation
        - Model resolution
        - Provider dispatch
        - Response normalization
        - Error handling

        Args:
            request: Standardized LLM request

        Returns:
            Standardized LLM response

        Raises:
            ModelNotFoundError: If model_id is not found
            ProviderNotSupportedError: If provider type is not supported
            InvalidRequestError: If request parameters are invalid
            ModelGenerationError: If generation fails
        """
        self._ensure_initialized()

        # Validate request
        self._validate_request(request)

        # Get provider and generate
        provider = self._get_provider(request.model_id)

        provider_name = provider.__class__.__name__
        logger.info(f"[AI] Generating with model {request.model_id} using {provider_name}")
        logger.debug(f"[REQUEST] {len(request.messages)} messages, temp={request.temperature}, max_tokens={request.max_tokens}")
        logger.debug(f"[MSG] First message preview: {request.messages[0].content[:100]}..." if request.messages else "No messages")

        generation_start = asyncio.get_event_loop().time()

        try:
            response = await provider.generate(request)

            generation_time = asyncio.get_event_loop().time() - generation_start

            # Log successful generation with performance metrics
            logger.info(
                f"[OK] Generation completed for model {request.model_id} "
                f"in {response.latency_ms}ms (provider: {response.latency_ms}ms)"
            )
            logger.info(f"[RESPONSE] {len(response.text)} chars, usage={response.usage}")
            logger.debug(f"[PREVIEW] Response preview: {response.text[:200]}...")

            return response

        except (ModelGenerationError, InvalidRequestError):
            # Re-raise known errors
            raise
        except Exception as e:
            generation_time = asyncio.get_event_loop().time() - generation_start

            # Wrap unexpected errors
            logger.error(f"💥 Unexpected error during generation after {generation_time:.2f}s: {str(e)}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            logger.error(f"📋 Model: {request.model_id}, Provider: {provider_name}", exc_info=True)

            raise ModelGenerationError(
                f"Unexpected error: {str(e)}",
                provider=self.registry.get_model(request.model_id).provider,
                model_id=request.model_id,
            ) from e

    async def generate_batch(
        self,
        requests: list[LLMRequest]
    ) -> list[LLMResponse]:
        """Generate text for multiple requests concurrently.

        Args:
            requests: List of LLM requests

        Returns:
            List of LLM responses in the same order as requests
        """
        self._ensure_initialized()

        # Create tasks for concurrent execution
        tasks = [self.generate(request) for request in requests]

        # Execute concurrently and maintain order
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions and convert to responses
        result = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                # Convert exception to error response if needed
                # For now, re-raise the exception
                raise response
            result.append(response)

        return result

    def get_available_models(self) -> list[str]:
        """Get list of available model IDs.

        Returns:
            List of active model IDs
        """
        self._ensure_initialized()
        return [model.id for model in self.registry.get_all_models()]

    def get_model_info(self, model_id: str) -> dict:
        """Get information about a specific model.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary with model information

        Raises:
            ModelNotFoundError: If model is not found
        """
        self._ensure_initialized()
        model_def = self.registry.get_model(model_id)

        return {
            "id": model_def.id,
            "provider": model_def.provider,
            "model_name": model_def.model_name,
            "supports_chat": model_def.supports_chat,
            "supports_json": model_def.supports_json,
            "max_tokens": model_def.max_tokens,
            "is_active": model_def.is_active,
        }

    def clear_provider_cache(self) -> None:
        """Clear cached provider instances."""
        self._providers.clear()
        logger.info("Provider cache cleared")
