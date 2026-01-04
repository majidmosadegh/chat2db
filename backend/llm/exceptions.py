"""
Custom Exception Classes for LLM Connector

This module defines explicit exception types for clear error handling
and debugging across the LLM connector system.
"""


class LLMConnectorError(Exception):
    """Base exception for all LLM connector errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ModelNotFoundError(LLMConnectorError):
    """Raised when a requested model ID is not found in the registry."""

    def __init__(self, model_id: str):
        super().__init__(
            f"Model '{model_id}' not found in registry",
            {"model_id": model_id}
        )
        self.model_id = model_id


class ProviderNotSupportedError(LLMConnectorError):
    """Raised when a model uses an unsupported provider type."""

    def __init__(self, provider: str, model_id: str):
        super().__init__(
            f"Provider '{provider}' is not supported for model '{model_id}'",
            {"provider": provider, "model_id": model_id}
        )
        self.provider = provider
        self.model_id = model_id


class InvalidRequestError(LLMConnectorError):
    """Raised when an LLM request contains invalid parameters."""

    def __init__(self, message: str, field: str = None, value: any = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value

        super().__init__(message, details)
        self.field = field
        self.value = value


class ModelGenerationError(LLMConnectorError):
    """Raised when LLM generation fails due to provider errors."""

    def __init__(self, message: str, provider: str, model_id: str, status_code: int = None):
        details = {
            "provider": provider,
            "model_id": model_id,
        }
        if status_code:
            details["status_code"] = status_code

        super().__init__(message, details)
        self.provider = provider
        self.model_id = model_id
        self.status_code = status_code


class ProviderConfigurationError(LLMConnectorError):
    """Raised when a provider is not properly configured."""

    def __init__(self, provider: str, message: str):
        super().__init__(
            f"Provider '{provider}' configuration error: {message}",
            {"provider": provider}
        )
        self.provider = provider


class TimeoutError(LLMConnectorError):
    """Raised when LLM generation times out."""

    def __init__(self, model_id: str, timeout_seconds: float):
        super().__init__(
            f"Generation timed out after {timeout_seconds}s for model '{model_id}'",
            {"model_id": model_id, "timeout_seconds": timeout_seconds}
        )
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds
