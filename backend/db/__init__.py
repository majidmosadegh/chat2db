"""
Database module for SQL PT.
Provides clean, secure database connectivity with proper separation of concerns.
"""

from .connector import DatabaseConnector
from .dependencies import get_database_connector, get_database_connector_by_name
from .engine_factory import create_engine_from_connection
from .models import DatabaseConnection, Snapshot
from .repositories import get_snapshot, get_database_connection, get_active_snapshots
from .security import validate_sql, decrypt_password, SQLSecurityError

__all__ = [
    # Core classes
    "DatabaseConnector",

    # Dependencies
    "get_database_connector",
    "get_database_connector_by_name",

    # Factories
    "create_engine_from_connection",

    # Models
    "DatabaseConnection",
    "Snapshot",

    # Repositories
    "get_snapshot",
    "get_database_connection",
    "get_active_snapshots",

    # Security
    "validate_sql",
    "decrypt_password",
    "SQLSecurityError",
]
