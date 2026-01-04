"""
Universal LLM Model Connector Package

This package provides a unified interface for interacting with various LLM providers
including OpenAI, vLLM, Ollama, and custom HTTP endpoints.

Main entry point: ModelConnector.generate(request)
"""

from .connector import ModelConnector
from .schemas import LLMRequest, LLMResponse, Message, MessageRole
from .exceptions import (
    ModelNotFoundError,
    ProviderNotSupportedError,
    InvalidRequestError,
    ModelGenerationError,
)

__all__ = [
    "ModelConnector",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "MessageRole",
    "ModelNotFoundError",
    "ProviderNotSupportedError",
    "InvalidRequestError",
    "ModelGenerationError",
]
