"""
Security utilities for database operations.
Handles SQL validation and password decryption.
"""

import re
from cryptography.fernet import Fernet
import os

# Forbidden SQL keywords - only SELECT queries allowed
FORBIDDEN_KEYWORDS = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bREPLACE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
]

# Dangerous system functions for untrusted / chat SQL
DANGEROUS_FUNCTIONS = [
    r"\bxp_",
    r"\bsp_",
    r"\bsys\.",
    r"\binformation_schema\.",
]

# Connector introspection may read information_schema / INFORMATION_SCHEMA.
CONNECTOR_DANGEROUS_FUNCTIONS = [
    r"\bxp_",
    r"\bsp_oa",
    r"\bsp_configure\b",
]


class SQLSecurityError(ValueError):
    """Raised when SQL query fails security validation"""
    pass


def _require_single_read_query(sql: str) -> str:
    if not sql or not sql.strip():
        raise SQLSecurityError("SQL query cannot be empty")

    upper_sql = sql.upper()
    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, upper_sql):
            keyword = pattern.replace(r"\b", "")
            raise SQLSecurityError(f"Forbidden SQL keyword detected: {keyword}")

    stripped = upper_sql.strip()
    if not (stripped.startswith("SELECT ") or stripped.startswith("WITH ")):
        raise SQLSecurityError("Only SELECT and WITH queries are allowed")

    if sql.count(";") > 1:
        raise SQLSecurityError("Multiple SQL statements not allowed")

    return upper_sql


def validate_sql(sql: str) -> None:
    """
    Validate SQL query for security (chat / untrusted path).
    Only allows SELECT queries and blocks dangerous operations,
    including information_schema access.
    """
    _require_single_read_query(sql)
    for pattern in DANGEROUS_FUNCTIONS:
        if re.search(pattern, sql, flags=re.IGNORECASE):
            raise SQLSecurityError(f"Dangerous system function detected: {pattern}")


def validate_read_only_sql(sql: str) -> None:
    """
    Validate SQL for application connectors that need metadata introspection.

    Blocks destructive statements and high-risk procedures, but allows
    information_schema / INFORMATION_SCHEMA reads used for schema discovery.
    """
    _require_single_read_query(sql)
    for pattern in CONNECTOR_DANGEROUS_FUNCTIONS:
        if re.search(pattern, sql, flags=re.IGNORECASE):
            raise SQLSecurityError(f"Dangerous system function detected: {pattern}")

    lowered = sql.lower()
    if "into outfile" in lowered or "load_file" in lowered:
        raise SQLSecurityError("File operations are not allowed")


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt a password using the deployment's configured Fernet key.

    The key must match the key used when the value was encrypted. If the key
    is missing or decryption fails, fail closed instead of returning a
    hard-coded credential.
    """
    if not encrypted_password:
        return ""

    key = os.getenv("CHAT2DB_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "CHAT2DB_ENCRYPTION_KEY is required to decrypt stored credentials."
        )

    try:
        return Fernet(key.encode()).decrypt(encrypted_password.encode()).decode()
    except Exception as exc:
        raise ValueError(
            "Unable to decrypt the stored password. Verify CHAT2DB_ENCRYPTION_KEY "
            "and re-enter the credential if the original key is unavailable."
        ) from exc
