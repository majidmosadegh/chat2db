"""
Generate AI Dictionary Command.
Command for initiating AI dictionary generation process.
"""

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4


@dataclass
class GenerateAIDictionaryCommand:
    """Command to generate AI dictionary for a database snapshot."""

    snapshot_id: str
    business_domain: str
    database_description: str
    target_user: str
    language: str = "persian"
    notes: Optional[str] = None

    # Command metadata
    command_id: str = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        """Initialize command metadata."""
        if self.command_id is None:
            self.command_id = str(uuid4())

        # Validate required fields
        self._validate()

    def _validate(self) -> None:
        """Validate command data."""
        if not self.snapshot_id:
            raise ValueError("Snapshot ID is required")

        if not self.business_domain or len(self.business_domain.strip()) == 0:
            raise ValueError("Business domain is required")

        if not self.database_description or len(self.database_description.strip()) == 0:
            raise ValueError("Database description is required")

        if not self.target_user or len(self.target_user.strip()) == 0:
            raise ValueError("Target user is required")

        if self.language not in ["persian", "english"]:
            raise ValueError("Language must be either 'persian' or 'english'")

    @classmethod
    def create(cls, snapshot_id: str, business_domain: str,
               database_description: str, target_user: str,
               language: str = "persian", notes: Optional[str] = None) -> 'GenerateAIDictionaryCommand':
        """Factory method to create a new command."""
        return cls(
            snapshot_id=snapshot_id,
            business_domain=business_domain,
            database_description=database_description,
            target_user=target_user,
            language=language,
            notes=notes
        )









