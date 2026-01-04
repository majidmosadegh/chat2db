"""
Execute SQL Query.
Query for executing SQL queries against database connections.
"""

from dataclasses import dataclass
from typing import Optional
from ...domain.value_objects.sql_query import SQLQuery


@dataclass
class ExecuteSQLQuery:
    """Query to execute SQL against a database connection."""

    connection_id: str
    sql_query: SQLQuery
    limit: Optional[int] = 1000
    include_metadata: bool = True

    # Query metadata
    query_id: str = None

    def __post_init__(self):
        """Initialize query metadata."""
        if self.query_id is None:
            import uuid
            self.query_id = str(uuid.uuid4())

        # Validate query
        self._validate()

    def _validate(self) -> None:
        """Validate query data."""
        if not self.connection_id:
            raise ValueError("Connection ID is required")

        if not isinstance(self.sql_query, SQLQuery):
            raise ValueError("SQL query must be a valid SQLQuery object")

        if self.limit is not None and self.limit <= 0:
            raise ValueError("Limit must be positive if specified")

        if self.limit is not None and self.limit > 10000:
            raise ValueError("Limit cannot exceed 10,000 rows")

    @classmethod
    def create(cls, connection_id: str, sql: str, limit: Optional[int] = 1000) -> 'ExecuteSQLQuery':
        """Factory method to create a query from SQL string."""
        sql_query = SQLQuery(sql)
        return cls(
            connection_id=connection_id,
            sql_query=sql_query,
            limit=limit
        )

    def should_apply_limit(self) -> bool:
        """Check if limit should be applied to the query."""
        return self.limit is not None and not self.sql_query.has_limit

    def get_effective_limit(self) -> int:
        """Get the effective limit to apply."""
        if self.sql_query.has_limit:
            return self.limit or 1000
        return self.limit or 1000









