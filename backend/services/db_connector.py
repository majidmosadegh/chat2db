import asyncio
import asyncpg
import aiomysql
import pyodbc
from typing import List, Dict, Any, Optional
from loguru import logger

class DirectDatabaseConnector:
    """
    Direct database connector for executing queries.
    
    Note: This connector expects the password to be already decrypted.
    If you pass an encrypted password, it will try to decrypt it using the standard
    decrypt_password function, but if decryption fails, it will use the password as-is
    (assuming it's already decrypted or plain text).
    """
    def __init__(self, db_type: str, host: str, port: int, username: str, password: str, database: str):
        self.db_type = db_type.lower()
        self.host = host
        self.port = port
        self.username = username
        # Try to decrypt password if it's encrypted, otherwise use as-is
        # Most callers (like db_connector_utils.py) already pass decrypted passwords
        self.password = self._try_decrypt_password(password)
        self.database = database
        self.connection = None
    
    def _try_decrypt_password(self, password: str) -> str:
        """
        Try to decrypt password if it's encrypted, otherwise return as-is.
        
        This handles both cases:
        1. Password is already decrypted (common case)
        2. Password is encrypted (rare case - should use decrypt_password before calling)
        """
        if not password:
            return password
        
        # Try to decrypt using standard decrypt_password function
        try:
            from api.database import decrypt_password
            decrypted = decrypt_password(password)
            # Only use decrypted version if it's different (was actually encrypted)
            # This prevents re-decrypting already decrypted passwords
            if decrypted != password:
                return decrypted
            # If same, it was already plain text, use as-is
            return password
        except Exception:
            # If decryption fails, password is likely already decrypted or plain text
            # Silently use as-is (this is the expected case)
            return password

    async def connect(self):
        """Establish database connection"""
        if self.db_type == "postgresql":
            self.connection = await asyncpg.connect(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                database=self.database
            )
        elif self.db_type == "mysql":
            self.connection = await aiomysql.connect(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                db=self.database
            )
        elif self.db_type == "sqlserver":
            # SQL Server uses synchronous connection, will handle in execute_query
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.host},{self.port};"
                f"DATABASE={self.database};"
                f"UID={self.username};"
                f"PWD={self.password};"
                "TrustServerCertificate=yes;"
            )
            self.connection = pyodbc.connect(conn_str)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    async def disconnect(self):
        """Close database connection"""
        if self.connection:
            if self.db_type == "postgresql":
                await self.connection.close()
            elif self.db_type == "mysql":
                self.connection.close()
            elif self.db_type == "sqlserver":
                self.connection.close()

    async def execute_query(self, query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Execute SQL query and return results as list of dictionaries"""
        if not self.connection:
            await self.connect()

        # Add LIMIT clause if specified
        if limit and "LIMIT" not in query.upper() and "TOP" not in query.upper():
            if self.db_type == "sqlserver":
                query = query.replace("SELECT", f"SELECT TOP {limit}", 1)
            else:
                query = f"{query} LIMIT {limit}"

        results = []

        try:
            if self.db_type == "postgresql":
                rows = await self.connection.fetch(query)
                if rows:
                    columns = [desc[0] for desc in self.connection.get_cursor().description]
                    for row in rows:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            value = row[i]
                            # Convert to JSON-serializable types
                            if value is None:
                                row_dict[col] = None
                            else:
                                row_dict[col] = str(value)
                        results.append(row_dict)

            elif self.db_type == "mysql":
                async with self.connection.cursor() as cursor:
                    await cursor.execute(query)
                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                        rows = await cursor.fetchall()
                        for row in rows:
                            row_dict = {}
                            for i, col in enumerate(columns):
                                value = row[i]
                                # Convert to JSON-serializable types
                                if value is None:
                                    row_dict[col] = None
                                else:
                                    row_dict[col] = str(value)
                            results.append(row_dict)

            elif self.db_type == "sqlserver":
                # SQL Server is synchronous, run in thread
                def execute_sqlserver():
                    cursor = self.connection.execute(query)
                    if cursor.description:
                        columns = [column[0] for column in cursor.description]
                        rows = cursor.fetchall()
                        return columns, rows
                    return [], []

                columns, rows = await asyncio.to_thread(execute_sqlserver)

                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Convert to JSON-serializable types
                        if value is None:
                            row_dict[col] = None
                        elif isinstance(value, str):
                            # Handle string encoding - assume it's already properly encoded
                            row_dict[col] = value
                        elif isinstance(value, bytes):
                            # If it's bytes, decode it
                            try:
                                row_dict[col] = value.decode('utf-8')
                            except UnicodeDecodeError:
                                try:
                                    row_dict[col] = value.decode('windows-1256')
                                except UnicodeDecodeError:
                                    row_dict[col] = value.decode('utf-8', errors='replace')
                        else:
                            row_dict[col] = str(value)
                    results.append(row_dict)

        except Exception as e:
            # Clean up connection on error
            await self.disconnect()
            raise e

        return results

    async def sample_rows(self, table: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get sample rows from a table
        
        Args:
            table: Table name (can include schema, e.g., 'schema.table' or 'table')
            limit: Number of rows to sample (default: 3)
        
        Returns:
            List of dictionaries representing rows
        """
        if not self.connection:
            await self.connect()
        
        # Handle schema.table format
        if '.' in table:
            schema_name, table_name = table.split('.', 1)
            if self.db_type == "postgresql":
                query = f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT {limit}'
            elif self.db_type == "mysql":
                query = f'SELECT * FROM `{schema_name}`.`{table_name}` LIMIT {limit}'
            elif self.db_type == "sqlserver":
                query = f'SELECT TOP {limit} * FROM [{schema_name}].[{table_name}]'
            else:
                query = f'SELECT * FROM {table} LIMIT {limit}'
        else:
            if self.db_type == "postgresql":
                query = f'SELECT * FROM "{table}" LIMIT {limit}'
            elif self.db_type == "mysql":
                query = f'SELECT * FROM `{table}` LIMIT {limit}'
            elif self.db_type == "sqlserver":
                query = f'SELECT TOP {limit} * FROM [{table}]'
            else:
                query = f'SELECT * FROM {table} LIMIT {limit}'
        
        return await self.execute_query(query)

    async def get_minified_schema(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get minified schema for all tables in the database
        
        Returns:
            Dictionary mapping table names to lists of column info
            Format: {
                "table_name": [
                    {"column": "col1", "type": "varchar"},
                    {"column": "col2", "type": "int"}
                ]
            }
        """
        if not self.connection:
            await self.connect()
        
        schema = {}
        
        try:
            if self.db_type == "postgresql":
                query = """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
                """
            elif self.db_type == "mysql":
                query = """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                ORDER BY table_name, ordinal_position
                """
            elif self.db_type == "sqlserver":
                query = """
                SELECT 
                    t.TABLE_NAME as table_name,
                    c.COLUMN_NAME as column_name,
                    c.DATA_TYPE as data_type
                FROM INFORMATION_SCHEMA.TABLES t
                INNER JOIN INFORMATION_SCHEMA.COLUMNS c 
                    ON t.TABLE_NAME = c.TABLE_NAME
                WHERE t.TABLE_TYPE = 'BASE TABLE'
                    AND t.TABLE_SCHEMA = 'dbo'
                ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
                """
            else:
                # Fallback for other databases
                return schema
            
            results = await self.execute_query(query)
            
            for row in results:
                table_name = row.get("table_name", "")
                column_name = row.get("column_name", "")
                data_type = row.get("data_type", "")
                
                if table_name and column_name:
                    if table_name not in schema:
                        schema[table_name] = []
                    schema[table_name].append({
                        "column": column_name,
                        "type": data_type
                    })
        
        except Exception as e:
            print(f"Error getting minified schema: {e}")
            # Return empty schema on error
            return {}
        
        return schema

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
