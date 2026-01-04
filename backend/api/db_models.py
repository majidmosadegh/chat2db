from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from typing import Optional
import os

import os
from config.config import DATABASE_URL


Base = declarative_base()


class AIGenerationJob(Base):
    __tablename__ = "ai_generation_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(255), unique=True, nullable=False, index=True)
    snapshot_id = Column(Integer, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="waiting")
    total_tables = Column(Integer, nullable=False, default=0)
    completed_tables = Column(Integer, nullable=False, default=0)
    progress = Column(Float, nullable=True, default=0.0)  # Nullable for backward compatibility
    result = Column(Text, nullable=True)  # JSON result
    # Legacy fields for backward compatibility
    current_table = Column(String(255), nullable=True)
    progress_data = Column(Text, nullable=True)  # Legacy JSON data
    errors = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationship to table tasks
    table_tasks = relationship("AITableTask", back_populates="job", cascade="all, delete-orphan")


class AITableTask(Base):
    __tablename__ = "ai_table_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(255), ForeignKey('ai_generation_jobs.job_id'), nullable=False, index=True)
    snapshot_id = Column(Integer, nullable=False, index=True)
    table_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="waiting")
    progress = Column(Float, nullable=False, default=0.0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationship to job
    job = relationship("AIGenerationJob", back_populates="table_tasks")


class LLMModel(Base):
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    service_name = Column(String(100), nullable=False)  # e.g., "OpenAI", "Ollama", "vLLM"
    base_url = Column(String(500), nullable=False)
    api_key = Column(Text, nullable=True)  # Optional for local services
    model_name = Column(String(100), nullable=False)
    max_tokens = Column(Integer, nullable=False, default=2048)
    temperature = Column(Float, nullable=False, default=0.7)
    top_p = Column(Float, nullable=False, default=1.0)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    db_type = Column(String(50), nullable=False)  # postgresql, mysql, sqlserver
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100), nullable=False)
    password_encrypted = Column(Text, nullable=False)  # Encrypted password
    database_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SchemaSnapshot(Base):
    __tablename__ = "schema_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    connection_id = Column(Integer, ForeignKey('database_connections.id'), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Unique constraint on (connection_id, name) - each connection can have snapshots with unique names
    __table_args__ = (UniqueConstraint('connection_id', 'name', name='unique_snapshot_per_connection'),)


class SchemaMetadata(Base):
    __tablename__ = "schema_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    schema_name = Column(String(100), nullable=False)
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=False)
    column_type = Column(String(100), nullable=False)
    is_primary_key = Column(Boolean, nullable=False, default=False)
    is_foreign_key = Column(Boolean, nullable=False, default=False)
    foreign_key_table = Column(String(100), nullable=True)
    foreign_key_column = Column(String(100), nullable=True)
    column_order = Column(Integer, nullable=True, default=None)  # To preserve column order from database
    created_at = Column(DateTime, server_default=func.now())

    # Add row count for table-level metadata (when column_name is None)
    row_count = Column(Integer, nullable=True)


