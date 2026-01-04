"""
Helper utilities for creating DirectDatabaseConnector from snapshot
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.db_models import SchemaSnapshot, DatabaseConnection
from api.database import decrypt_password
from services.db_connector import DirectDatabaseConnector


async def create_db_connector_for_snapshot(
    snapshot_id: int,
    session: AsyncSession
) -> Optional[DirectDatabaseConnector]:
    """
    Create DirectDatabaseConnector for a snapshot
    
    Args:
        snapshot_id: Schema snapshot ID
        session: Database session
        
    Returns:
        DirectDatabaseConnector instance or None if not found
    """
    try:
        # Get snapshot
        result = await session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            return None
        
        # Get connection details
        conn_result = await session.execute(
            select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
        )
        connection = conn_result.scalar_one_or_none()
        if not connection:
            return None
        
        # Decrypt password
        password = decrypt_password(connection.password_encrypted) if connection.password_encrypted else ""
        
        # Create connector
        connector = DirectDatabaseConnector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            username=connection.username,
            password=password,
            database=connection.database_name
        )
        
        return connector
    
    except Exception as e:
        from loguru import logger
        logger.error(f"Failed to create DB connector for snapshot {snapshot_id}: {e}")
        return None





