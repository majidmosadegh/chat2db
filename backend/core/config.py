"""
Core Configuration and Constants
Centralized configuration for the Dictionary Generation module
"""

# Dictionary Generation Constants
DEFAULT_ROW_SAMPLE_LIMIT = 5
MAX_CONCURRENT_JOBS = 3
MAX_RETRIES = 2
MAX_COLUMNS_PER_TABLE = 120  # Internal limit to prevent unlimited column generation (increased from 100)
MAX_TABLES_PER_JOB = 1000  # Internal limit to prevent unlimited table generation
MAX_TABLES_PER_RESPONSE = 5  # Max tables per single LLM response batch
MAX_JSON_OUTPUT_CHARS = 8000  # Max characters in JSON output to prevent token cut-offs (increased from 3500)

# Job Status Timeouts (in seconds)
STUCK_TASK_TIMEOUT = 300  # 5 minutes
JOB_COMPLETION_TIMEOUT = 600  # 10 minutes

# LLM Generation Settings
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 8000  # Increased to reduce token cut-offs (was 4000, originally 2000)
LLM_TIMEOUT_SECONDS = 1200  # 20 minutes

# JSON Safety Settings
MAX_JSON_REPAIR_ATTEMPTS = 3
MAX_ERROR_MESSAGE_LENGTH = 1000  # Database column limit

# Database Type Mappings
DB_TYPE_MAP = {
    "sqlserver": "SQL Server",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "oracle": "Oracle"
}

# Language Mappings
LANGUAGE_MAP = {
    "persian": "Persian (Farsi)",
    "farsi": "Persian (Farsi)",
    "english": "English",
    "en": "English"
}

# Scope Mappings
SCOPE_MAP = {
    "full_snapshot": "FULL_SNAPSHOT",
    "table": "SINGLE_TABLE",
    "column": "SINGLE_COLUMN",
    "multi_table": "FULL_SNAPSHOT"
}

# Logging Settings
LOG_ENCODING = "utf-8"
LOG_ERROR_HANDLING = "replace"  # For Windows encoding safety
MAX_LOG_MESSAGE_LENGTH = 200  # Truncate long log messages

