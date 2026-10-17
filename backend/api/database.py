from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from pydantic import BaseModel
import asyncio
import os
from cryptography.fernet import Fernet
import pyodbc
from loguru import logger

from .db_models import DatabaseConnection, LLMModel, get_db_session
from .exceptions import (
    DatabaseConnectionError,
    ValidationError,
    create_http_exception_from_sqlpt_exception
)

# Encryption setup.
# Never commit encryption keys. Set CHAT2DB_ENCRYPTION_KEY to a Fernet key
# supplied through the deployment environment or a secret manager.
# Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv("CHAT2DB_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise RuntimeError(
        "CHAT2DB_ENCRYPTION_KEY is required. Set it in the environment; "
        "do not store encryption keys in source control."
    )

try:
    cipher = Fernet(ENCRYPTION_KEY.encode())
except Exception as exc:
    raise RuntimeError("CHAT2DB_ENCRYPTION_KEY must be a valid Fernet key.") from exc

router = APIRouter()

@router.get("/test-ping")
def test_ping():
    """Simple test endpoint"""
    return {"success": True, "message": "Database router works!"}


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


def encrypt_password(password: str) -> str:
    """Encrypt password for storage"""
    return cipher.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt password for use. Fail closed if decryption is impossible."""
    if not encrypted_password:
        return ""
    try:
        return cipher.decrypt(encrypted_password.encode()).decode()
    except Exception as exc:
        logger.warning(
            "Stored password could not be decrypted; "
            "verify the configured encryption key."
        )
        raise ValueError(
            "Unable to decrypt the stored password. Verify CHAT2DB_ENCRYPTION_KEY "
            "and re-enter the credential if the original key is unavailable."
        ) from exc


def encrypt_api_key(api_key: str) -> str:
    """Encrypt API key for storage"""
    if api_key:
        return cipher.encrypt(api_key.encode()).decode()
    return api_key


def decrypt_api_key(encrypted_api_key: str) -> str:
    """Decrypt API key for use"""
    if not encrypted_api_key:
        return encrypted_api_key

    try:
        return cipher.decrypt(encrypted_api_key.encode()).decode()
    except Exception as exc:
        # Never silently treat an undecryptable value as plaintext.
        logger.warning("Stored API key could not be decrypted; verify the configured encryption key.")
        raise ValueError(
            "Unable to decrypt the stored API key. Verify CHAT2DB_ENCRYPTION_KEY "
            "and re-enter the credential if the original key is unavailable."
        ) from exc


def build_connection_string(db_type: str, host: str, port: int, username: str,
                           password: str, database_name: str) -> str:
    """Build database connection string"""
    if db_type.lower() == "postgresql":
        return f"postgresql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type.lower() == "mysql":
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type.lower() == "sqlserver":
        if username and password:
            # SQL Server Authentication - use aioodbc for async support
            return f"mssql+aioodbc://{username}:{password}@{host}:{port}/{database_name}?driver=ODBC+Driver+17+for+SQL+Server"
        else:
            # Windows Authentication - fallback to pyodbc if needed
            return f"mssql+pyodbc://@{host}:{port}/{database_name}?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


async def test_database_connection(db_type: str, host: str, port: int, username: str,
                                 password: str, database_name: str) -> dict:
    """Test database connection asynchronously"""
    try:
        # Validate inputs
        if not db_type or db_type.lower() not in ["postgresql", "mysql", "sqlserver"]:
            raise ValidationError(f"Unsupported database type: {db_type}", field="db_type", value=db_type)

        if not host or not host.strip():
            raise ValidationError("Host is required", field="host")

        if not isinstance(port, int) or port <= 0 or port > 65535:
            raise ValidationError("Port must be between 1 and 65535", field="port", value=port)

        if not database_name or not database_name.strip():
            raise ValidationError("Database name is required", field="database_name")

        logger.info(f"Testing connection to {db_type} database: {host}:{port}/{database_name}")

        connection_string = build_connection_string(db_type, host, port, username, password, database_name)

        try:
            if db_type.lower() == "postgresql":
                import asyncpg
                conn = await asyncpg.connect(connection_string)
                await conn.close()
            elif db_type.lower() == "mysql":
                import aiomysql
                conn = await aiomysql.connect(
                    host=host, port=port, user=username,
                    password=password, db=database_name
                )
                conn.close()
            elif db_type.lower() == "sqlserver":
                # For SQL Server, use synchronous connection in a separate thread
                def test_sqlserver_sync():
                    try:
                        import pyodbc
                        if username and password:
                            # SQL Server Authentication
                            odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={database_name};UID={username};PWD={password}"
                        else:
                            # Windows Authentication
                            odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={database_name};Trusted_Connection=yes"

                        conn = pyodbc.connect(odbc_conn_str, timeout=10)
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                        cursor.close()
                        conn.close()
                        return True
                    except Exception as e:
                        raise Exception(f"SQL Server connection failed: {str(e)}")

                # Use asyncio.to_thread for Python 3.9+
                result = await asyncio.to_thread(test_sqlserver_sync)
            else:
                raise ValidationError(f"Unsupported database type: {db_type}", field="db_type", value=db_type)

            logger.success(f"Successfully connected to {db_type} database: {host}:{port}/{database_name}")
            return {"success": True, "message": f"Successfully connected to {db_type} database"}

        except ImportError as e:
            raise DatabaseConnectionError(
                f"Required database driver not installed: {e}",
                db_type=db_type
            )
        except asyncio.TimeoutError:
            raise DatabaseConnectionError(
                "Connection timeout",
                db_type=db_type,
                host=host
            )
        except Exception as e:
            logger.warning(f"Database connection failed for {db_type} at {host}:{port}: {e}")
            raise DatabaseConnectionError(
                f"Failed to connect to {db_type} database: {str(e)}",
                db_type=db_type,
                host=host
            )

    except (ValidationError, DatabaseConnectionError) as e:
        return {"success": False, "message": e.message, "error_type": e.__class__.__name__, "details": e.details}
    except Exception as e:
        logger.error(f"Unexpected error testing database connection: {e}")
        return {"success": False, "message": f"Unexpected error: {str(e)}", "error_type": "UnexpectedError"}


@router.get("/", response_model=List[DatabaseConnectionResponse])
async def get_connections(session: AsyncSession = Depends(get_db_session)):
    """Get all database connections"""
    result = await session.execute(select(DatabaseConnection).order_by(DatabaseConnection.created_at.desc()))
    connections = result.scalars().all()

    # Convert SQLAlchemy models to dicts for Pydantic response
    connection_dicts = [{
        "id": conn.id,
        "db_type": conn.db_type,
        "host": conn.host,
        "port": conn.port,
        "username": conn.username,
        "database_name": conn.database_name,
        "is_active": conn.is_active
    } for conn in connections]
    return [DatabaseConnectionResponse(**conn_dict) for conn_dict in connection_dicts]


@router.get("/{connection_id}", response_model=DatabaseConnectionResponse)
async def get_connection(connection_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get a specific database connection"""
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    connection_dict = {
        "id": connection.id,
        "db_type": connection.db_type,
        "host": connection.host,
        "port": connection.port,
        "username": connection.username,
        "database_name": connection.database_name,
        "is_active": connection.is_active
    }
    return DatabaseConnectionResponse(**connection_dict)


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

    # Convert SQLAlchemy model to dict for Pydantic response
    connection_dict = {
        "id": connection.id,
        "db_type": connection.db_type,
        "host": connection.host,
        "port": connection.port,
        "username": connection.username,
        "database_name": connection.database_name,
        "is_active": connection.is_active
    }
    return DatabaseConnectionResponse(**connection_dict)


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

    connection_dict = {
        "id": connection.id,
        "db_type": connection.db_type,
        "host": connection.host,
        "port": connection.port,
        "username": connection.username,
        "database_name": connection.database_name,
        "is_active": connection.is_active
    }
    return DatabaseConnectionResponse(**connection_dict)


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


