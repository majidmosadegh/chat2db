import re
from typing import Optional


class SQLValidationError(Exception):
    """Exception raised when SQL validation fails"""
    pass


class SQLGuard:
    """Validates SQL queries for safety"""

    # Dangerous keywords that are not allowed
    DANGEROUS_KEYWORDS = {
        'insert', 'update', 'delete', 'drop', 'create', 'alter', 'truncate',
        'merge', 'replace', 'upsert', 'execute', 'exec', 'call', 'begin',
        'commit', 'rollback', 'savepoint', 'grant', 'revoke', 'lock', 'unlock'
    }

    # Allowed SELECT-related keywords
    ALLOWED_KEYWORDS = {
        'select', 'from', 'where', 'join', 'inner', 'left', 'right', 'full',
        'outer', 'on', 'group', 'by', 'having', 'order', 'asc', 'desc',
        'limit', 'top', 'distinct', 'as', 'union', 'all', 'with', 'cte',
        'case', 'when', 'then', 'else', 'end', 'and', 'or', 'not', 'in',
        'exists', 'between', 'like', 'is', 'null', 'count', 'sum', 'avg',
        'min', 'max', 'cast', 'convert', 'coalesce', 'ifnull'
    }

    def validate_sql(self, sql: str) -> str:
        """
        Validate SQL query for safety

        Args:
            sql: The SQL query to validate

        Returns:
            str: The cleaned SQL query

        Raises:
            SQLValidationError: If validation fails
        """
        if not sql or not sql.strip():
            raise SQLValidationError("SQL query is empty")

        # Clean the SQL
        cleaned_sql = self._clean_sql(sql)

        # Validate structure
        self._validate_structure(cleaned_sql)

        # Check for dangerous operations
        self._check_dangerous_operations(cleaned_sql)

        return cleaned_sql

    def _clean_sql(self, sql: str) -> str:
        """Clean and normalize the SQL query"""
        # Remove leading/trailing whitespace
        sql = sql.strip()

        # Remove any markdown code blocks
        sql = re.sub(r'```\w*\n?', '', sql)
        sql = re.sub(r'```', '', sql)

        # Remove comments
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        # Normalize whitespace
        sql = re.sub(r'\s+', ' ', sql)

        return sql.strip()

    def _validate_structure(self, sql: str) -> None:
        """Validate SQL structure"""
        sql_lower = sql.lower()

        # Must start with SELECT or WITH
        if not (sql_lower.startswith('select ') or sql_lower.startswith('with ')):
            raise SQLValidationError("SQL must start with SELECT or WITH")

        # Count semicolons - should be at most 1
        semicolon_count = sql.count(';')
        if semicolon_count > 1:
            raise SQLValidationError("Multiple SQL statements not allowed")
        elif semicolon_count == 1 and not sql.endswith(';'):
            raise SQLValidationError("Semicolon must be at the end if present")

        # Remove trailing semicolon for further checks
        sql_no_semicolon = sql.rstrip(';').strip()

        # Check for subqueries or CTEs that might hide dangerous operations
        self._validate_subqueries(sql_no_semicolon)

    def _validate_subqueries(self, sql: str) -> None:
        """Validate subqueries don't contain dangerous operations"""
        # Simple check: look for dangerous keywords in subqueries
        # This is a basic implementation - could be enhanced

        # Find all subqueries (content within parentheses that looks like SQL)
        subquery_pattern = r'\(\s*(select|with)\s+.*?\)'
        subqueries = re.findall(subquery_pattern, sql, re.IGNORECASE | re.DOTALL)

        for subquery in subqueries:
            self._check_dangerous_operations(subquery)

    def _check_dangerous_operations(self, sql: str) -> None:
        """Check for dangerous SQL operations"""
        sql_lower = sql.lower()

        # Check for dangerous keywords
        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(r'\b' + re.escape(keyword) + r'\b', sql_lower):
                raise SQLValidationError(f"Dangerous SQL keyword '{keyword}' not allowed")

        # Check for system functions that might be dangerous
        dangerous_functions = ['xp_', 'sp_', 'sys.']
        for func in dangerous_functions:
            if func in sql_lower:
                raise SQLValidationError(f"Dangerous system function '{func}' not allowed")

        # Check for file operations
        if 'load_file' in sql_lower or 'into outfile' in sql_lower:
            raise SQLValidationError("File operations not allowed")

    def is_read_only_query(self, sql: str) -> bool:
        """Check if the SQL query is read-only"""
        try:
            self.validate_sql(sql)
            return True
        except SQLValidationError:
            return False