class DataDictionary(Base):
    __tablename__ = "data_dictionary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    schema_name = Column(String(100), nullable=False)
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=True)  # NULL for table-level
    description = Column(Text, nullable=True)
    example_values = Column(Text, nullable=True)  # JSON array
    synonyms = Column(Text, nullable=True)  # comma-separated
    is_sensitive = Column(Boolean, nullable=False, default=False)
    is_ai_generated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    source_table = Column(String(100), nullable=False)
    source_column = Column(String(100), nullable=False)
    target_table = Column(String(100), nullable=False)
    target_column = Column(String(100), nullable=False)
    relationship_type = Column(String(20), nullable=False, default="manual")  # schema_fk, ai_suggested, manual
    join_type = Column(String(20), nullable=False, default="inner")  # inner, left, right
    cardinality = Column(String(5), nullable=False, default="1-n")  # 1-1, 1-n, n-1, n-n
    description = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)  # AI confidence (0-1)
    strength_score = Column(Float, nullable=True)  # Calculated ranking score (0-1)
    semantic_similarity = Column(Float, nullable=True)  # Column/table name similarity (0-1)
    user_accepted = Column(Boolean, nullable=False, default=False)  # User manually accepted
    agent_approved = Column(Boolean, nullable=False, default=False)  # Approved for agent use
    is_confirmed = Column(Boolean, nullable=False, default=False)  # Legacy field
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UseCase(Base):
    __tablename__ = "use_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)

    # Basic fields
    name = Column(String(200), nullable=False)
    business_goal = Column(Text, nullable=False)
    example_questions = Column(Text, nullable=False)  # JSON array
    example_queries = Column(Text, nullable=True)  # JSON array of SQL queries
    output_style = Column(String(100), nullable=False)  # numeric, summary, analytical

    # AI Generation tracking
    is_ai_generated = Column(Boolean, nullable=False, default=False)
    generation_log_id = Column(Integer, ForeignKey('ai_generation_logs.id'), nullable=True)
    generation_version = Column(Integer, nullable=True)

    # Smart Builder wizard inputs (stored for reference)
    business_context = Column(Text, nullable=True)
    primary_audience = Column(Text, nullable=True)  # JSON array
    typical_questions = Column(Text, nullable=True)  # JSON array
    output_preference = Column(String(100), nullable=True)

    # Version tracking
    dictionary_version = Column(Integer, nullable=True)  # data dictionary version
    relationships_version = Column(Integer, nullable=True)  # relationships version

    # Relationships
    versions = relationship("UseCaseVersion", backref="original_use_case", cascade="all, delete-orphan")
    fine_tuning_sessions = relationship("FineTuningSession", backref="use_case", cascade="all, delete-orphan")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AiGenerationLog(Base):
    __tablename__ = "ai_generation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('llm_models.id'), nullable=False)
    business_domain = Column(String(200), nullable=False)
    database_description = Column(Text, nullable=False)
    target_user = Column(String(200), nullable=False)
    optional_notes = Column(Text, nullable=True)
    prompt_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class GeneratedPrompt(Base):
    __tablename__ = "generated_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    version = Column(Integer, nullable=False)
    prompt_text = Column(Text, nullable=False)
    model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class UseCaseVersion(Base):
    __tablename__ = "use_case_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_use_case_id = Column(Integer, ForeignKey('use_cases.id'), nullable=False)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)

    # Version info
    version_number = Column(Integer, nullable=False)
    version_description = Column(Text, nullable=True)  # e.g., "Fine-tuned based on execution results"

    # Copied fields from original use case
    name = Column(String(200), nullable=False)
    business_goal = Column(Text, nullable=False)
    example_questions = Column(Text, nullable=False)  # JSON array
    example_queries = Column(Text, nullable=True)  # JSON array of SQL queries
    output_style = Column(String(100), nullable=False)  # numeric, summary, analytical

    # AI Generation tracking
    is_ai_generated = Column(Boolean, nullable=False, default=False)
    generation_log_id = Column(Integer, ForeignKey('ai_generation_logs.id'), nullable=True)
    generation_version = Column(Integer, nullable=True)

    # Smart Builder wizard inputs (stored for reference)
    business_context = Column(Text, nullable=True)
    primary_audience = Column(Text, nullable=True)  # JSON array
    typical_questions = Column(Text, nullable=True)  # JSON array
    output_preference = Column(String(100), nullable=True)

    # Version tracking
    dictionary_version = Column(Integer, nullable=True)  # data dictionary version
    relationships_version = Column(Integer, nullable=True)  # relationships version

    # Fine-tuning metrics
    confidence_score = Column(Float, nullable=True)  # approved_questions / total_questions

    created_at = Column(DateTime, server_default=func.now())


