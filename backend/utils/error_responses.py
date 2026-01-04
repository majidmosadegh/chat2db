"""
Error response utilities for consistent API error handling
"""

from typing import Dict, Any, Optional
from fastapi import HTTPException
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    code: Optional[str] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response with field details"""
    error: str
    message: str
    fields: Dict[str, str]
    code: Optional[str] = None


def create_error_response(
    status_code: int,
    error: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    code: Optional[str] = None
) -> ErrorResponse:
    """Create a standardized error response"""
    return ErrorResponse(
        error=error,
        message=message,
        details=details,
        code=code
    )


def create_validation_error_response(
    message: str,
    fields: Dict[str, str],
    code: Optional[str] = "VALIDATION_ERROR"
) -> ValidationErrorResponse:
    """Create a validation error response with field-specific errors"""
    return ValidationErrorResponse(
        error="Validation Error",
        message=message,
        fields=fields,
        code=code
    )


def handle_database_error(error: Exception) -> ErrorResponse:
    """Handle database-related errors"""
    return create_error_response(
        status_code=500,
        error="Database Error",
        message="A database error occurred",
        details={"original_error": str(error)},
        code="DATABASE_ERROR"
    )


def handle_validation_error(error: Exception, field_errors: Optional[Dict[str, str]] = None) -> ValidationErrorResponse:
    """Handle validation errors"""
    if field_errors:
        return create_validation_error_response(
            message=str(error),
            fields=field_errors
        )

    return create_validation_error_response(
        message=str(error),
        fields={}
    )


def handle_not_found_error(resource: str, resource_id: Optional[str] = None) -> ErrorResponse:
    """Handle not found errors"""
    message = f"{resource} not found"
    if resource_id:
        message += f" with ID: {resource_id}"

    return create_error_response(
        status_code=404,
        error="Not Found",
        message=message,
        code="NOT_FOUND"
    )


def handle_unauthorized_error(message: str = "Unauthorized access") -> ErrorResponse:
    """Handle unauthorized access errors"""
    return create_error_response(
        status_code=401,
        error="Unauthorized",
        message=message,
        code="UNAUTHORIZED"
    )


def handle_forbidden_error(message: str = "Insufficient permissions") -> ErrorResponse:
    """Handle forbidden access errors"""
    return create_error_response(
        status_code=403,
        error="Forbidden",
        message=message,
        code="FORBIDDEN"
    )


def handle_internal_error(error: Exception, details: Optional[Dict[str, Any]] = None) -> ErrorResponse:
    """Handle internal server errors"""
    error_details = {
        "original_error": str(error),
        "error_type": type(error).__name__
    }

    if details:
        error_details.update(details)

    return create_error_response(
        status_code=500,
        error="Internal Server Error",
        message="An unexpected error occurred",
        details=error_details,
        code="INTERNAL_ERROR"
    )


def handle_external_api_error(service: str, error: Exception) -> ErrorResponse:
    """Handle errors from external API calls"""
    return create_error_response(
        status_code=502,
        error="External Service Error",
        message=f"Error communicating with {service}",
        details={
            "service": service,
            "original_error": str(error)
        },
        code="EXTERNAL_API_ERROR"
    )


def handle_rate_limit_error(retry_after: Optional[int] = None) -> ErrorResponse:
    """Handle rate limiting errors"""
    details = {}
    if retry_after:
        details["retry_after_seconds"] = retry_after

    return create_error_response(
        status_code=429,
        error="Rate Limit Exceeded",
        message="Too many requests. Please try again later.",
        details=details,
        code="RATE_LIMIT_EXCEEDED"
    )


def handle_ai_service_error(service: str, error: Exception) -> ErrorResponse:
    """Handle AI service specific errors"""
    return create_error_response(
        status_code=503,
        error="AI Service Unavailable",
        message=f"The {service} service is currently unavailable",
        details={
            "service": service,
            "original_error": str(error)
        },
        code="AI_SERVICE_ERROR"
    )


# Common error codes for reference
ERROR_CODES = {
    "VALIDATION_ERROR": "VALIDATION_ERROR",
    "DATABASE_ERROR": "DATABASE_ERROR",
    "NOT_FOUND": "NOT_FOUND",
    "UNAUTHORIZED": "UNAUTHORIZED",
    "FORBIDDEN": "FORBIDDEN",
    "INTERNAL_ERROR": "INTERNAL_ERROR",
    "EXTERNAL_API_ERROR": "EXTERNAL_API_ERROR",
    "RATE_LIMIT_EXCEEDED": "RATE_LIMIT_EXCEEDED",
    "AI_SERVICE_ERROR": "AI_SERVICE_ERROR",
    "NETWORK_ERROR": "NETWORK_ERROR",
    "TIMEOUT_ERROR": "TIMEOUT_ERROR"
}