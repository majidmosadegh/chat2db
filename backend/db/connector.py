"""
Database connector - the core of database operations.
Handles connection management and query execution.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
try:
    import pymssql
except ImportError:
    pymssql = None
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from .engine_factory import create_engine_from_connection
from .security import decrypt_password, validate_sql, SQLSecurityError
from .models import Snapshot, DatabaseConnection


class DatabaseConnector:
    """
    Core database connector for executing queries against snapshots.
    Manages connection lifecycle and ensures readonly operations.
    """

    def __init__(self, snapshot: Snapshot, db_conn: DatabaseConnection):
        self.snapshot = snapshot
        self.db_conn = db_conn
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[sessionmaker] = None
        self._connected = False

    async def connect(self) -> None:
        """
        Establish connection to the database.
        Called automatically when needed, but can be called explicitly.
        """
        if self._connected:
            return

        try:
            password = decrypt_password(self.db_conn.encrypted_password)

            self.engine = create_engine_from_connection(
                self.db_conn, password
            )

            self.session_factory = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            self._connected = True

        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}")

    async def disconnect(self) -> None:
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            self._connected = False

    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """
        Get a database session.
        Ensures connection is established before returning session.
        """
        if not self._connected:
            await self.connect()

        if not self.session_factory:
            raise ConnectionError("Session factory not initialized")

        async with self.session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    async def execute_readonly(
        self,
        sql: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Execute a readonly SQL query with security validation and comprehensive logging.

        Args:
            sql: SQL query to execute
            limit: Maximum number of rows to return

        Returns:
            List of dictionaries containing query results

        Raises:
            SQLSecurityError: If query fails security validation
            ConnectionError: If database connection fails
        """
        import logging
        logger = logging.getLogger(__name__)
        query_id = f"DBQ_{int(time.time()*1000)}_{hash(sql) % 10000:04d}"

        logger.info(f"🔌 DB_CONNECTOR_START | ID: {query_id} | DB_Type: {self.db_conn.db_type} | Limit: {limit} | SQL_Length: {len(sql)}")
        logger.debug(f"📝 DB_RAW_SQL | ID: {query_id} | SQL: {sql}")

        start_time = time.time()

        # Validate SQL security
        logger.debug(f"🛡️ DB_SECURITY_CHECK | ID: {query_id} | Validating SQL security...")
        validate_sql(sql)
        logger.debug(f"✅ DB_SECURITY_PASSED | ID: {query_id} | SQL security validation passed")

        # Apply limit if specified and not already present
        original_sql = sql
        if limit and "limit" not in sql.lower() and "top" not in sql.lower():
            if self.db_conn.db_type.lower() == "sqlserver":
                # For SQL Server, wrap in subquery with TOP
                sql = f"SELECT TOP {limit} * FROM ({sql}) AS limited_query"
                logger.debug(f"🔄 DB_LIMIT_APPLIED | ID: {query_id} | Applied TOP {limit} to SQL Server query")
            else:
                sql = f"{sql.rstrip(';')} LIMIT {limit}"
                logger.debug(f"🔄 DB_LIMIT_APPLIED | ID: {query_id} | Applied LIMIT {limit} to query")

        if sql != original_sql:
            logger.debug(f"📝 DB_MODIFIED_SQL | ID: {query_id} | Original: '{original_sql[:50]}...' | Modified: '{sql[:50]}...'")

        # Execute based on database type
        if self.db_conn.db_type.lower() == "sqlserver":
            logger.info(f"🗄️ DB_EXECUTE_SQLSERVER | ID: {query_id} | Using direct pymssql connection to {self.db_conn.host}:{self.db_conn.port}")
            result_rows = await self._execute_sqlserver_direct(sql)
        else:
            logger.info(f"🗄️ DB_EXECUTE_SQLALCHEMY | ID: {query_id} | Using SQLAlchemy session")
            async with self.get_session() as session:
                try:
                    logger.debug(f"⚡ DB_SESSION_EXECUTE | ID: {query_id} | Executing query...")
                    result = await session.execute(text(sql))
                    rows = result.mappings().all()

                    # Convert to list of dicts for JSON serialization
                    result_rows = [dict(row) for row in rows]
                    logger.debug(f"📊 DB_ROWS_FETCHED | ID: {query_id} | Raw rows: {len(rows)} | Converted: {len(result_rows)}")

                except Exception as e:
                    logger.error(f"❌ DB_SQLALCHEMY_ERROR | ID: {query_id} | Error: {str(e)} | SQL: '{sql[:50]}...'", exc_info=True)
                    raise ConnectionError(f"Query execution failed: {e}")

        total_time = int((time.time() - start_time) * 1000)
        logger.info(f"✅ DB_QUERY_SUCCESS | ID: {query_id} | Rows: {len(result_rows)} | TotalTime: {total_time}ms | DB_Type: {self.db_conn.db_type}")

        if result_rows:
            logger.debug(f"📋 DB_FIRST_ROW | ID: {query_id} | Sample: {result_rows[0] if result_rows else 'None'}")
            logger.debug(f"🏷️ DB_COLUMNS | ID: {query_id} | Columns: {list(result_rows[0].keys()) if result_rows else 'None'}")

        return result_rows

    async def _execute_sqlserver_direct(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL Server query using pymssql directly with comprehensive logging"""
        import logging
        logger = logging.getLogger(__name__)
        query_id = f"DBQ_{int(time.time()*1000)}_{hash(sql) % 10000:04d}"  # Define query_id here

        def _sync_execute():
            conn_id = f"CONN_{int(time.time()*1000)}"
            try:
                logger.debug(f"🔓 DB_DECRYPT_PASSWORD | ID: {conn_id} | Decrypting database password...")
                password = decrypt_password(self.db_conn.encrypted_password)

                # Connect using pymssql
                if pymssql is None:
                    raise Exception("pymssql module not available. Please install pymssql to connect to SQL Server databases.")
                logger.info(f"🔌 DB_SQLSERVER_CONNECT | ID: {conn_id} | Connecting to {self.db_conn.host}:{self.db_conn.port} as {self.db_conn.username} database: {self.db_conn.database_name}")
                connect_start = time.time()
                conn = pymssql.connect(
                    host=self.db_conn.host,
                    port=self.db_conn.port,
                    user=self.db_conn.username,
                    password=password,
                    database=self.db_conn.database_name
                )
                connect_time = int((time.time() - connect_start) * 1000)
                logger.debug(f"✅ DB_SQLSERVER_CONNECTED | ID: {conn_id} | Connection established in {connect_time}ms")

                # Execute query
                logger.debug(f"⚡ DB_SQLSERVER_EXECUTE | ID: {conn_id} | Executing query...")
                execute_start = time.time()
                cursor = conn.cursor(as_dict=True)
                cursor.execute(sql)

                # Fetch results
                logger.debug(f"📥 DB_SQLSERVER_FETCH | ID: {conn_id} | Fetching results...")
                rows = cursor.fetchall()
                fetch_time = int((time.time() - execute_start) * 1000)

                logger.debug(f"📊 DB_SQLSERVER_RESULTS | ID: {conn_id} | Fetched {len(rows)} rows in {fetch_time}ms")

                cursor.close()
                conn.close()
                logger.debug(f"🔌 DB_SQLSERVER_DISCONNECTED | ID: {conn_id} | Connection closed")

                return rows

            except Exception as e:
                logger.error(f"❌ DB_SQLSERVER_ERROR | ID: {conn_id} | Error: {str(e)} | SQL: '{sql[:50]}...'", exc_info=True)
                raise ConnectionError(f"SQL Server query failed: {e}")

        # Run in thread pool to avoid blocking
        logger.debug(f"🔄 DB_THREAD_EXECUTE | ID: {query_id} | Running SQL Server query in thread pool...")
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            thread_start = time.time()
            result = await loop.run_in_executor(executor, _sync_execute)
            thread_time = int((time.time() - thread_start) * 1000)

            logger.debug(f"✅ DB_THREAD_COMPLETE | ID: {query_id} | Thread execution completed in {thread_time}ms | Raw results: {len(result) if result else 0}")

            # Convert to consistent format
            converted_result = [dict(row) for row in (result or [])]
            logger.debug(f"🔄 DB_FORMAT_CONVERT | ID: {query_id} | Converted to dict format: {len(converted_result)} rows")

            return converted_result

    async def test_connection(self) -> bool:
        """
        Test database connection with a simple query.

        Returns:
            bool: True if connection works, False otherwise
        """
        try:
            # For SQL Server, test with pymssql directly
            if self.db_conn.db_type.lower() == "sqlserver":
                if pymssql is None:
                    raise Exception("pymssql module not available. Please install pymssql to connect to SQL Server databases.")
                def _sync_test():
                    password = decrypt_password(self.db_conn.encrypted_password)
                    conn = pymssql.connect(
                        host=self.db_conn.host,
                        port=self.db_conn.port,
                        user=self.db_conn.username,
                        password=password,
                        database=self.db_conn.database_name
                    )
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.close()
                    conn.close()
                    return True

                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    return await loop.run_in_executor(executor, _sync_test)

            # For other databases, use SQLAlchemy
            result = await self.execute_readonly("SELECT 1 as test", limit=1)
            return len(result) > 0
        except Exception:
            return False

    async def get_table_info(self) -> List[Dict[str, Any]]:
        """
        Get information about available tables in the database.

        Returns:
            List of table information
        """
        if self.db_conn.db_type.lower() == "sqlserver":
            sql = """
            SELECT TOP 100 TABLE_SCHEMA as schema_name, TABLE_NAME as table_name
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
        else:
            sql = """
            SELECT table_schema as schema_name, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
            LIMIT 100
            """

        return await self.execute_readonly(sql, limit=None)  # Don't double-limit
