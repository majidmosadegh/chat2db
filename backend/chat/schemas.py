from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import hashlib


class ChatLanguage(str, Enum):
    """Supported chat languages"""
    ENGLISH = "en"
    PERSIAN = "fa"


class ChatRequest(BaseModel):
    """Request model for chat execution"""
    snapshot_id: int
    selected_model_id: int
    language: ChatLanguage
    user_question: str
    conversation_id: Optional[str] = None


class ChatContext(BaseModel):
    """Immutable context object containing all context for a chat session"""
    snapshot_id: int
    snapshot_name: str
    database_type: str  # postgresql, mysql, sqlserver, etc.
    schema_info: List['SchemaInfo']
    data_dictionary: List['DataDictionaryInfo']
    relationships: List['RelationshipInfo']
    use_cases: List['UseCaseInfo']
    context_hash: str

    def __init__(self, **data):
        # Generate context hash for traceability before validation
        if 'context_hash' not in data:
            snapshot_id = data.get('snapshot_id', 0)
            snapshot_name = data.get('snapshot_name', '')
            database_type = data.get('database_type', '')
            schema_info = data.get('schema_info', [])
            data_dictionary = data.get('data_dictionary', [])
            relationships = data.get('relationships', [])
            use_cases = data.get('use_cases', [])

            context_str = f"{snapshot_id}|{snapshot_name}|{database_type}|" + \
                         f"{len(schema_info)}|{len(data_dictionary)}|" + \
                         f"{len(relationships)}|{len(use_cases)}"
            data['context_hash'] = hashlib.sha256(context_str.encode()).hexdigest()[:16]

        super().__init__(**data)


class PromptTemplate(BaseModel):
    """Versioned and serializable prompt template"""
    version: str
    template_type: str  # 'reasoning', 'sql', 'validation'
    language: ChatLanguage
    template: str
    variables: List[str]
    created_at: datetime = datetime.utcnow()


class LLMResponse(BaseModel):
    """Response from LLM gateway"""
    raw_text: str
    model_used: str
    tokens_used: Optional[int] = None
    processing_time_ms: int
    success: bool
    error_message: Optional[str] = None


class SQLValidationResult(BaseModel):
    """Result of SQL validation"""
    is_valid: bool
    validation_errors: List[str]
    is_read_only: bool
    cleaned_sql: Optional[str] = None


class SQLExecutionResult(BaseModel):
    """Result of SQL execution"""
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: int
    truncated: bool
    success: bool
    error_message: Optional[str] = None


class ConversationState(BaseModel):
    """Optional conversation state for continuity"""
    conversation_id: str
    last_intent: Optional[str] = None
    last_tables: List[str] = []
    last_sql: Optional[str] = None
    last_result_summary: Optional[str] = None
    updated_at: datetime = datetime.utcnow()


class ChatResponse(BaseModel):
    """Enhanced response model with full traceability"""
    success: bool
    user_question: str
    generated_sql: str
    rows: List[Dict[str, Any]]
    row_count: int
    snapshot_id: int
    model_used: str
    execution_status: str
    error_message: Optional[str] = None

    # Traceability fields
    context_hash: str
    sql_validation_status: str  # 'passed', 'failed', 'skipped'
    execution_time_ms: int
    processing_timestamp: datetime = datetime.utcnow()

    # Optional conversation continuity
    conversation_id: Optional[str] = None

    # For conversational responses (when intent is CONVERSATIONAL)
    conversational_response: Optional[str] = None

    # Formatted content for display (includes RTL/LTR formatting)
    formatted_content: Optional[str] = None


class SchemaInfo(BaseModel):
    """Schema information for a table column"""
    schema_name: str
    table_name: str
    column_name: str
    column_type: str
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_table: Optional[str]
    foreign_key_column: Optional[str]


class DataDictionaryInfo(BaseModel):
    """Data dictionary information"""
    schema_name: str
    table_name: str
    column_name: Optional[str]  # None for table-level entries
    description: Optional[str]
    example_values: Optional[str]
    synonyms: Optional[str]
    is_sensitive: bool


class RelationshipInfo(BaseModel):
    """Relationship information"""
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: str
    join_type: str
    cardinality: str
    description: str
    confidence_score: Optional[float]


class UseCaseInfo(BaseModel):
    """Use case information"""
    name: str
    business_goal: str
    example_questions: List[str]
    example_queries: Optional[List[str]]
    output_style: str
