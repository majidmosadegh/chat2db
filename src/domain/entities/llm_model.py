"""
LLM Model Domain Entity.
Contains business rules for LLM model configurations.
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
from .base_entity import BaseEntity


ModelProvider = Literal['openai', 'ollama', 'vllm', 'anthropic', 'custom']


@dataclass(frozen=True)
class LLMModel(BaseEntity):
    """Domain entity representing an LLM model configuration."""

    name: str
    provider: ModelProvider
    model_name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # Encrypted at infrastructure layer
    is_active: bool = False
    max_tokens: int = 2048
    temperature_range: tuple[float, float] = field(default=(0.0, 2.0))
    supports_chat: bool = True
    supports_json: bool = False
    context_window: int = 4096
    pricing_per_token: Optional[float] = None

    def _validate(self) -> None:
        """Validate LLM model business rules."""
        if not self.name or len(self.name.strip()) == 0:
            raise ValueError("LLM model name cannot be empty")

        if not self.model_name or len(self.model_name.strip()) == 0:
            raise ValueError("Model name cannot be empty")

        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive")

        if self.context_window <= 0:
            raise ValueError("Context window must be positive")

        if not (0 <= self.temperature_range[0] <= self.temperature_range[1] <= 2):
            raise ValueError("Temperature range must be between 0 and 2")

        # Validate provider-specific rules
        self._validate_provider_rules()

    def _validate_provider_rules(self) -> None:
        """Validate provider-specific business rules."""
        if self.provider == 'openai':
            if not self.api_key:
                raise ValueError("OpenAI models require an API key")
            if not self.base_url:
                self._set_default_openai_url()
            self.supports_json = True

        elif self.provider == 'ollama':
            if not self.base_url:
                self._set_default_ollama_url()
            # Ollama doesn't require API key

        elif self.provider == 'anthropic':
            if not self.api_key:
                raise ValueError("Anthropic models require an API key")
            if not self.base_url:
                self._set_default_anthropic_url()

    def _set_default_openai_url(self) -> None:
        """Set default OpenAI API URL."""
        object.__setattr__(self, 'base_url', 'https://api.openai.com/v1')

    def _set_default_ollama_url(self) -> None:
        """Set default Ollama API URL."""
        object.__setattr__(self, 'base_url', 'http://localhost:11434')

    def _set_default_anthropic_url(self) -> None:
        """Set default Anthropic API URL."""
        object.__setattr__(self, 'base_url', 'https://api.anthropic.com')

    def is_temperature_valid(self, temperature: float) -> bool:
        """Check if temperature is valid for this model."""
        return self.temperature_range[0] <= temperature <= self.temperature_range[1]

    def can_handle_token_count(self, token_count: int) -> bool:
        """Check if model can handle the given token count."""
        return token_count <= self.context_window

    def get_effective_max_tokens(self, requested_max_tokens: int) -> int:
        """Get effective max tokens considering model limits."""
        return min(requested_max_tokens, self.max_tokens, self.context_window)

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        data = super().to_dict()
        data.update({
            'name': self.name,
            'provider': self.provider,
            'model_name': self.model_name,
            'base_url': self.base_url,
            'is_active': self.is_active,
            'max_tokens': self.max_tokens,
            'temperature_range': self.temperature_range,
            'supports_chat': self.supports_chat,
            'supports_json': self.supports_json,
            'context_window': self.context_window,
            'pricing_per_token': self.pricing_per_token
        })
        return data









