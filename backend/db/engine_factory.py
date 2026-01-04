"""
Engine factory for creating SQLAlchemy async engines.
Completely stateless and focused on engine creation.
"""

from sqlalchemy.ext.asyncio import create_async_engine
from typing import Union

from .models import DatabaseConnection


def create_engine_from_connection(
    db_conn: DatabaseConnection,
    password: str
):
    """
    Create SQLAlchemy async engine from database connection.

    Args:
        db_conn: Database connection configuration
        password: Decrypted password

    Returns:
        AsyncEngine: Configured SQLAlchemy async engine

    Raises:
        ValueError: If database type is unsupported
    """
    if db_conn.db_type.lower() == "postgresql":
        return create_async_engine(
            f"postgresql+asyncpg://{db_conn.username}:{password}@{db_conn.host}:{db_conn.port}/{db_conn.database_name}",
            pool_size=10,  # Increased from 5 for better concurrency
            max_overflow=20,  # Increased from 10
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

    if db_conn.db_type.lower() == "mysql":
        return create_async_engine(
            f"mysql+aiomysql://{db_conn.username}:{password}@{db_conn.host}:{db_conn.port}/{db_conn.database_name}",
            pool_size=10,  # Added pool size
            max_overflow=20,  # Added max overflow
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

    if db_conn.db_type.lower() == "sqlserver":
        # For SQL Server, we'll try aioodbc first, fallback to pymssql if needed
        try:
            return create_async_engine(
                f"mssql+aioodbc://{db_conn.username}:{password}@{db_conn.host}:{db_conn.port}/{db_conn.database_name}"
                "?driver=ODBC+Driver+17+for+SQL+Server",
                pool_size=10,  # Added pool size
                max_overflow=20,  # Added max overflow
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections after 1 hour
            )
        except ImportError:
            # Fallback to pymssql if aioodbc is not available
            return create_async_engine(
                f"mssql+pymssql://{db_conn.username}:{password}@{db_conn.host}:{db_conn.port}/{db_conn.database_name}",
                pool_size=10,  # Added pool size
                max_overflow=20,  # Added max overflow
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections after 1 hour
            )

    raise ValueError(f"Unsupported database type: {db_conn.db_type}")
