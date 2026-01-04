from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from typing import List, Dict, Any, Optional
import asyncio
from contextlib import asynccontextmanager

from db import DatabaseConnector


class SQLExecutionError(Exception):
    """Exception raised when SQL execution fails"""
    pass


class SQLExecutor:
    """Executes SQL queries using the new DatabaseConnector"""

    def __init__(self, connector: DatabaseConnector):
        self.connector = connector

    async def execute_query(
        self,
        sql: str,
        max_rows: int = 50
    ) -> Dict[str, Any]:
        """
        Execute SQL query using the database connector

        Args:
            sql: The SQL query to execute
            max_rows: Maximum number of rows to return

        Returns:
            Dict containing execution results

        Raises:
            SQLExecutionError: If execution fails
        """
        try:
            # Execute the query using the connector
            rows = await self.connector.execute_readonly(sql, limit=max_rows)

            return {
                "rows": rows,
                "row_count": len(rows),
                "execution_status": "success",
                "truncated": len(rows) >= max_rows  # Assume truncated if we hit the limit
            }

        except Exception as e:
            error_msg = str(e)
            # Clean up error message for security
            if "password" in error_msg.lower():
                error_msg = "Database connection error"

            raise SQLExecutionError(f"Query execution failed: {error_msg}")

    async def test_connection(self) -> bool:
        """Test if the database connection works"""
        try:
            return await self.connector.test_connection()
        except:
            return False
