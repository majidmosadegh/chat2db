"""
Ollama Provider Implementation

This module provides support for Ollama local LLM server.
Ollama uses a different API format than OpenAI-compatible services.
"""

import logging
from typing import Dict, Any, List, Optional

import httpx

from .base import BaseProvider
from ..schemas import LLMRequest, Message, MessageRole
from ..exceptions import ProviderConfigurationError, ModelGenerationError
from ..registry import ModelDefinition

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama provider implementation."""

    def _validate_configuration(self) -> None:
        """Validate Ollama provider configuration."""
        if not self.model_def.base_url.startswith(('http://', 'https://')):
            raise ProviderConfigurationError(
                "ollama",
                f"Invalid base URL: {self.model_def.base_url}"
            )

        # Ollama typically doesn't require API keys for local instances

    def _convert_messages_to_ollama_format(self, messages: List[Message]) -> Dict[str, Any]:
        """Convert standard messages to Ollama format."""
        # Ollama expects a different format than OpenAI
        # It uses 'prompt' for single messages or conversation history

        if len(messages) == 1:
            # Single message
            message = messages[0]
            return {"prompt": message.content}
        else:
            # Multiple messages - build conversation
            conversation_parts = []
            system_message = None

            for message in messages:
                if message.role == MessageRole.SYSTEM:
                    system_message = message.content
                elif message.role == MessageRole.USER:
                    if system_message:
                        conversation_parts.append(f"System: {system_message}")
                        system_message = None
                    conversation_parts.append(f"User: {message.content}")
                elif message.role == MessageRole.ASSISTANT:
                    conversation_parts.append(f"Assistant: {message.content}")

            # Add final system message if not used
            if system_message:
                conversation_parts.insert(0, f"System: {system_message}")

            prompt = "\n\n".join(conversation_parts)
            return {"prompt": prompt}

    async def _generate_impl(
        self,
        request: LLMRequest,
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """Generate text using Ollama server."""
        # Convert messages to Ollama format
        ollama_payload = self._convert_messages_to_ollama_format(request.messages)
        ollama_payload["model"] = self.model_def.model_name

        # Add optional parameters
        if request.temperature is not None:
            ollama_payload["temperature"] = request.temperature

        # Ollama uses 'num_predict' instead of 'max_tokens'
        if request.max_tokens is not None:
            ollama_payload["num_predict"] = min(request.max_tokens, self.model_def.max_tokens)
        else:
            ollama_payload["num_predict"] = self.model_def.max_tokens

        if request.top_p is not None:
            ollama_payload["top_p"] = request.top_p

        if request.stop:
            ollama_payload["stop"] = request.stop

        # Ollama-specific parameters
        ollama_payload.update({
            "stream": False,  # We handle streaming at higher level
            "raw": False,     # Return formatted response
        })

        headers = {
            "Content-Type": "application/json",
        }

        endpoint = f"{self.model_def.base_url.rstrip('/')}/api/generate"

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                logger.debug(f"Making request to Ollama server at {endpoint} for model {request.model_id}")

                response = await client.post(
                    endpoint,
                    json=ollama_payload,
                    headers=headers,
                )

                if response.status_code != 200:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("error", error_detail)
                    except:
                        pass

                    raise ModelGenerationError(
                        f"Ollama API error: {error_detail}",
                        provider="ollama",
                        model_id=request.model_id,
                        status_code=response.status_code,
                    )

                result = response.json()
                logger.debug(f"Ollama response received for model {request.model_id}")
                return result

            except httpx.TimeoutException:
                raise ModelGenerationError(
                    f"Ollama request timed out after {timeout_seconds}s",
                    provider="ollama",
                    model_id=request.model_id,
                )
            except httpx.RequestError as e:
                raise ModelGenerationError(
                    f"Ollama request failed: {str(e)}",
                    provider="ollama",
                    model_id=request.model_id,
                )

    def _extract_text(self, raw_response: Dict[str, Any]) -> str:
        """Extract text from Ollama response."""
        return raw_response.get("response", "")

    def _extract_usage(self, raw_response: Dict[str, Any]) -> Optional[Any]:
        """Extract usage information from Ollama response."""
        # Ollama provides basic usage info
        eval_count = raw_response.get("eval_count", 0)
        prompt_eval_count = raw_response.get("prompt_eval_count", 0)

        if eval_count > 0 or prompt_eval_count > 0:
            from ..schemas import Usage
            return Usage(
                prompt_tokens=prompt_eval_count,
                completion_tokens=eval_count,
                total_tokens=prompt_eval_count + eval_count,
            )
        return None

    def _extract_finish_reason(self, raw_response: Dict[str, Any]) -> str:
        """Extract finish reason from Ollama response."""
        done = raw_response.get("done", False)
        if done:
            done_reason = raw_response.get("done_reason")
            return done_reason or "stop"
        return None
