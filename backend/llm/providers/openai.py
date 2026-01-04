"""
OpenAI Provider Implementation

This module provides support for OpenAI-compatible APIs including
OpenAI's official API and other OpenAI-compatible endpoints.
"""

import logging
from typing import Dict, Any

import httpx

from .base import BaseProvider
from ..schemas import LLMRequest
from ..exceptions import ProviderConfigurationError, ModelGenerationError
from ..registry import ModelDefinition

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI-compatible provider implementation."""

    def _validate_configuration(self) -> None:
        """Validate OpenAI provider configuration."""
        if not self.model_def.api_key:
            raise ProviderConfigurationError(
                "openai",
                "API key is required for OpenAI provider"
            )

        if not self.model_def.base_url.startswith(('http://', 'https://')):
            raise ProviderConfigurationError(
                "openai",
                f"Invalid base URL: {self.model_def.base_url}"
            )

    async def _generate_impl(
        self,
        request: LLMRequest,
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """Generate text using OpenAI-compatible API."""
        # Prepare request payload
        payload = {
            "model": self.model_def.model_name,
            "messages": [msg.to_dict() for msg in request.messages],
        }

        # Add optional parameters
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
            # Add schema instruction to system message if present
            if request.messages and request.messages[0].role.name == "system":
                request.messages[0].content += f"\n\nRespond with valid JSON matching this schema: {request.json_schema}"

        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.model_def.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.model_def.base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                logger.debug(f"Making request to {endpoint} for model {request.model_id}")

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
                        f"OpenAI API error: {error_detail}",
                        provider="openai",
                        model_id=request.model_id,
                        status_code=response.status_code,
                    )

                return response.json()

            except httpx.TimeoutException:
                raise ModelGenerationError(
                    f"Request timed out after {timeout_seconds}s",
                    provider="openai",
                    model_id=request.model_id,
                )
            except httpx.RequestError as e:
                raise ModelGenerationError(
                    f"Request failed: {str(e)}",
                    provider="openai",
                    model_id=request.model_id,
                )

    def _extract_text(self, raw_response: Dict[str, Any]) -> str:
        """Extract text from OpenAI response."""
        if "choices" in raw_response and raw_response["choices"]:
            choice = raw_response["choices"][0]
            message = choice.get("message", {})
            return message.get("content", "")
        return ""

    def _extract_finish_reason(self, raw_response: Dict[str, Any]) -> str:
        """Extract finish reason from OpenAI response."""
        if "choices" in raw_response and raw_response["choices"]:
            choice = raw_response["choices"][0]
            return choice.get("finish_reason")
        return None
