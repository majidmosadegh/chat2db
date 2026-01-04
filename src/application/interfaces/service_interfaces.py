"""
Service Interfaces - Contracts for external services.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ...domain.entities.llm_model import LLMModel
from ...domain.value_objects.llm_prompt import LLMPrompt
from ...domain.value_objects.llm_response import LLMResponse


class ILLMService(ABC):
    """Interface for LLM service operations."""

    @abstractmethod
    async def generate_text(
        self,
        model: LLMModel,
        prompt: LLMPrompt
    ) -> LLMResponse:
        """Generate text using the specified LLM model."""
        pass

    @abstractmethod
    async def validate_model(self, model: LLMModel) -> bool:
        """Validate that a model configuration is working."""
        pass

    @abstractmethod
    async def get_available_models(self) -> List[LLMModel]:
        """Get list of available models."""
        pass

    @abstractmethod
    async def estimate_tokens(self, text: str, model: LLMModel) -> int:
        """Estimate token count for text with given model."""
        pass


class IDatabaseService(ABC):
    """Interface for database operations."""

    @abstractmethod
    async def execute_query(
        self,
        connection_id: str,
        sql: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Execute SQL query against database connection."""
        pass

    @abstractmethod
    async def test_connection(self, connection_id: str) -> bool:
        """Test database connection."""
        pass

    @abstractmethod
    async def get_table_schema(self, connection_id: str, table_name: str) -> Dict[str, Any]:
        """Get schema information for a table."""
        pass

    @abstractmethod
    async def get_database_info(self, connection_id: str) -> Dict[str, Any]:
        """Get general database information."""
        pass


class IEncryptionService(ABC):
    """Interface for encryption/decryption operations."""

    @abstractmethod
    def encrypt(self, plain_text: str) -> str:
        """Encrypt plain text."""
        pass

    @abstractmethod
    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt encrypted text."""
        pass

    @abstractmethod
    def generate_key(self) -> str:
        """Generate a new encryption key."""
        pass









