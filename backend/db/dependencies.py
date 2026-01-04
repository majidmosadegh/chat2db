"""
FastAPI dependencies for database operations.
Provides clean dependency injection for endpoints.
"""

from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.db_models import get_db_session
from .connector import DatabaseConnector
from .repositories import get_snapshot, get_database_connection
from .models import Snapshot, DatabaseConnection


async def get_database_connector(
    snapshot_id: int = Query(..., description="Snapshot ID"),
    session: AsyncSession = Depends(get_db_session)
) -> DatabaseConnector:
    """
    FastAPI dependency to get a database connector for a snapshot.

    Args:
        snapshot_id: ID of the snapshot
        session: Database session (injected by FastAPI)

    Returns:
        DatabaseConnector: Configured connector for the snapshot

    Raises:
        HTTPException: If snapshot or connection not found
    """
    # Get snapshot
    snapshot = await get_snapshot(session, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot with ID {snapshot_id} not found"
        )

    # Get database connection
    db_conn = await get_database_connection(session, snapshot.database_connection_id)
    if not db_conn:
        raise HTTPException(
            status_code=404,
            detail=f"Database connection for snapshot {snapshot_id} not found"
        )

    # Create and return connector
    connector = DatabaseConnector(snapshot, db_conn)
    return connector


async def get_database_connector_by_name(
    snapshot_name: str,
    session: AsyncSession = Depends(get_db_session)
) -> DatabaseConnector:
    """
    Get database connector by snapshot name.
    Useful for endpoints that accept snapshot names instead of IDs.
    """
    from sqlalchemy import select
    from api.db_models import SchemaSnapshot

    # Find snapshot by name
    result = await session.execute(
        select(SchemaSnapshot).where(SchemaSnapshot.name == snapshot_name)
    )
    db_snapshot = result.scalar_one_or_none()

    if not db_snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot with name '{snapshot_name}' not found"
        )

    # Create snapshot object
    snapshot = Snapshot(
        id=db_snapshot.id,
        name=db_snapshot.name,
        database_connection_id=db_snapshot.connection_id,
        is_active=db_snapshot.is_active
    )

    # Get database connection
    db_conn = await get_database_connection(session, snapshot.database_connection_id)
    if not db_conn:
        raise HTTPException(
            status_code=404,
            detail=f"Database connection for snapshot '{snapshot_name}' not found"
        )

    # Create and return connector
    connector = DatabaseConnector(snapshot, db_conn)
    return connector
