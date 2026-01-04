"""
LLM Prompt Value Object.
Immutable object representing a validated LLM prompt.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class LLMPrompt:
    """Value object representing a validated LLM prompt."""

    system_message: Optional[str]
    user_messages: List[str]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate prompt after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate prompt business rules."""
        if not self.user_messages or len(self.user_messages) == 0:
            raise ValueError("At least one user message is required")

        for message in self.user_messages:
            if not message or not message.strip():
                raise ValueError("User messages cannot be empty")

        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")

        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive if specified")

        # Validate message lengths
        total_length = len(self.system_message or "") + sum(len(msg) for msg in self.user_messages)
        if total_length > 100000:  # 100k characters
            raise ValueError("Total prompt length exceeds maximum allowed (100,000 characters)")

    @classmethod
    def create_simple(cls, user_message: str, temperature: float = 0.7) -> 'LLMPrompt':
        """Create a simple prompt with just user message."""
        return cls(
            system_message=None,
            user_messages=[user_message],
            temperature=temperature
        )

    @classmethod
    def create_with_system(cls, system_message: str, user_message: str,
                          temperature: float = 0.7) -> 'LLMPrompt':
        """Create a prompt with system and user messages."""
        return cls(
            system_message=system_message,
            user_messages=[user_message],
            temperature=temperature
        )

    @classmethod
    def create_conversation(cls, system_message: Optional[str],
                           messages: List[str], temperature: float = 0.7) -> 'LLMPrompt':
        """Create a conversation-style prompt."""
        return cls(
            system_message=system_message,
            user_messages=messages,
            temperature=temperature
        )

    def get_total_length(self) -> int:
        """Get total character count of the prompt."""
        return len(self.system_message or "") + sum(len(msg) for msg in self.user_messages)

    def is_too_long(self, max_length: int = 50000) -> bool:
        """Check if prompt is too long for the model."""
        return self.get_total_length() > max_length

    def truncate_messages(self, max_length: int) -> 'LLMPrompt':
        """Create a new prompt with truncated messages if too long."""
        if not self.is_too_long(max_length):
            return self

        # Simple truncation strategy - keep system message, truncate user messages
        available_length = max_length - len(self.system_message or "")
        if available_length <= 0:
            raise ValueError("System message is too long")

        truncated_messages = []
        remaining_length = available_length

        for message in self.user_messages:
            if len(message) <= remaining_length:
                truncated_messages.append(message)
                remaining_length -= len(message)
            else:
                truncated_messages.append(message[:remaining_length] + "...")
                remaining_length = 0
                break

        return LLMPrompt(
            system_message=self.system_message,
            user_messages=truncated_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            context=self.context
        )