class FineTuningSession(Base):
    __tablename__ = "fine_tuning_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    use_case_id = Column(Integer, ForeignKey('use_cases.id'), nullable=False)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('llm_models.id'), nullable=False)

    # Session configuration
    include_full_dictionary = Column(Boolean, nullable=False, default=False)
    questions_count = Column(Integer, nullable=False, default=5)
    language = Column(String(20), nullable=False, default="english")  # "english" or "persian"

    # Status tracking
    status = Column(String(50), nullable=False, default="created")  # created, generating_questions, executing_sql, refining_use_case, completed, failed
    current_step = Column(String(50), nullable=True)  # context_preview, question_generation, sql_execution, use_case_refinement

    # Results
    generated_questions_count = Column(Integer, nullable=False, default=0)
    approved_questions_count = Column(Integer, nullable=False, default=0)
    rejected_questions_count = Column(Integer, nullable=False, default=0)
    confidence_score = Column(Float, nullable=True)  # approved_questions / total_questions

    # Final output
    refined_use_case_version_id = Column(Integer, ForeignKey('use_case_versions.id'), nullable=True)

    # Relationships
    questions = relationship("FineTuningQuestion", backref="session", cascade="all, delete-orphan")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FineTuningQuestion(Base):
    __tablename__ = "fine_tuning_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('fine_tuning_sessions.id'), nullable=False)
    question_index = Column(Integer, nullable=False)  # Order in the session

    # Question data
    question_text = Column(Text, nullable=False)
    is_user_edited = Column(Boolean, nullable=False, default=False)
    original_question_text = Column(Text, nullable=True)  # If user edited

    # SQL generation
    generated_sql = Column(Text, nullable=True)
    sql_generation_error = Column(Text, nullable=True)
    sql_generation_model_id = Column(Integer, ForeignKey('llm_models.id'), nullable=True)

    # Execution results
    execution_status = Column(String(50), nullable=True)  # pending, executing, success, error
    execution_result = Column(Text, nullable=True)  # JSON result data
    execution_error = Column(Text, nullable=True)
    execution_duration_ms = Column(Integer, nullable=True)

    # User feedback
    user_approval = Column(String(20), nullable=True)  # approved, rejected, pending
    user_feedback = Column(Text, nullable=True)  # Optional user feedback

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class MaturationSession(Base):
    """Session for continuous use case maturation"""
    __tablename__ = "maturation_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    use_case_id = Column(Integer, ForeignKey('use_cases.id'), nullable=False)
    schema_snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('llm_models.id'), nullable=False)

    # Session configuration
    language = Column(String(20), nullable=False, default="persian")
    questions_per_batch = Column(Integer, nullable=False, default=5)
    max_retries_per_question = Column(Integer, nullable=False, default=3)

    # Status tracking
    status = Column(String(50), nullable=False, default="created")  # created, generating, processing, paused, completed, failed
    current_step = Column(String(50), nullable=True)  # loading_context, generating_questions, generating_sql, executing_sql, storing_results

    # Progress tracking
    total_questions_generated = Column(Integer, nullable=False, default=0)
    total_questions_processed = Column(Integer, nullable=False, default=0)
    successful_questions = Column(Integer, nullable=False, default=0)
    failed_questions = Column(Integer, nullable=False, default=0)
    stored_questions = Column(Integer, nullable=False, default=0)  # Approved and stored

    # Statistics
    average_execution_time_ms = Column(Float, nullable=True)
    success_rate = Column(Float, nullable=True)  # successful_questions / total_questions_processed
    
    # Session metadata storage (JSON) for storing test results, analysis, and other session data
    # Note: Using 'session_metadata' instead of 'metadata' because 'metadata' is reserved in SQLAlchemy
    session_metadata = Column(Text, nullable=True)  # JSON: {existing_test_results: {...}, analysis: {...}, last_processed_index: int, ...}

    # Relationships
    questions = relationship("MaturationQuestion", backref="session", cascade="all, delete-orphan")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class MaturationQuestion(Base):
    """Question generated and processed during maturation"""
    __tablename__ = "maturation_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('maturation_sessions.id'), nullable=False)
    question_index = Column(Integer, nullable=False)  # Order in the session

    # Question data
    question_text = Column(Text, nullable=False)
    is_user_edited = Column(Boolean, nullable=False, default=False)
    original_question_text = Column(Text, nullable=True)  # If user edited

    # SQL generation
    generated_sql = Column(Text, nullable=True)
    sql_generation_error = Column(Text, nullable=True)
    sql_generation_model_id = Column(Integer, ForeignKey('llm_models.id'), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Execution results
    execution_status = Column(String(50), nullable=True)  # pending, generating_sql, executing, success, error, retrying
    execution_result = Column(Text, nullable=True)  # JSON result data
    execution_error = Column(Text, nullable=True)
    execution_duration_ms = Column(Integer, nullable=True)

    # User feedback
    user_approval = Column(String(20), nullable=True)  # approved, rejected, pending
    user_feedback = Column(Text, nullable=True)  # Optional user feedback
    is_stored = Column(Boolean, nullable=False, default=False)  # Whether stored in use case

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ChatBot(Base):
    """Chat Bot configuration - each bot has fixed settings"""
    __tablename__ = "chat_bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)  # User-defined bot name
    description = Column(Text, nullable=True)  # Optional description
    
    # Bot configuration (fixed for all sessions in this bot)
    snapshot_id = Column(Integer, ForeignKey('schema_snapshots.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('llm_models.id'), nullable=False)
    language = Column(String(20), nullable=False, default="english")  # en, fa, etc.
    
    # Statistics
    session_count = Column(Integer, nullable=False, default=0)  # Number of sessions
    total_message_count = Column(Integer, nullable=False, default=0)  # Total messages across all sessions
    
    # Last activity timestamp (from most recent session)
    last_activity_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sessions = relationship("ChatSession", back_populates="bot", cascade="all, delete-orphan")


class ChatSession(Base):
    """Chat session for storing conversation history - belongs to a ChatBot"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey('chat_bots.id'), nullable=False)  # Link to ChatBot
    conversation_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=True)  # Auto-generated or user-defined title
    
    # Message count for quick display
    message_count = Column(Integer, nullable=False, default=0)
    
    # Last activity timestamp
    last_activity_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    bot = relationship("ChatBot", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Individual messages in a chat session"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id'), nullable=False)
    conversation_id = Column(String(255), nullable=False, index=True)  # Denormalized for easier querying
    
    # Message content
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    
    # SQL execution metadata
    generated_sql = Column(Text, nullable=True)
    execution_status = Column(String(50), nullable=True)
    row_count = Column(Integer, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    # Additional metadata as JSON (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    message_metadata = Column(Text, nullable=True)  # JSON string for additional data
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")


# Database setup
# DATABASE_URL is now imported from config.py

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Dependency for routes
async def get_db_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
