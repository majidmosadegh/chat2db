"""
Database Connection Domain Entity.
Contains business rules for database connections.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
from .base_entity import BaseEntity


DatabaseType = Literal['postgresql', 'mysql', 'sqlserver', 'oracle', 'sqlite']


@dataclass(frozen=True)
class DatabaseConnection(BaseEntity):
    """Domain entity representing a database connection."""

    name: str
    db_type: DatabaseType
    host: str
    port: int
    database_name: str
    username: str
    # Note: Password is not stored in domain entity for security
    is_active: bool = True
    connection_timeout: int = 30
    query_timeout: int = 300

    def _validate(self) -> None:
        """Validate database connection business rules."""
        if not self.name or len(self.name.strip()) == 0:
            raise ValueError("Database connection name cannot be empty")

        if not self.host or len(self.host.strip()) == 0:
            raise ValueError("Database host cannot be empty")

        if self.port <= 0 or self.port > 65535:
            raise ValueError("Database port must be between 1 and 65535")

        if not self.database_name or len(self.database_name.strip()) == 0:
            raise ValueError("Database name cannot be empty")

        if not self.username or len(self.username.strip()) == 0:
            raise ValueError("Database username cannot be empty")

        if self.connection_timeout <= 0:
            raise ValueError("Connection timeout must be positive")

        if self.query_timeout <= 0:
            raise ValueError("Query timeout must be positive")

        # Validate database type specific rules
        self._validate_db_type_rules()

    def _validate_db_type_rules(self) -> None:
        """Validate database type specific business rules."""
        if self.db_type == 'postgresql' and self.port != 5432:
            # Allow custom ports but warn about non-standard
            pass
        elif self.db_type == 'mysql' and self.port != 3306:
            pass
        elif self.db_type == 'sqlserver' and self.port not in [1433, 1434]:
            pass

    def get_connection_string_template(self) -> str:
        """Get connection string template for this database type."""
        templates = {
            'postgresql': 'postgresql://{username}:{password}@{host}:{port}/{database}',
            'mysql': 'mysql://{username}:{password}@{host}:{port}/{database}',
            'sqlserver': 'mssql+pyodbc://{username}:{password}@{host}:{port}/{database}',
            'oracle': 'oracle://{username}:{password}@{host}:{port}/{database}',
            'sqlite': 'sqlite:///{database}'
        }
        return templates.get(self.db_type, '')

    def supports_schemas(self) -> bool:
        """Check if this database type supports schemas."""
        return self.db_type in ['postgresql', 'sqlserver', 'oracle']

    def supports_multiple_databases(self) -> bool:
        """Check if this database type supports multiple databases per server."""
        return self.db_type != 'sqlite'

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        data = super().to_dict()
        data.update({
            'name': self.name,
            'db_type': self.db_type,
            'host': self.host,
            'port': self.port,
            'database_name': self.database_name,
            'username': self.username,
            'is_active': self.is_active,
            'connection_timeout': self.connection_timeout,
            'query_timeout': self.query_timeout
        })
        return data