@router.get("/test-ping")
def test_ping():
    """Simple test endpoint"""
    return {"success": True, "message": "Database router works!"}

@router.post("/test")
def test_connection(test_data: TestConnectionRequest):
    """Test database connection"""
    try:
        print(f"Testing connection to {test_data.db_type} at {test_data.host}:{test_data.port}")

        if test_data.db_type.lower() == "sqlserver":
            # Try SQL Server Authentication first
            odbc_conn_str = ""
            auth_method = ""

            if test_data.username and test_data.password:
                odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={test_data.host},{test_data.port};DATABASE={test_data.database_name};UID={test_data.username};PWD={test_data.password}"
                auth_method = "SQL Server Authentication"
            else:
                # Try Windows Authentication if no credentials provided
                odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={test_data.host},{test_data.port};DATABASE={test_data.database_name};Trusted_Connection=yes"
                auth_method = "Windows Authentication"

            print(f"Using {auth_method}")
            conn = pyodbc.connect(odbc_conn_str, timeout=10)
            cursor = conn.cursor()
            cursor.execute("SELECT SUSER_NAME() as current_username, @@SERVERNAME as server_name")
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            result = {
                "success": True,
                "message": f"Connection successful using {auth_method}",
                "user": result[0],
                "server": result[1]
            }
        else:
            result = {"success": False, "message": f"Unsupported database type: {test_data.db_type}"}

        print(f"Test result: {result}")
        return result
    except Exception as e:
        error_msg = str(e)
        print(f"Test failed with exception: {error_msg}")

        # Provide helpful error messages
        if "18456" in error_msg:
            return {
                "success": False,
                "message": "Authentication failed. Check username/password or enable Mixed Authentication Mode.",
                "error_code": "18456"
            }
        elif "4060" in error_msg:
            return {
                "success": False,
                "message": "Database not found or access denied.",
                "error_code": "4060"
            }
        else:
            return {"success": False, "message": f"Connection failed: {error_msg}"}

@router.get("/test-simple")
async def test_simple():
    """Simple test endpoint"""
    return {"success": True, "message": "Simple test works!"}

@router.get("/ping")
def ping():
    """Very simple synchronous endpoint"""
    return {"message": "pong"}


@router.get("/active/connection", response_model=DatabaseConnectionResponse)
async def get_active_connection(session: AsyncSession = Depends(get_db_session)):
    """Get the currently active database connection"""
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.is_active == True))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="No active connection found")

    connection_dict = {
        "id": connection.id,
        "db_type": connection.db_type,
        "host": connection.host,
        "port": connection.port,
        "username": connection.username,
        "database_name": connection.database_name,
        "is_active": connection.is_active
    }
    return DatabaseConnectionResponse(**connection_dict)


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