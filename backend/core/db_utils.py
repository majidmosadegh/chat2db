"""
Database Utilities for Dictionary Generation
Centralized database sampling and query utilities
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text

from api.db_models import SchemaSnapshot, DatabaseConnection, SchemaMetadata
from db.connector import DatabaseConnector
from db.repositories import get_snapshot, get_database_connection
from core.config import DEFAULT_ROW_SAMPLE_LIMIT, MAX_COLUMNS_PER_TABLE

logger = logging.getLogger(__name__)


async def get_table_sample_data(
    snapshot_id: int,
    schema_name: str,
    table_name: str,
    limit: int = DEFAULT_ROW_SAMPLE_LIMIT,
    session: Optional[AsyncSession] = None
) -> List[Dict[str, Any]]:
    """
    Get sample data from table with improved query generation.
    Uses DatabaseConnector module and schema-aware queries.
    
    Args:
        snapshot_id: Schema snapshot ID
        schema_name: Schema name
        table_name: Table name
        limit: Number of rows to sample
        session: Optional database session (will create if not provided)
        
    Returns:
        List of sample row dictionaries
    """
    try:
        # Get database connection info from snapshot using repositories
        # If session not provided, create a new one using the session factory
        if not session:
            from api.db_models import async_session
            async with async_session() as new_session:
                return await _get_table_sample_data_with_session(
                    new_session, snapshot_id, schema_name, table_name, limit
                )
        else:
            # Use provided session
            return await _get_table_sample_data_with_session(
                session, snapshot_id, schema_name, table_name, limit
            )
        
    except Exception as e:
        logger.error(f"Failed to sample data from {schema_name}.{table_name}: {e}", exc_info=True)
        return []


async def _get_table_sample_data_with_session(
    session: AsyncSession,
    snapshot_id: int,
    schema_name: str,
    table_name: str,
    limit: int
) -> List[Dict[str, Any]]:
    """Internal helper to get sample data with a session"""
    db_connector = None
    try:
        # Use repository functions to get snapshot and connection
        snapshot = await get_snapshot(session, snapshot_id)
        if not snapshot:
            raise Exception(f"Snapshot {snapshot_id} not found")
        
        db_conn = await get_database_connection(session, snapshot.database_connection_id)
        if not db_conn:
            raise Exception(f"Database connection for snapshot {snapshot_id} not found")
        
        # Create DatabaseConnector instance
        db_connector = DatabaseConnector(snapshot, db_conn)
        await db_connector.connect()
        
        # Get schema info to find primary key for proper ordering
        schema_info = await get_table_schema_with_relationships(
            snapshot_id=snapshot_id,
            schema_name=schema_name,
            table_name=table_name,
            session=session
        )
        
        # Build improved query with schema awareness
        query = _build_schema_aware_query(
            schema_name=schema_name,
            table_name=table_name,
            schema_info=schema_info,
            db_type=db_conn.db_type,
            limit=limit
        )
        
        # Execute query using DatabaseConnector's execute_readonly method
        # Pass limit=None since query already has OFFSET/FETCH or LIMIT to prevent DatabaseConnector from adding TOP
        sample_rows = await db_connector.execute_readonly(query, limit=None)
        
        await db_connector.disconnect()
        return sample_rows
        
    except Exception as e:
        logger.error(f"Failed to sample data from {schema_name}.{table_name}: {e}", exc_info=True)
        if db_connector:
            try:
                await db_connector.disconnect()
            except:
                pass
        return []


def _build_schema_aware_query(
    schema_name: str,
    table_name: str,
    schema_info: Dict[str, Any],
    db_type: str,
    limit: int
) -> str:
    """
    Build schema-aware query for sampling following SQL generation rules.
    NEVER generates SELECT TOP. Uses LIMIT with proper ordering.
    
    Args:
        schema_name: Schema name
        table_name: Table name
        schema_info: Schema information dictionary with columns
        db_type: Database type
        limit: Row limit
        
    Returns:
        SQL query string (uses LIMIT, never TOP)
    """
    # Find primary key column for ordering
    pk_column = None
    columns = schema_info.get("columns", [])
    for col in columns:
        if col.get("is_primary_key"):
            pk_column = col.get("name")
            break
    
    # Build query based on SQL generation rules
    # NEVER use SELECT TOP - always use LIMIT
    if pk_column:
        # Normal sample with PK ordering
        if db_type.lower() == "sqlserver":
            # SQL Server: Use OFFSET/FETCH instead of LIMIT
            query = f"SELECT * FROM [{schema_name}].[{table_name}] ORDER BY [{pk_column}] OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
        else:
            # Other databases: Use LIMIT with ORDER BY
            query = f"SELECT * FROM {schema_name}.{table_name} ORDER BY {pk_column} LIMIT {limit}"
    else:
        # No PK: LIMIT without ordering
        if db_type.lower() == "sqlserver":
            # SQL Server: Use OFFSET/FETCH
            query = f"SELECT * FROM [{schema_name}].[{table_name}] OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
        else:
            # Other databases: Use LIMIT
            query = f"SELECT * FROM {schema_name}.{table_name} LIMIT {limit}"
    
    return query


async def get_table_schema_with_relationships(
    snapshot_id: int,
    schema_name: str,
    table_name: str,
    session: AsyncSession
) -> Dict[str, Any]:
    """
    Get table schema information including columns and foreign key relationships.
    Enhanced version with relationship context.
    
    Args:
        snapshot_id: Schema snapshot ID
        schema_name: Schema name
        table_name: Table name
        session: Database session
        
    Returns:
        Dictionary with schema information
    """
    try:
        # Get columns (limit to prevent unlimited columns)
        result = await session.execute(
            select(SchemaMetadata).where(
                and_(
                    SchemaMetadata.schema_snapshot_id == snapshot_id,
                    SchemaMetadata.schema_name == schema_name,
                    SchemaMetadata.table_name == table_name,
                    SchemaMetadata.column_name.isnot(None),
                    SchemaMetadata.column_name != ''
                )
            ).order_by(SchemaMetadata.column_order).limit(MAX_COLUMNS_PER_TABLE)
        )
        columns = result.scalars().all()
        
        # Build relationships from foreign keys
        relationships = []
        for col in columns:
            if col.is_foreign_key and col.foreign_key_table and col.foreign_key_column:
                relationships.append({
                    "from_column": col.column_name,
                    "to_table": col.foreign_key_table,
                    "to_column": col.foreign_key_column
                })
        
        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "columns": [
                {
                    "name": col.column_name,
                    "data_type": col.column_type,
                    "is_primary_key": col.is_primary_key,
                    "is_foreign_key": col.is_foreign_key,
                    "foreign_key_table": col.foreign_key_table,
                    "foreign_key_column": col.foreign_key_column,
                }
                for col in columns if col.column_name
            ],
            "relationships": relationships
        }
        
    except Exception as e:
        logger.error(f"Failed to get schema for {schema_name}.{table_name}: {e}")
        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "columns": [],
            "relationships": []
        }


def extract_query_keywords(query: str) -> List[str]:
    """
    Extract keywords from query for intent detection.
    
    Args:
        query: SQL query string
        
    Returns:
        List of extracted keywords
    """
    # Simple keyword extraction - can be enhanced
    keywords = []
    query_upper = query.upper()
    
    # Common SQL keywords
    sql_keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY', 'HAVING']
    for keyword in sql_keywords:
        if keyword in query_upper:
            keywords.append(keyword)
    
    return keywords


def detect_query_intent(query: str) -> str:
    """
    Detect query intent for query enrichment.
    
    Args:
        query: SQL query string
        
    Returns:
        Intent string (e.g., 'aggregation', 'filtering', 'join', etc.)
    """
    query_upper = query.upper()
    
    if 'COUNT' in query_upper or 'SUM' in query_upper or 'AVG' in query_upper:
        return 'aggregation'
    elif 'WHERE' in query_upper:
        return 'filtering'
    elif 'JOIN' in query_upper:
        return 'join'
    elif 'GROUP BY' in query_upper:
        return 'grouping'
    else:
        return 'selection'

