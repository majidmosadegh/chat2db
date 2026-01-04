"""
Base Provider Interface

This module defines the abstract base class that all LLM providers must implement.
It ensures consistent behavior across all provider implementations.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from ..schemas import LLMRequest, LLMResponse, Usage
from ..exceptions import ModelGenerationError, ProviderConfigurationError
from ..registry import ModelDefinition

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """Abstract base class for all LLM providers.

    All concrete providers must implement the generate method and follow
    the same request/response contract.
    """

    def __init__(self, model_def: ModelDefinition):
        """Initialize provider with model definition.

        Args:
            model_def: Model definition containing provider configuration

        Raises:
            ProviderConfigurationError: If provider cannot be configured
        """
        self.model_def = model_def
        self._validate_configuration()

        logger.info(f"Initialized {self.__class__.__name__} for model {model_def.id}")
        logger.debug(f"Base URL: {model_def.base_url}")
        logger.debug(f"Model: {model_def.model_name}")
        logger.debug(f"Config: max_tokens={model_def.max_tokens}, timeout={model_def.timeout_seconds}s")

    @abstractmethod
    def _validate_configuration(self) -> None:
        """Validate provider-specific configuration.

        Raises:
            ProviderConfigurationError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def _generate_impl(
        self,
        request: LLMRequest,
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """Provider-specific generation implementation.

        Args:
            request: Standardized LLM request
            timeout_seconds: Timeout for the request

        Returns:
            Raw response from the provider API

        Raises:
            ModelGenerationError: If generation fails
        """
        pass

    def _extract_text(self, raw_response: Dict[str, Any]) -> str:
        """Extract text content from provider response.

        Default implementation - override for provider-specific extraction.
        """
        # Default extraction logic - most providers follow OpenAI format
        if "choices" in raw_response and raw_response["choices"]:
            choice = raw_response["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
            elif "text" in choice:
                return choice["text"]
        return ""

    def _extract_usage(self, raw_response: Dict[str, Any]) -> Optional[Usage]:
        """Extract token usage from provider response.

        Default implementation - override for provider-specific extraction.
        """
        usage_data = raw_response.get("usage", {})
        if usage_data:
            return Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
        return None

    def _extract_finish_reason(self, raw_response: Dict[str, Any]) -> Optional[str]:
        """Extract finish reason from provider response."""
        if "choices" in raw_response and raw_response["choices"]:
            choice = raw_response["choices"][0]
            return choice.get("finish_reason")
        return None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using the LLM provider.

        This is the main entry point that all providers must implement.
        It handles timing, error handling, and response normalization.

        Args:
            request: Standardized LLM request

        Returns:
            Standardized LLM response

        Raises:
            ModelGenerationError: If generation fails
        """
        start_time = time.time()

        try:
            logger.debug(f"Generating with {self.__class__.__name__} for model {request.model_id}")

            # Call provider-specific implementation
            raw_response = await self._generate_impl(
                request,
                timeout_seconds=self.model_def.timeout_seconds
            )

            # Extract standardized response components
            text = self._extract_text(raw_response)
            usage = self._extract_usage(raw_response)
            finish_reason = self._extract_finish_reason(raw_response)

            latency_ms = int((time.time() - start_time) * 1000)

            response = LLMResponse.from_provider_response(
                text=text,
                raw_response=raw_response,
                model_id=request.model_id,
                usage=usage,
                latency_ms=latency_ms,
                finish_reason=finish_reason,
            )

            logger.debug(f"[OK] Generated response in {latency_ms}ms for model {request.model_id}")
            return response

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            # Safe encoding for Windows
            error_msg = str(e)
            try:
                from core.config import LOG_ENCODING, LOG_ERROR_HANDLING
                error_msg = error_msg.encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            except:
                pass
            
            logger.error(
                f"[ERROR] Generation failed for model {request.model_id} after {latency_ms}ms: {error_msg}"
            )
            logger.error(f"[DEBUG] Error type: {type(e).__name__}", exc_info=True)

            if isinstance(e, ModelGenerationError):
                raise

            # Wrap unexpected errors
            raise ModelGenerationError(
                f"Unexpected error during generation: {str(e)}",
                provider=self.model_def.provider,
                model_id=request.model_id,
            ) from e
