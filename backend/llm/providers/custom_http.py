"""
Custom HTTP Provider Implementation

This module provides support for custom HTTP-based LLM APIs.
It allows flexible configuration for any REST API that serves LLMs.
"""

import logging
from typing import Dict, Any, Optional

import httpx

from .base import BaseProvider
from ..schemas import LLMRequest
from ..exceptions import ProviderConfigurationError, ModelGenerationError
from ..registry import ModelDefinition

logger = logging.getLogger(__name__)


class CustomHTTPProvider(BaseProvider):
    """Custom HTTP provider for flexible LLM API integration."""

    def __init__(self, model_def: ModelDefinition):
        """Initialize custom HTTP provider."""
        super().__init__(model_def)
        self.request_template: Optional[Dict[str, Any]] = None
        self.response_mapping: Optional[Dict[str, Any]] = None

        # Parse custom configuration from model definition
        # This could be extended to support custom headers, auth, etc.
        self.custom_headers = getattr(self.model_def, 'custom_headers', {})

    def _validate_configuration(self) -> None:
        """Validate custom HTTP provider configuration."""
        if not self.model_def.base_url.startswith(('http://', 'https://')):
            raise ProviderConfigurationError(
                "custom",
                f"Invalid base URL: {self.model_def.base_url}"
            )

    def _build_request_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """Build request payload for custom HTTP API.

        This is a flexible implementation that can be customized based on
        the specific API requirements.
        """
        # Default to OpenAI-compatible format
        payload = {
            "model": self.model_def.model_name,
            "messages": [msg.to_dict() for msg in request.messages],
        }

        # Add standard parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop"] = request.stop

        # Add advanced features if supported
        if request.json_schema and self.model_def.supports_json:
            payload["response_format"] = {"type": "json_object"}

        if request.tools:
            payload["tools"] = request.tools

        return payload

    async def _generate_impl(
        self,
        request: LLMRequest,
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """Generate text using custom HTTP API."""
        payload = self._build_request_payload(request)

        headers = {
            "Content-Type": "application/json",
            **self.custom_headers,
        }

        # Add API key if provided
        if self.model_def.api_key:
            headers["Authorization"] = f"Bearer {self.model_def.api_key}"

        endpoint = f"{self.model_def.base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                logger.debug(f"Making request to custom HTTP API at {endpoint} for model {request.model_id}")

                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                )

                if response.status_code != 200:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("error", {}).get("message", response.text)
                    except:
                        pass

                    raise ModelGenerationError(
                        f"Custom HTTP API error: {error_detail}",
                        provider="custom",
                        model_id=request.model_id,
                        status_code=response.status_code,
                    )

                result = response.json()
                logger.debug(f"Custom HTTP response received for model {request.model_id}")
                return result

            except httpx.TimeoutException:
                raise ModelGenerationError(
                    f"Custom HTTP request timed out after {timeout_seconds}s",
                    provider="custom",
                    model_id=request.model_id,
                )
            except httpx.RequestError as e:
                raise ModelGenerationError(
                    f"Custom HTTP request failed: {str(e)}",
                    provider="custom",
                    model_id=request.model_id,
                )

    def _extract_text(self, raw_response: Dict[str, Any]) -> str:
        """Extract text from custom HTTP response.

        Assumes OpenAI-compatible response format by default.
        Override for custom formats.
        """
        # Default to OpenAI-compatible extraction
        if "choices" in raw_response and raw_response["choices"]:
            choice = raw_response["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
            elif "text" in choice:
                return choice["text"]

        # Fallback: look for common response fields
        for field in ["response", "text", "content", "result"]:
            if field in raw_response:
                return str(raw_response[field])

        return ""

    def _extract_usage(self, raw_response: Dict[str, Any]) -> Optional[Any]:
        """Extract usage information from custom HTTP response."""
        from ..schemas import Usage

        usage_data = raw_response.get("usage", {})
        if usage_data:
            return Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

        # Try alternative usage fields
        prompt_tokens = raw_response.get("prompt_tokens") or raw_response.get("input_tokens")
        completion_tokens = raw_response.get("completion_tokens") or raw_response.get("output_tokens")

        if prompt_tokens is not None or completion_tokens is not None:
            return Usage(
                prompt_tokens=prompt_tokens or 0,
                completion_tokens=completion_tokens or 0,
                total_tokens=(prompt_tokens or 0) + (completion_tokens or 0),
            )

        return None

    def _extract_finish_reason(self, raw_response: Dict[str, Any]) -> str:
        """Extract finish reason from custom HTTP response."""
        if "choices" in raw_response and raw_response["choices"]:
            choice = raw_response["choices"][0]
            return choice.get("finish_reason")

        # Try alternative fields
        return raw_response.get("finish_reason") or raw_response.get("stop_reason")
