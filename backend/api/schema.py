from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from pydantic import BaseModel
import json
from sqlalchemy import select, delete, update

from .db_models import SchemaMetadata, SchemaSnapshot, DatabaseConnection, get_db_session
from .database import decrypt_password, build_connection_string

router = APIRouter()

class SchemaInfo(BaseModel):
    schema_name: str
    table_name: str
    column_name: str
    column_type: str
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_table: Optional[str]
    foreign_key_column: Optional[str]


class TableInfo(BaseModel):
    schema_name: str
    table_name: str
    row_count: int = 0
    columns: List[dict]


class SchemaSnapshotCreate(BaseModel):
    name: str
    description: Optional[str] = None
    connection_id: int


class SchemaSnapshotResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    connection_id: int
    created_at: str
    table_count: int = 0

@router.post("/introspect")
async def introspect_schema(session: AsyncSession = Depends(get_db_session)):
    """Introspect the active database connection and store schema metadata"""
    # Get active connection
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.is_active == True))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=400, detail="No active database connection found")

    return await introspect_schema_by_id(connection.id, session)

@router.post("/introspect/{connection_id}")
async def introspect_schema_by_id_endpoint(connection_id: int, session: AsyncSession = Depends(get_db_session)):
    """Introspect a specific database connection by ID"""
    return await introspect_schema_by_id(connection_id, session)


class SchemaSnapshotCreateWithConnection(BaseModel):
    name: str
    description: Optional[str] = None
    connection_id: int  # Specify which connection this snapshot is for


