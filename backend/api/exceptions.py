"""
Custom exceptions for the SQL-PT API
"""

from fastapi import HTTPException
from typing import Optional, Dict, Any


class SQLPTException(Exception):
    """Base exception for SQL-PT application"""

    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class DatabaseConnectionError(SQLPTException):
    """Exception raised when database connection fails"""

    def __init__(self, message: str, db_type: str = None, host: str = None):
        super().__init__(
            message=f"Database connection failed: {message}",
            status_code=503,
            details={"db_type": db_type, "host": host}
        )


class LLMConnectionError(SQLPTException):
    """Exception raised when LLM service connection fails"""

    def __init__(self, message: str, provider: str = None, base_url: str = None):
        super().__init__(
            message=f"LLM service connection failed: {message}",
            status_code=503,
            details={"provider": provider, "base_url": base_url}
        )


class ValidationError(SQLPTException):
    """Exception raised when input validation fails"""

    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(
            message=f"Validation error: {message}",
            status_code=400,
            details={"field": field, "value": value}
        )


class ResourceNotFoundError(SQLPTException):
    """Exception raised when a requested resource is not found"""

    def __init__(self, message: str, resource_type: str = None, resource_id: Any = None):
        super().__init__(
            message=f"Resource not found: {message}",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class DuplicateResourceError(SQLPTException):
    """Exception raised when trying to create a duplicate resource"""

    def __init__(self, message: str, resource_type: str = None, field: str = None, value: Any = None):
        super().__init__(
            message=f"Duplicate resource: {message}",
            status_code=409,
            details={"resource_type": resource_type, "field": field, "value": value}
        )


class AuthenticationError(SQLPTException):
    """Exception raised when authentication fails"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, status_code=401)


class AuthorizationError(SQLPTException):
    """Exception raised when authorization fails"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, status_code=403)


class ConfigurationError(SQLPTException):
    """Exception raised when configuration is invalid"""

    def __init__(self, message: str, config_key: str = None):
        super().__init__(
            message=f"Configuration error: {message}",
            status_code=500,
            details={"config_key": config_key}
        )


# Global exception handler for FastAPI
def create_http_exception_from_sqlpt_exception(exc: SQLPTException) -> HTTPException:
    """Convert SQLPTException to FastAPI HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "message": exc.message,
            "error_type": exc.__class__.__name__,
            "details": exc.details
        }
    )















