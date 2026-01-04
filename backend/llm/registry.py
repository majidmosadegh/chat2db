"""
Model Registry

This module manages LLM model definitions and provides lookup functionality.
The registry can be backed by database, configuration files, or other sources.

Model definitions include provider type, endpoints, and capabilities.
"""

import logging
from typing import Dict, List, Optional, Any, Protocol
from pydantic import BaseModel
from abc import ABC, abstractmethod

from .exceptions import ModelNotFoundError

logger = logging.getLogger(__name__)


class ModelDefinition(BaseModel):
    """Definition of an LLM model and its capabilities."""
    id: str
    provider: str  # 'openai', 'vllm', 'ollama', 'custom'
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    supports_chat: bool = True
    supports_json: bool = False
    max_tokens: int = 4096
    is_active: bool = True
    timeout_seconds: float = 30.0
    retry_attempts: int = 3

    def model_post_init(self, __context):
        """Validate model definition."""
        if not self.id:
            raise ValueError("Model ID cannot be empty")
        if not self.provider:
            raise ValueError("Provider cannot be empty")
        if not self.base_url:
            raise ValueError("Base URL cannot be empty")
        if not self.model_name:
            raise ValueError("Model name cannot be empty")

        valid_providers = {'openai', 'vllm', 'ollama', 'custom'}
        if self.provider not in valid_providers:
            raise ValueError(f"Provider must be one of: {valid_providers}")

        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class ModelRegistryLoader(Protocol):
    """Protocol for loading model definitions from various sources."""

    async def load_models(self) -> List[ModelDefinition]:
        """Load all model definitions from the source."""
        ...


class ConfigRegistryLoader:
    """Simple configuration-based model registry loader."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def load_models(self) -> List[ModelDefinition]:
        """Load models from configuration dictionary."""
        models = []
        for model_config in self.config.get('models', []):
            try:
                model = ModelDefinition(**model_config)
                models.append(model)
                logger.info(f"Loaded model: {model.id} ({model.provider})")
            except Exception as e:
                logger.error(f"Failed to load model config: {model_config}. Error: {e}")
                continue
        return models


class ModelRegistry:
    """Registry for managing LLM model definitions."""

    def __init__(self, loader: ModelRegistryLoader):
        self.loader = loader
        self._models: Dict[str, ModelDefinition] = {}
        self._loaded = False

    async def load(self) -> None:
        """Load all model definitions from the loader."""
        if self._loaded:
            logger.warning("Registry already loaded, reloading...")
            self._models.clear()

        models = await self.loader.load_models()
        for model in models:
            if model.is_active:
                self._models[model.id] = model
                logger.info(f"Registered active model: {model.id}")
            else:
                logger.debug(f"Skipped inactive model: {model.id}")

        self._loaded = True
        logger.info(f"Loaded {len(self._models)} active models")

    def get_model(self, model_id: str) -> ModelDefinition:
        """Get model definition by ID."""
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call load() first.")

        if model_id not in self._models:
            raise ModelNotFoundError(model_id)

        return self._models[model_id]

    def get_all_models(self) -> List[ModelDefinition]:
        """Get all active model definitions."""
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call load() first.")
        return list(self._models.values())

    def get_models_by_provider(self, provider: str) -> List[ModelDefinition]:
        """Get all models for a specific provider."""
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call load() first.")
        return [model for model in self._models.values() if model.provider == provider]

    def is_loaded(self) -> bool:
        """Check if registry has been loaded."""
        return self._loaded

    def clear(self) -> None:
        """Clear all loaded models."""
        self._models.clear()
        self._loaded = False
        logger.info("Registry cleared")


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Get the global model registry instance."""
    global _registry
    if _registry is None:
        raise RuntimeError("Global registry not initialized. Call initialize_registry() first.")
    return _registry


def initialize_registry(loader: ModelRegistryLoader) -> ModelRegistry:
    """Initialize the global model registry."""
    global _registry
    _registry = ModelRegistry(loader)
    logger.info("Global model registry initialized")
    return _registry
