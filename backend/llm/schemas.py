"""
LLM Request and Response Schemas

This module defines the provider-agnostic contracts for LLM interactions.
These schemas ensure consistent communication across all LLM providers.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Standard message roles for LLM conversations."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """Represents a single message in an LLM conversation."""
    role: MessageRole
    content: str
    name: Optional[str] = None  # For function calling support

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        result = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        return result


class Usage(BaseModel):
    """Token usage information from LLM generation."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @property
    def cost_estimate(self) -> Optional[float]:
        """Placeholder for cost estimation - implement based on model pricing."""
        return None


class LLMRequest(BaseModel):
    """Standard request format for LLM generation.

    This class defines the universal interface that all providers must support.
    """
    model_id: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    stream: bool = Field(default=False, description="For future streaming support")
    json_schema: Optional[Dict[str, Any]] = Field(default=None, description="For structured outputs")
    tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="For function calling")

    def model_post_init(self, __context):
        """Validate request parameters."""
        if not self.model_id:
            raise ValueError("model_id is required")

        if not self.messages:
            raise ValueError("messages cannot be empty")

        if self.temperature is not None and not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")

        if self.top_p is not None and not (0.0 <= self.top_p <= 1.0):
            raise ValueError("top_p must be between 0.0 and 1.0")

        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary format for provider compatibility."""
        return {
            "model_id": self.model_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "stop": self.stop,
            "stream": self.stream,
            "json_schema": self.json_schema,
            "tools": self.tools,
        }


class LLMResponse(BaseModel):
    """Standard response format from LLM generation.

    This class normalizes responses from all providers into a consistent format.
    """
    text: str
    raw_response: Dict[str, Any]
    model_id: str
    usage: Optional[Usage] = None
    latency_ms: Optional[int] = None
    finish_reason: Optional[str] = None

    def model_post_init(self, __context):
        """Validate response parameters."""
        if not self.model_id:
            raise ValueError("model_id is required")

    @classmethod
    def from_provider_response(
        cls,
        text: str,
        raw_response: Dict[str, Any],
        model_id: str,
        usage: Optional[Usage] = None,
        latency_ms: Optional[int] = None,
        finish_reason: Optional[str] = None,
    ) -> "LLMResponse":
        """Factory method to create response from provider-specific data."""
        return cls(
            text=text,
            raw_response=raw_response,
            model_id=model_id,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )
