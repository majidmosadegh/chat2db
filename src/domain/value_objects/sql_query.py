"""
SQL Query Value Object.
Immutable object representing a validated SQL query.
"""

import re
from dataclasses import dataclass
from typing import List, Set


@dataclass(frozen=True)
class SQLQuery:
    """Value object representing a validated SQL query."""

    query: str
    is_select_only: bool = False
    has_limit: bool = False
    tables_referenced: Set[str] = frozenset()
    estimated_complexity: str = "simple"  # simple, medium, complex

    def __post_init__(self):
        """Validate SQL query after initialization."""
        if not self.query or not self.query.strip():
            raise ValueError("SQL query cannot be empty")

        # Normalize query
        normalized_query = self._normalize_query(self.query)

        # Validate and analyze query
        self._validate_query(normalized_query)

        # Analyze query characteristics
        analysis = self._analyze_query(normalized_query)

        # Set computed attributes
        object.__setattr__(self, 'is_select_only', analysis['is_select_only'])
        object.__setattr__(self, 'has_limit', analysis['has_limit'])
        object.__setattr__(self, 'tables_referenced', frozenset(analysis['tables']))
        object.__setattr__(self, 'estimated_complexity', analysis['complexity'])

    def _normalize_query(self, query: str) -> str:
        """Normalize SQL query for analysis."""
        # Remove extra whitespace and normalize case
        normalized = re.sub(r'\s+', ' ', query.strip().upper())
        return normalized

    def _validate_query(self, query: str) -> None:
        """Validate SQL query against business rules."""
        # Check for dangerous operations
        dangerous_patterns = [
            r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE)\b',
            r'\b(EXEC|EXECUTE|SP_|XP_)\b',  # SQL Server procedures
            r'--|/\*|\*/',  # Comments that might hide malicious code
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                raise ValueError(f"Query contains potentially dangerous operation: {pattern}")

        # Check query length
        if len(query) > 10000:
            raise ValueError("Query is too long (max 10000 characters)")

    def _analyze_query(self, query: str) -> dict:
        """Analyze query characteristics."""
        analysis = {
            'is_select_only': False,
            'has_limit': False,
            'tables': set(),
            'complexity': 'simple'
        }

        # Check if SELECT only
        analysis['is_select_only'] = query.strip().startswith('SELECT') and not re.search(
            r'\b(INTO|UPDATE|DELETE|INSERT)\b', query
        )

        # Check for LIMIT/TOP
        analysis['has_limit'] = bool(re.search(r'\b(LIMIT|TOP)\b', query))

        # Extract table names (simplified)
        # This is a basic implementation - real implementation would use proper SQL parsing
        table_pattern = r'\bFROM\s+(\w+)(?:\s+AS\s+\w+)?'
        matches = re.findall(table_pattern, query, re.IGNORECASE)
        analysis['tables'].update(matches)

        # Estimate complexity
        complexity_score = 0
        if re.search(r'\b(JOIN|UNION|GROUP BY|HAVING|ORDER BY)\b', query):
            complexity_score += 1
        if re.search(r'\b(WHERE|AND|OR)\b', query):
            complexity_score += 1
        if len(query) > 500:
            complexity_score += 1
        if len(analysis['tables']) > 3:
            complexity_score += 1

        if complexity_score >= 3:
            analysis['complexity'] = 'complex'
        elif complexity_score >= 2:
            analysis['complexity'] = 'medium'

        return analysis

    def with_limit(self, limit: int) -> 'SQLQuery':
        """Create a new SQLQuery with LIMIT clause."""
        if self.has_limit:
            raise ValueError("Query already has a LIMIT clause")

        if not self.is_select_only:
            raise ValueError("Can only add LIMIT to SELECT queries")

        if self.query.upper().startswith('SELECT'):
            # Add LIMIT for different database types
            new_query = f"{self.query} LIMIT {limit}"
            return SQLQuery(new_query)

        raise ValueError("Cannot add LIMIT to non-SELECT queries")

    def is_safe_for_execution(self) -> bool:
        """Check if query is safe for execution."""
        return self.is_select_only and len(self.query) < 5000

    def get_execution_timeout(self) -> int:
        """Get recommended execution timeout in seconds."""
        timeouts = {
            'simple': 30,
            'medium': 120,
            'complex': 300
        }
        return timeouts.get(self.estimated_complexity, 60)









