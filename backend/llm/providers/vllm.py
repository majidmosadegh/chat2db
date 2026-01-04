"""
vLLM Provider Implementation

This module provides support for vLLM (Very Large Language Model) inference servers.
vLLM typically exposes OpenAI-compatible APIs, but this provider allows for
vLLM-specific optimizations and configurations.
"""

import logging
from typing import Dict, Any

import httpx

from .base import BaseProvider
from ..schemas import LLMRequest
from ..exceptions import ProviderConfigurationError, ModelGenerationError
from ..registry import ModelDefinition

logger = logging.getLogger(__name__)


class VLLMProvider(BaseProvider):
    """vLLM provider implementation."""

    def _validate_configuration(self) -> None:
        """Validate vLLM provider configuration."""
        if not self.model_def.base_url.startswith(('http://', 'https://')):
            raise ProviderConfigurationError(
                "vllm",
                f"Invalid base URL: {self.model_def.base_url}"
            )

        # vLLM may or may not require API key depending on configuration
        # We'll allow it to be optional

    async def _generate_impl(
        self,
        request: LLMRequest,
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """Generate text using vLLM server."""
        # vLLM uses OpenAI-compatible API format
        payload = {
            "model": self.model_def.model_name,
            "messages": [msg.to_dict() for msg in request.messages],
        }

        # Add optional parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = min(request.max_tokens, self.model_def.max_tokens)
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

        # vLLM-specific parameters for better performance
        payload.update({
            "stream": False,  # We handle streaming at higher level if needed
            "logprobs": None,  # Disable for now, can be enabled later
        })

        headers = {
            "Content-Type": "application/json",
        }

        # Add API key if provided
        if self.model_def.api_key:
            headers["Authorization"] = f"Bearer {self.model_def.api_key}"

        endpoint = f"{self.model_def.base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                logger.debug(f"Making request to vLLM server at {endpoint} for model {request.model_id}")

                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                )

                if response.status_code != 200:
                    # Try to get detailed error information
                    error_detail = response.text or ""
                    status_code_info = f"HTTP {response.status_code}"
                    
                    # Log raw response for debugging
                    logger.warning(
                        f"vLLM API returned non-200 status for model {request.model_id}: "
                        f"Status={response.status_code}, "
                        f"URL={endpoint}, "
                        f"Response length={len(error_detail)} chars, "
                        f"Headers={dict(response.headers)}"
                    )
                    
                    # Try to parse JSON error
                    error_msg = None
                    try:
                        error_json = response.json()
                        if isinstance(error_json, dict):
                            # Try multiple common error message fields
                            if isinstance(error_json.get("error"), dict):
                                error_msg = error_json["error"].get("message") or error_json["error"].get("type") or str(error_json["error"])
                            elif isinstance(error_json.get("error"), str):
                                error_msg = error_json["error"]
                            else:
                                error_msg = (
                                    error_json.get("message")
                                    or error_json.get("detail")
                                    or error_json.get("type")
                                    or str(error_json)
                                )
                    except Exception as parse_error:
                        # If JSON parsing fails, use text
                        logger.debug(f"Could not parse vLLM error response as JSON: {parse_error}")
                        if error_detail and error_detail.strip():
                            error_msg = error_detail[:500]  # Limit length
                    
                    # Construct final error message
                    if error_msg and error_msg.strip():
                        error_detail = f"{status_code_info}: {error_msg}"
                    elif error_detail and error_detail.strip():
                        error_detail = f"{status_code_info}: {error_detail[:500]}"
                    else:
                        # Check for common HTTP status codes
                        status_messages = {
                            400: "Bad Request",
                            401: "Unauthorized",
                            403: "Forbidden",
                            404: "Not Found",
                            429: "Too Many Requests (Rate Limited)",
                            500: "Internal Server Error",
                            502: "Bad Gateway",
                            503: "Service Unavailable",
                            504: "Gateway Timeout"
                        }
                        status_msg = status_messages.get(response.status_code, "Unknown Error")
                        error_detail = f"{status_code_info}: {status_msg} (empty response body)"
                    
                    # Log detailed error for debugging
                    logger.error(
                        f"vLLM API error for model {request.model_id}: {error_detail[:300]}"
                    )
                    
                    raise ModelGenerationError(
                        f"vLLM API error: {error_detail}",
                        provider="vllm",
                        model_id=request.model_id,
                        status_code=response.status_code,
                    )

                result = response.json()
                logger.debug(f"vLLM response received for model {request.model_id}")
                return result

            except httpx.TimeoutException:
                raise ModelGenerationError(
                    f"vLLM request timed out after {timeout_seconds}s",
                    provider="vllm",
                    model_id=request.model_id,
                )
            except httpx.RequestError as e:
                raise ModelGenerationError(
                    f"vLLM request failed: {str(e)}",
                    provider="vllm",
                    model_id=request.model_id,
                )
