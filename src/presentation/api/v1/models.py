"""
API Models - Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class APIResponse(BaseModel):
    """Generic API response wrapper."""
    success: bool
    data: Any = None
    message: str = ""
    errors: Optional[List[str]] = None


class GenerateAIDictionaryRequest(BaseModel):
    """Request model for AI dictionary generation."""
    snapshot_id: str
    business_domain: str
    database_description: str
    target_user: str
    language: str = "persian"
    notes: Optional[str] = None


class GenerateAIDictionaryResponse(BaseModel):
    """Response model for AI dictionary generation."""
    job_id: str
    status: str
    message: str
    command_id: str


class ExecuteSQLRequest(BaseModel):
    """Request model for SQL execution."""
    connection_id: str
    sql: str
    limit: Optional[int] = 1000


class ExecuteSQLResponse(BaseModel):
    """Response model for SQL execution."""
    results: List[Dict[str, Any]]
    execution_time: float
    row_count: int









