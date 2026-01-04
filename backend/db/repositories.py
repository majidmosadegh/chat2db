"""
Repository layer for database operations.
Handles data access for snapshots and connections.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from api.db_models import SchemaSnapshot, DatabaseConnection
from .models import Snapshot, DatabaseConnection as DBConnection


async def get_snapshot(session: AsyncSession, snapshot_id: int) -> Optional[Snapshot]:
    """
    Get snapshot by ID.

    Args:
        session: Database session
        snapshot_id: Snapshot ID

    Returns:
        Snapshot object or None if not found
    """
    result = await session.execute(
        select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
    )
    db_snapshot = result.scalar_one_or_none()

    if not db_snapshot:
        return None

    # SchemaSnapshot may not have is_active attribute, default to True
    is_active = getattr(db_snapshot, 'is_active', True)
    
    return Snapshot(
        id=db_snapshot.id,
        name=db_snapshot.name,
        database_connection_id=db_snapshot.connection_id,
        is_active=is_active
    )


async def get_database_connection(session: AsyncSession, connection_id: int) -> Optional[DBConnection]:
    """
    Get database connection by ID.

    Args:
        session: Database session
        connection_id: Connection ID

    Returns:
        DatabaseConnection object or None if not found
    """
    result = await session.execute(
        select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
    )
    db_conn = result.scalar_one_or_none()

    if not db_conn:
        return None

    # DatabaseConnection may not have is_active attribute, default to True
    is_active = getattr(db_conn, 'is_active', True)
    
    return DBConnection(
        id=db_conn.id,
        db_type=db_conn.db_type,
        host=db_conn.host,
        port=db_conn.port,
        username=db_conn.username,
        encrypted_password=db_conn.password_encrypted,
        database_name=db_conn.database_name,
        is_active=is_active
    )


async def get_active_snapshots(session: AsyncSession) -> list[Snapshot]:
    """
    Get all active snapshots.

    Args:
        session: Database session

    Returns:
        List of active snapshots
    """
    # Check if is_active attribute exists before filtering
    if hasattr(SchemaSnapshot, 'is_active'):
        result = await session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.is_active == True)
        )
    else:
        # If is_active doesn't exist, get all snapshots
        result = await session.execute(select(SchemaSnapshot))
    
    db_snapshots = result.scalars().all()

    return [
        Snapshot(
            id=snapshot.id,
            name=snapshot.name,
            database_connection_id=snapshot.connection_id,
            is_active=getattr(snapshot, 'is_active', True)
        )
        for snapshot in db_snapshots
    ]