@router.post("/snapshots")
async def create_schema_snapshot(
    snapshot_data: SchemaSnapshotCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a schema snapshot from introspected data"""
    # For backward compatibility, use active connection
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.is_active == True))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=400, detail="No active database connection found")

    return await create_schema_snapshot_with_connection(
        SchemaSnapshotCreateWithConnection(
            name=snapshot_data.name,
            description=snapshot_data.description,
            connection_id=connection.id
        ),
        session
    )


@router.post("/snapshots/with-connection")
async def create_schema_snapshot_with_connection_endpoint(
    snapshot_data: SchemaSnapshotCreateWithConnection,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a schema snapshot for a specific database connection"""
    return await create_schema_snapshot_with_connection(snapshot_data, session)


async def create_schema_snapshot_with_connection(
    snapshot_data: SchemaSnapshotCreateWithConnection,
    session: AsyncSession
):
    """Create a schema snapshot for a specific database connection"""

    # Check if name already exists for this connection
    result = await session.execute(
        select(SchemaSnapshot).where(
            SchemaSnapshot.name == snapshot_data.name,
            SchemaSnapshot.connection_id == snapshot_data.connection_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Schema snapshot name '{snapshot_data.name}' already exists for this database connection")

    # Verify connection exists
    result = await session.execute(
        select(DatabaseConnection).where(DatabaseConnection.id == snapshot_data.connection_id)
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail=f"Database connection with id {snapshot_data.connection_id} not found")

    # Create the snapshot
    snapshot = SchemaSnapshot(
        name=snapshot_data.name,
        description=snapshot_data.description,
        connection_id=snapshot_data.connection_id
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)

    return {
        "message": "Schema snapshot created successfully",
        "snapshot": {
            "id": snapshot.id,
            "name": snapshot.name,
            "description": snapshot.description
        }
    }


@router.post("/snapshots/{snapshot_id}/save-data")
async def save_schema_data_to_snapshot(
    snapshot_id: int,
    schema_data: dict,
    session: AsyncSession = Depends(get_db_session)
):
    """Save introspected schema data to an existing snapshot"""
    # Verify snapshot exists
    result = await session.execute(select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Schema snapshot not found")

    # Clear existing metadata for this snapshot
    await session.execute(delete(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == snapshot_id))

    # Save new metadata
    data_items = schema_data.get("schema_data", [])

    for table_item in data_items:
        schema_name = table_item["schema_name"]
        table_name = table_item["table_name"]
        row_count = table_item.get("row_count", 0)

        # Save table-level metadata (without column_name)
        table_metadata = SchemaMetadata(
            schema_snapshot_id=snapshot_id,
            schema_name=schema_name,
            table_name=table_name,
            column_name="",  # Empty string for table-level metadata
            column_type="",  # Empty string for table-level metadata
            row_count=row_count
        )
        session.add(table_metadata)

        # Save column-level metadata
        for column_item in table_item.get("columns", []):
            metadata = SchemaMetadata(
                schema_snapshot_id=snapshot_id,
                schema_name=schema_name,
                table_name=table_name,
                column_name=column_item["column_name"],
                column_type=column_item["column_type"],
                is_primary_key=column_item.get("is_primary_key", False),
                is_foreign_key=column_item.get("is_foreign_key", False),
                foreign_key_table=column_item.get("foreign_key_table"),
                foreign_key_column=column_item.get("foreign_key_column"),
                column_order=column_item.get("column_id")
            )
            session.add(metadata)

    await session.commit()

    return {"message": f"Successfully saved {len(data_items)} schema items to snapshot '{snapshot.name}'"}


@router.get("/snapshots", response_model=List[SchemaSnapshotResponse])
async def get_schema_snapshots(session: AsyncSession = Depends(get_db_session)):
    """Get all schema snapshots"""
    result = await session.execute(
        select(SchemaSnapshot)
    )
    snapshots = result.scalars().all()

    response = []
    for snapshot in snapshots:
        # Count tables in this snapshot
        table_result = await session.execute(
            select(SchemaMetadata.table_name).where(
                SchemaMetadata.schema_snapshot_id == snapshot.id
            ).distinct()
        )
        table_count = len(table_result.fetchall())

        response.append(SchemaSnapshotResponse(
            id=snapshot.id,
            name=snapshot.name,
            description=snapshot.description,
            connection_id=snapshot.connection_id,
            created_at=snapshot.created_at.isoformat() if snapshot.created_at else None,
            table_count=table_count
        ))

    return response


# Removed activate_schema_snapshot endpoint - no longer needed


@router.delete("/snapshots/{snapshot_id}")
async def delete_schema_snapshot(snapshot_id: int, session: AsyncSession = Depends(get_db_session)):
    """Delete a schema snapshot"""
    result = await session.execute(select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Schema snapshot not found")

    # Delete associated metadata and data dictionary entries
    await session.execute(delete(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == snapshot_id))
    # Note: DataDictionary deletion will be handled by cascade delete if configured

    # Delete the snapshot
    await session.delete(snapshot)
    await session.commit()

    return {"message": f"Schema snapshot '{snapshot.name}' deleted successfully"}

async def introspect_schema_by_id(connection_id: int, session: AsyncSession):
    """Introspect schema for a specific connection ID"""
    from sqlalchemy import select

    # Get connection by ID
    result = await session.execute(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Database connection not found")

    try:
        # Decrypt password
        if connection.password_encrypted and connection.password_encrypted.strip():
            password = decrypt_password(connection.password_encrypted)
        else:
            password = ""  # Empty password for Windows Authentication

        # Build connection string
        conn_string = build_connection_string(
            connection.db_type, connection.host, connection.port,
            connection.username, password, connection.database_name
        )

        # Connect and introspect based on database type
        if connection.db_type.lower() == "sqlserver":
            # For SQL Server, use direct synchronous call with proper connection details
            schema_data = await introspect_sqlserver_direct(
                connection.host,
                connection.port,
                connection.database_name,
                connection.username if connection.username else "",
                password
            )
        else:
            schema_data = await introspect_database(
                connection.db_type, conn_string, connection.database_name
            )

        # Return schema data for snapshot creation
        # Do not automatically save to database
        return {
            "connection_id": connection_id,
            "database_name": connection.database_name,
            "schema_data": schema_data,
            "total_items": len(schema_data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema introspection failed: {str(e)}")

async def introspect_database(db_type: str, conn_string: str, db_name: str) -> List[dict]:
    """Introspect database schema based on type"""
    if db_type.lower() == "postgresql":
        return await introspect_postgresql(conn_string, db_name)
    elif db_type.lower() == "mysql":
        return await introspect_mysql(conn_string, db_name)
    elif db_type.lower() == "sqlserver":
        return await introspect_sqlserver(conn_string, db_name)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

async def introspect_postgresql(conn_string: str, db_name: str) -> List[dict]:
    """Introspect PostgreSQL database"""
    import asyncpg

    conn = await asyncpg.connect(conn_string)
    try:
        # Get unique tables first
        table_query = """
        SELECT DISTINCT
            n.nspname as schema_name,
            t.relname as table_name
        FROM pg_class t
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE t.relkind = 'r'
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY n.nspname, t.relname
        """

        tables = await conn.fetch(table_query)

        result = []
        for table_row in tables:
            schema_name = table_row['schema_name']
            table_name = table_row['table_name']

            # Get row count for this table
            try:
                count_query = f'SELECT COUNT(*) as row_count FROM "{schema_name}"."{table_name}"'
                count_result = await conn.fetchval(count_query)
                row_count = int(count_result) if count_result is not None else 0
            except Exception:
                # If count fails (permissions, etc.), set to 0
                row_count = 0

            # Get column information for this table
            column_query = """
            SELECT
                c.attname as column_name,
                pg_catalog.format_type(c.atttypid, c.atttypmod) as column_type,
                CASE WHEN pk.contype = 'p' THEN true ELSE false END as is_primary_key,
                CASE WHEN fk.contype = 'f' THEN true ELSE false END as is_foreign_key,
                fk_ref.relname as foreign_key_table,
                fk_ref_att.attname as foreign_key_column
            FROM pg_class t
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_attribute c ON c.attrelid = t.oid AND c.attnum > 0
            LEFT JOIN pg_constraint pk ON pk.conrelid = t.oid AND pk.contype = 'p' AND c.attnum = ANY(pk.conkey)
            LEFT JOIN pg_constraint fk ON fk.conrelid = t.oid AND fk.contype = 'f' AND c.attnum = ANY(fk.conkey)
            LEFT JOIN pg_class fk_ref ON fk.confrelid = fk_ref.oid
            LEFT JOIN pg_attribute fk_ref_att ON fk_ref_att.attrelid = fk.confrelid AND fk_ref_att.attnum = fk.confkey[1]
            WHERE t.relkind = 'r'
            AND n.nspname = $1
            AND t.relname = $2
            AND c.attname NOT IN ('tableoid', 'cmax', 'xmax', 'cmin', 'xmin', 'ctid')
            ORDER BY c.attnum
            """

            columns = await conn.fetch(column_query, schema_name, table_name)

            result.append({
                'schema_name': schema_name,
                'table_name': table_name,
                'row_count': row_count,
                'columns': [dict(col) for col in columns]
            })

        return result
    finally:
        await conn.close()

async def introspect_mysql(conn_string: str, db_name: str) -> List[dict]:
    """Introspect MySQL database"""
    import aiomysql

    conn = await aiomysql.connect(conn_string)
    try:
        cursor = await conn.cursor()

        # Get unique tables first
        table_query = """
        SELECT TABLE_SCHEMA as schema_name, TABLE_NAME as table_name
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
        AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """

        await cursor.execute(table_query, (db_name,))
        table_rows = await cursor.fetchall()

        result = []
        for table_row in table_rows:
            schema_name = table_row[0]
            table_name = table_row[1]

            # Get row count for this table
            try:
                count_cursor = await conn.cursor()
                count_query = f"SELECT COUNT(*) FROM `{schema_name}`.`{table_name}`"
                await count_cursor.execute(count_query)
                count_result = await count_cursor.fetchone()
                row_count = int(count_result[0]) if count_result else 0
                await count_cursor.close()
            except Exception:
                # If count fails (permissions, etc.), set to 0
                row_count = 0

            # Get column information for this table
            column_query = """
            SELECT
                COLUMN_NAME as column_name,
                COLUMN_TYPE as column_type,
                CASE WHEN COLUMN_KEY = 'PRI' THEN true ELSE false END as is_primary_key,
                CASE WHEN COLUMN_KEY = 'MUL' AND REFERENCED_TABLE_NAME IS NOT NULL THEN true ELSE false END as is_foreign_key,
                REFERENCED_TABLE_NAME as foreign_key_table,
                REFERENCED_COLUMN_NAME as foreign_key_column
            FROM information_schema.COLUMNS c
            LEFT JOIN information_schema.KEY_COLUMN_USAGE kcu
                ON c.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                AND c.TABLE_NAME = kcu.TABLE_NAME
                AND c.COLUMN_NAME = kcu.COLUMN_NAME
                AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            WHERE c.TABLE_SCHEMA = %s
            AND c.TABLE_NAME = %s
            ORDER BY c.ORDINAL_POSITION
            """

            await cursor.execute(column_query, (schema_name, table_name))
            column_rows = await cursor.fetchall()
            column_columns = [desc[0] for desc in cursor.description]

            columns = []
            for row in column_rows:
                columns.append(dict(zip(column_columns, row)))

            result.append({
                'schema_name': schema_name,
                'table_name': table_name,
                'row_count': row_count,
                'columns': columns
            })

        await cursor.close()
        return result
    finally:
        conn.close()

async def introspect_sqlserver_direct(host: str, port: int, db_name: str, username: str = "", password: str = "") -> List[dict]:
    """Direct SQL Server introspection with specific connection parameters"""
    import pyodbc
    import asyncio

    def introspect_sqlserver_sync():
        """Synchronous SQL Server introspection with direct connection"""
        print(f"Starting SQL Server introspection for {host}:{port}/{db_name}...")
        try:
            # Build ODBC connection string for the specific server
            if username and password:
                # SQL Server Authentication
                odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={db_name};UID={username};PWD={password}"
                auth_type = "SQL Server Authentication"
            else:
                # Windows Authentication
                odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={db_name};Trusted_Connection=yes"
                auth_type = "Windows Authentication"

            print(f"Connecting to SQL Server with {auth_type}: {odbc_conn_str[:80]}...")

            conn = pyodbc.connect(odbc_conn_str, timeout=30)
            cursor = conn.cursor()

            # Test connection first
            cursor.execute("SELECT @@SERVERNAME as server_name, DB_NAME() as db_name")
            server_info = cursor.fetchone()
            print(f"Connected to SQL Server: {server_info[0]}, Database: {server_info[1]}")

            # Get unique tables first
            table_query = """
            SELECT s.name as schema_name, t.name as table_name
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name != 'sys'
            ORDER BY s.name, t.name
            """

            print("Getting list of tables...")
            cursor.execute(table_query)
            table_rows = cursor.fetchall()

            result = []
            for table_row in table_rows:
                schema_name = table_row[0]
                table_name = table_row[1]

                # Get row count for this table
                try:
                    count_query = f"SELECT COUNT(*) FROM [{schema_name}].[{table_name}]"
                    cursor.execute(count_query)
                    count_result = cursor.fetchone()
                    row_count = int(count_result[0]) if count_result else 0
                    print(f"Table {schema_name}.{table_name}: {row_count} rows")
                except Exception as e:
                    print(f"Could not count rows for {schema_name}.{table_name}: {e}")
                    row_count = 0

                # Get column information for this table
                column_query = """
                SELECT
                    c.name as column_name,
                    ty.name +
                        CASE
                            WHEN ty.name IN ('varchar', 'nvarchar', 'char', 'nchar') THEN '(' + CASE WHEN c.max_length = -1 THEN 'max' ELSE CAST(c.max_length AS varchar) END + ')'
                            WHEN ty.name IN ('decimal', 'numeric') THEN '(' + CAST(c.precision AS varchar) + ',' + CAST(c.scale AS varchar) + ')'
                            ELSE ''
                        END as column_type,
                    CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END as is_primary_key,
                    CASE WHEN fk.parent_column_id IS NOT NULL THEN 1 ELSE 0 END as is_foreign_key,
                    ref_t.name as foreign_key_table,
                    ref_c.name as foreign_key_column
                FROM sys.columns c
                JOIN sys.types ty ON c.user_type_id = ty.user_type_id
                JOIN sys.tables t ON c.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                LEFT JOIN (
                    SELECT ic.object_id, ic.column_id
                    FROM sys.indexes i
                    JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                    WHERE i.is_primary_key = 1
                ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
                LEFT JOIN sys.foreign_key_columns fk ON c.object_id = fk.parent_object_id AND c.column_id = fk.parent_column_id
                LEFT JOIN sys.tables ref_t ON fk.referenced_object_id = ref_t.object_id
                LEFT JOIN sys.columns ref_c ON fk.referenced_object_id = ref_c.object_id AND fk.referenced_column_id = ref_c.column_id
                WHERE s.name = ?
                AND t.name = ?
                ORDER BY c.column_id
                """

                cursor.execute(column_query, (schema_name, table_name))
                column_rows = cursor.fetchall()
                column_columns = [desc[0] for desc in cursor.description]

                columns = []
                for row in column_rows:
                    row_dict = dict(zip(column_columns, row))
                    # Convert bits to booleans
                    row_dict['is_primary_key'] = bool(row_dict['is_primary_key'])
                    row_dict['is_foreign_key'] = bool(row_dict['is_foreign_key'])
                    columns.append(row_dict)

                result.append({
                    'schema_name': schema_name,
                    'table_name': table_name,
                    'row_count': row_count,
                    'columns': columns
                })

            cursor.close()
            conn.close()

            print(f"Successfully introspected {len(result)} schema items from {host}:{port}/{db_name}")
            return result

        except Exception as e:
            import traceback
            print(f"SQL Server introspection failed for {host}:{port}/{db_name}: {str(e)}")
            traceback.print_exc()
            raise Exception(f"SQL Server introspection failed: {str(e)}")

    # Run the synchronous code in a thread
    try:
        print("Running introspection in thread...")
        result = await asyncio.to_thread(introspect_sqlserver_sync)
        print(f"Introspection completed successfully with {len(result)} items")
        return result
    except Exception as e:
        import traceback
        print(f"Async introspection wrapper failed: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        raise

async def introspect_sqlserver(conn_string: str, db_name: str) -> List[dict]:
    """Introspect SQL Server database"""
    import pyodbc
    import asyncio

    def introspect_sqlserver_sync():
        """Synchronous SQL Server introspection"""
        print("Starting SQL Server introspection...")
        try:
            # Always build ODBC connection string from scratch for reliability
            # We know we're using localhost with Windows Authentication
            odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER=localhost,1433;DATABASE=master;Trusted_Connection=yes"
            print(f"Connecting to SQL Server with: {odbc_conn_str[:60]}...")
            conn = pyodbc.connect(odbc_conn_str, timeout=30)
            cursor = conn.cursor()

            # Test connection first
            cursor.execute("SELECT @@VERSION as version")
            version = cursor.fetchone()
            print(f"Connected to SQL Server: {version[0][:50]}...")

            # Get unique tables first
            table_query = """
            SELECT s.name as schema_name, t.name as table_name
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name != 'sys'
            ORDER BY s.name, t.name
            """

            print("Getting list of tables...")
            cursor.execute(table_query)
            table_rows = cursor.fetchall()

            result = []
            for table_row in table_rows:
                schema_name = table_row[0]
                table_name = table_row[1]

                # Get row count for this table
                try:
                    count_query = f"SELECT COUNT(*) FROM [{schema_name}].[{table_name}]"
                    cursor.execute(count_query)
                    count_result = cursor.fetchone()
                    row_count = int(count_result[0]) if count_result else 0
                    print(f"Table {schema_name}.{table_name}: {row_count} rows")
                except Exception as e:
                    print(f"Could not count rows for {schema_name}.{table_name}: {e}")
                    row_count = 0

                # Get column information for this table
                column_query = """
                SELECT
                    c.name as column_name,
                    ty.name +
                        CASE
                            WHEN ty.name IN ('varchar', 'nvarchar', 'char', 'nchar') THEN '(' + CASE WHEN c.max_length = -1 THEN 'max' ELSE CAST(c.max_length AS varchar) END + ')'
                            WHEN ty.name IN ('decimal', 'numeric') THEN '(' + CAST(c.precision AS varchar) + ',' + CAST(c.scale AS varchar) + ')'
                            ELSE ''
                        END as column_type,
                    CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END as is_primary_key,
                    CASE WHEN fk.parent_column_id IS NOT NULL THEN 1 ELSE 0 END as is_foreign_key,
                    ref_t.name as foreign_key_table,
                    ref_c.name as foreign_key_column
                FROM sys.columns c
                JOIN sys.types ty ON c.user_type_id = ty.user_type_id
                JOIN sys.tables t ON c.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                LEFT JOIN (
                    SELECT ic.object_id, ic.column_id
                    FROM sys.indexes i
                    JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                    WHERE i.is_primary_key = 1
                ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
                LEFT JOIN sys.foreign_key_columns fk ON c.object_id = fk.parent_object_id AND c.column_id = fk.parent_column_id
                LEFT JOIN sys.tables ref_t ON fk.referenced_object_id = ref_t.object_id
                LEFT JOIN sys.columns ref_c ON fk.referenced_object_id = ref_c.object_id AND fk.referenced_column_id = ref_c.column_id
                WHERE s.name = ?
                AND t.name = ?
                ORDER BY c.column_id
                """

                cursor.execute(column_query, (schema_name, table_name))
                column_rows = cursor.fetchall()
                column_columns = [desc[0] for desc in cursor.description]

                columns = []
                for row in column_rows:
                    row_dict = dict(zip(column_columns, row))
                    # Convert bits to booleans
                    row_dict['is_primary_key'] = bool(row_dict['is_primary_key'])
                    row_dict['is_foreign_key'] = bool(row_dict['is_foreign_key'])
                    columns.append(row_dict)

                result.append({
                    'schema_name': schema_name,
                    'table_name': table_name,
                    'row_count': row_count,
                    'columns': columns
                })

            cursor.close()
            conn.close()

            print(f"Successfully introspected {len(result)} schema items")
            return result

        except Exception as e:
            import traceback
            print(f"SQL Server introspection failed: {str(e)}")
            print("Traceback:")
            traceback.print_exc()
            raise Exception(f"SQL Server introspection failed: {str(e)}")

    # Run the synchronous code in a thread
    try:
        print("Running introspection in thread...")
        result = await asyncio.to_thread(introspect_sqlserver_sync)
        print(f"Introspection completed successfully with {len(result)} items")
        return result
    except Exception as e:
        import traceback
        print(f"Async introspection wrapper failed: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        raise

@router.get("/")
async def get_schema_metadata(snapshot_id: Optional[int] = None, session: AsyncSession = Depends(get_db_session)):
    """Get stored schema metadata for specified snapshot"""
    if snapshot_id is None:
        raise HTTPException(status_code=400, detail="snapshot_id query parameter is required")

    # Build select statement without column_order to avoid database schema mismatch
    query = select(
        SchemaMetadata.schema_name,
        SchemaMetadata.table_name,
        SchemaMetadata.column_name,
        SchemaMetadata.column_type,
        SchemaMetadata.is_primary_key,
        SchemaMetadata.is_foreign_key,
        SchemaMetadata.foreign_key_table,
        SchemaMetadata.foreign_key_column
    ).where(
        SchemaMetadata.schema_snapshot_id == snapshot_id,
        SchemaMetadata.column_name != ""  # Exclude table-level metadata records
    ).order_by(
        SchemaMetadata.schema_name, SchemaMetadata.table_name, SchemaMetadata.column_order
    )

    result = await session.execute(query)
    rows = result.all()
    return [{"schema_name": row[0], "table_name": row[1], "column_name": row[2],
             "column_type": row[3], "is_primary_key": row[4], "is_foreign_key": row[5],
             "foreign_key_table": row[6], "foreign_key_column": row[7]}
            for row in rows]

@router.get("/tables", response_model=List[TableInfo])
async def get_tables(snapshot_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get list of tables with their columns and row counts for specified snapshot.
    Always returns tables first, then relationships are shown if they exist."""

    # Verify snapshot exists
    snapshot_query = select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
    snapshot_result = await session.execute(snapshot_query)
    snapshot = snapshot_result.scalar_one_or_none()
    
    if not snapshot:
        # Return empty list if snapshot doesn't exist (frontend will handle it)
        return []

    # Get all metadata for this snapshot - use same approach as get_snapshot_data
    # Simple query without order_by to avoid NULL issues
    query = select(
        SchemaMetadata.schema_name,
        SchemaMetadata.table_name,
        SchemaMetadata.column_name,
        SchemaMetadata.column_type,
        SchemaMetadata.is_primary_key,
        SchemaMetadata.is_foreign_key,
        SchemaMetadata.foreign_key_table,
        SchemaMetadata.foreign_key_column,
        SchemaMetadata.row_count
    ).where(
        SchemaMetadata.schema_snapshot_id == snapshot_id
    )

    result = await session.execute(query)
    metadata = result.all()
    
    # Sort in Python instead of SQL to avoid NULL issues
    metadata = sorted(metadata, key=lambda x: (
        x[0] or "",  # schema_name
        x[1] or "",  # table_name
        x[2] or "" if len(x) > 2 else ""  # column_name
    ))

    # Group by table to build table structure - use same logic as get_snapshot_data
    tables = {}
    for item in metadata:
        key = f"{item[0]}.{item[1]}"  # schema_name.table_name
        if key not in tables:
            # Get row count from table-level metadata (where column_name is empty)
            row_count = 0
            for meta_item in metadata:
                if (meta_item[0] == item[0] and meta_item[1] == item[1] and
                    (meta_item[2] == "" or meta_item[2] is None) and meta_item[8] is not None):
                    row_count = meta_item[8]
                    break

            tables[key] = {
                "schema_name": item[0],
                "table_name": item[1],
                "row_count": row_count,
                "columns": []
            }

        # Only add column data (skip table-level metadata)
        if item[2] and item[2] != "":
            tables[key]["columns"].append({
                "name": item[2],  # column_name
                "type": item[3],  # column_type
                "is_primary_key": item[4],  # is_primary_key
                "is_foreign_key": item[5],  # is_foreign_key
                "foreign_key_table": item[6],  # foreign_key_table
                "foreign_key_column": item[7]  # foreign_key_column
            })

    # Return tables sorted by schema and table name for consistent display
    return sorted(list(tables.values()), key=lambda t: (t["schema_name"] or "", t["table_name"]))

@router.get("/snapshots/{snapshot_id}/data")
async def get_snapshot_data(snapshot_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get full schema data for a specific snapshot"""
    # Verify snapshot exists
    result = await session.execute(select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Schema snapshot not found")

    # Get all metadata for this snapshot
    query = select(
        SchemaMetadata.schema_name,
        SchemaMetadata.table_name,
        SchemaMetadata.column_name,
        SchemaMetadata.column_type,
        SchemaMetadata.is_primary_key,
        SchemaMetadata.is_foreign_key,
        SchemaMetadata.foreign_key_table,
        SchemaMetadata.foreign_key_column,
        SchemaMetadata.row_count
    ).where(
        SchemaMetadata.schema_snapshot_id == snapshot_id
    ).order_by(
        SchemaMetadata.schema_name, SchemaMetadata.table_name, SchemaMetadata.column_order
    )

    result = await session.execute(query)
    metadata = result.all()

    # Group by table
    tables = {}
    for item in metadata:
        key = f"{item[0]}.{item[1]}"  # schema_name.table_name
        if key not in tables:
            # Get row count from table-level metadata (where column_name is empty)
            row_count = 0
            for meta_item in metadata:
                if (meta_item[0] == item[0] and meta_item[1] == item[1] and
                    (meta_item[2] == "" or meta_item[2] is None) and meta_item[8] is not None):
                    row_count = meta_item[8]
                    break

            tables[key] = {
                "schema_name": item[0],
                "table_name": item[1],
                "row_count": row_count,
                "columns": []
            }

        # Only add column data (skip table-level metadata)
        if item[2] and item[2] != "":
            tables[key]["columns"].append({
                "column_name": item[2],  # column_name
                "column_type": item[3],  # column_type
                "is_primary_key": item[4],  # is_primary_key
                "is_foreign_key": item[5],  # is_foreign_key
                "foreign_key_table": item[6],  # foreign_key_table
                "foreign_key_column": item[7]  # foreign_key_column
            })

    return {
        "snapshot": {
            "id": snapshot.id,
            "name": snapshot.name,
            "description": snapshot.description,
            "connection_id": snapshot.connection_id,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None
        },
        "schema_data": list(tables.values()),
        "total_tables": len(tables)
    }


@router.delete("/")
async def clear_schema_metadata(session: AsyncSession = Depends(get_db_session)):
    """Clear all stored schema metadata"""
    await session.execute(delete(SchemaMetadata))
    await session.commit()
    return {"message": "Schema metadata cleared successfully"}