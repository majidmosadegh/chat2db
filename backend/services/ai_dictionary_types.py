"""
AI Dictionary Generation Types and Contracts
"""
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


class ProgressData(BaseModel):
    """Structure for persistent progress tracking"""
    tables: Dict[str, Dict] = {}  # table_name -> table progress data

    class Config:
        json_encoders = {
            Dict: lambda v: v
        }


class TableProgress(BaseModel):
    """Individual table progress tracking"""
    status: str
    attempts: int = 0
    error: Optional[str] = None
    last_attempt_at: Optional[str] = None
    current_attempt: Optional[int] = None


class AIGenerationConfig:
    """Configuration constants"""
    MAX_ATTEMPTS_PER_TABLE = 2
    LLM_TIMEOUT_SECONDS = 120.0
    MAX_TOKENS = 8000  # Increased to reduce token cut-offs (was 2000)
    TEMPERATURE = 0.1  # Low temperature for deterministic output


class StateMachine:
    """Deterministic state machine for job and table states"""

    @staticmethod
    def is_valid_job_state_transition(from_state: str, to_state: str) -> bool:
        """Validate job state transitions"""
        valid_transitions = {
            JobState.PENDING: [JobState.PROCESSING],
            JobState.PROCESSING: [JobState.COMPLETED, JobState.FAILED],
            JobState.COMPLETED: [],  # Terminal state
            JobState.FAILED: []  # Terminal state
        }
        return to_state in valid_transitions.get(from_state, [])

    @staticmethod
    def is_valid_table_state_transition(from_state: str, to_state: str) -> bool:
        """Validate table state transitions"""
        valid_transitions = {
            TableState.PENDING: [TableState.PROMPT_CREATED, TableState.FAILED_TERMINAL],
            TableState.PROMPT_CREATED: [TableState.LLM_CALLED, TableState.FAILED_TERMINAL],
            TableState.LLM_CALLED: [TableState.RESPONSE_RECEIVED, TableState.FAILED_TERMINAL],
            TableState.RESPONSE_RECEIVED: [TableState.PARSED_OK, TableState.FAILED_TERMINAL],
            TableState.PARSED_OK: [TableState.STORED, TableState.FAILED_TERMINAL],
            TableState.STORED: [],  # Terminal state
            TableState.FAILED_TERMINAL: []  # Terminal state
        }
        return to_state in valid_transitions.get(from_state, [])

    @staticmethod
    def is_terminal_table_state(state: str) -> bool:
        """Check if table state is terminal"""
        return state in [TableState.STORED, TableState.FAILED_TERMINAL]

    @staticmethod
    def is_terminal_job_state(state: str) -> bool:
        """Check if job state is terminal"""
        return state in [JobState.COMPLETED, JobState.FAILED]
