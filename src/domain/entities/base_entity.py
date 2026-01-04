"""
Base Entity class with common domain entity functionality.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass(frozen=True)
class BaseEntity(ABC):
    """Base class for all domain entities."""

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate entity after initialization."""
        self._validate()

    @abstractmethod
    def _validate(self) -> None:
        """Validate entity business rules."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary for persistence."""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEntity':
        """Create entity from dictionary (for loading from persistence)."""
        return cls(**data)









