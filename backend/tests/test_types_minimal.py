from typing import Dict, Optional, Literal
from pydantic import BaseModel

class TableGenerationResult(BaseModel):
    """Strict result contract for table generation"""
    status: Literal["SUCCESS", "FAILED"]
    table_description: Optional[str] = None
    column_descriptions: Dict[str, str] = {}
    error_reason: Optional[str] = None
    attempts_used: int = 0

class JobState:
    """Job-level states"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TableState:
    """Table-level states"""
    PENDING = "PENDING"
    PROMPT_CREATED = "PROMPT_CREATED"
    LLM_CALLED = "LLM_CALLED"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    PARSED_OK = "PARSED_OK"
    STORED = "STORED"
    FAILED_TERMINAL = "FAILED_TERMINAL"
