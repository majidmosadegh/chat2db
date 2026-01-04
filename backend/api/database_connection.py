from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from pydantic import BaseModel
import asyncio
from cryptography.fernet import Fernet
import os

from .database import (
    DatabaseConnection, get_db_session,
    encrypt_password, decrypt_password, build_connection_string
)


router = APIRouter()


class DatabaseConnectionCreate(BaseModel):
    db_type: str  # postgresql, mysql, sqlserver
    host: str
    port: int
    username: str
    password: str  # Plain text, will be encrypted
    database_name: str


class DatabaseConnectionResponse(BaseModel):
    id: int
    db_type: str
    host: str
    port: int
    username: str
    database_name: str
    is_active: bool


class TestConnectionRequest(BaseModel):
    db_type: str
    host: str
    port: int
    username: str
    password: str
    database_name: str


async def get_database_connection(db_type: str, host: str, port: int, username: str,
                               password: str, database_name: str):
    """Get database connection object for data operations"""
    if db_type.lower() == "postgresql":
        import asyncpg
        return await asyncpg.connect(
            host=host, port=port, user=username,
            password=password, database=database_name
        )
    elif db_type.lower() == "mysql":
        import aiomysql
        return await aiomysql.connect(
            host=host, port=port, user=username,
            password=password, db=database_name
        )
    elif db_type.lower() == "sqlserver":
        # For SQL Server, use synchronous pyodbc in a thread with raw ODBC connection string
        import pyodbc
        import asyncio

        # Build raw ODBC connection string instead of SQLAlchemy format
        if username and password:
            # SQL Server Authentication
            odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={database_name};UID={username};PWD={password}"
        else:
            # Windows Authentication
            odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={database_name};Trusted_Connection=yes"

        def connect_sync():
            return pyodbc.connect(odbc_conn_str, timeout=30)

        return await asyncio.to_thread(connect_sync)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


async def test_database_connection(db_type: str, host: str, port: int, username: str,
                                 password: str, database_name: str) -> dict:
    """Test database connection asynchronously"""
    try:
        conn = await get_database_connection(db_type, host, port, username, password, database_name)

        if db_type.lower() == "postgresql":
            await conn.close()
        elif db_type.lower() == "mysql":
            conn.close()
        elif db_type.lower() == "sqlserver":
            conn.close()

        return {"success": True, "message": "Connection successful"}

    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}


@router.get("/", response_model=List[DatabaseConnectionResponse])
async def get_connections(session: AsyncSession = Depends(get_db_session)):
    """Get all database connections"""
    result = await session.execute(select(DatabaseConnection).order_by(DatabaseConnection.created_at.desc()))
    connections = result.scalars().all()
    return [DatabaseConnectionResponse.model_validate(conn) for conn in connections]


@router.get("/{connection_id}", response_model=DatabaseConnectionResponse)
async def get_connection(connection_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get a specific database connection"""
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return DatabaseConnectionResponse.model_validate(connection)


@router.post("/", response_model=DatabaseConnectionResponse)
async def create_connection(connection_data: DatabaseConnectionCreate, session: AsyncSession = Depends(get_db_session)):
    """Create a new database connection"""
    # Encrypt password
    encrypted_password = encrypt_password(connection_data.password)

    connection = DatabaseConnection(
        db_type=connection_data.db_type,
        host=connection_data.host,
        port=connection_data.port,
        username=connection_data.username,
        password_encrypted=encrypted_password,
        database_name=connection_data.database_name
    )

    session.add(connection)
    await session.commit()
    await session.refresh(connection)
    return DatabaseConnectionResponse.model_validate(connection)


@router.put("/{connection_id}", response_model=DatabaseConnectionResponse)
async def update_connection(
    connection_id: int,
    connection_data: DatabaseConnectionCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Update a database connection"""
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Encrypt new password
    encrypted_password = encrypt_password(connection_data.password)

    connection.db_type = connection_data.db_type
    connection.host = connection_data.host
    connection.port = connection_data.port
    connection.username = connection_data.username
    connection.password_encrypted = encrypted_password
    connection.database_name = connection_data.database_name

    await session.commit()
    await session.refresh(connection)
    return DatabaseConnectionResponse.model_validate(connection)


@router.delete("/{connection_id}")
async def delete_connection(connection_id: int, session: AsyncSession = Depends(get_db_session)):
    """Delete a database connection"""
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    await session.delete(connection)
    await session.commit()
    return {"message": "Connection deleted successfully"}


@router.post("/test")
async def test_connection(test_data: TestConnectionRequest):
    """Test database connection"""
    return await test_database_connection(
        test_data.db_type,
        test_data.host,
        test_data.port,
        test_data.username,
        test_data.password,
        test_data.database_name
    )


@router.get("/active/connection", response_model=DatabaseConnectionResponse)
async def get_active_connection(session: AsyncSession = Depends(get_db_session)):
    """Get the currently active database connection"""
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.is_active == True))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="No active connection found")
    return DatabaseConnectionResponse.model_validate(connection)


@router.post("/{connection_id}/activate")
async def activate_connection(connection_id: int, session: AsyncSession = Depends(get_db_session)):
    """Activate a database connection (only one can be active at a time)"""
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Deactivate all connections
    await session.execute(update(DatabaseConnection).where(DatabaseConnection.is_active == True).values(is_active=False))

    # Activate the selected connection
    connection.is_active = True
    await session.commit()

    return {"message": f"Connection to '{connection.database_name}' activated successfully"}
