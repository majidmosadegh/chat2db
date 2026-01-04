"""
Use Case Generator Service
Handles async use case generation with job management, WebSocket updates, and comprehensive logging
"""

import asyncio
import uuid
import json
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import hashlib

from api.db_models import (
    UseCase, SchemaSnapshot, SchemaMetadata, DataDictionary,
    Relationship, LLMModel, AiGenerationLog, AIGenerationJob, AITableTask,
    DatabaseConnection
)
from services.llm_helper import generate_with_llm_service
from llm.schemas import LLMRequest, Message, MessageRole
from llm.exceptions import ModelNotFoundError, ModelGenerationError
from api.database import get_db_session
from services.db_connector_utils import create_db_connector_for_snapshot
from core.db_utils import get_table_schema_with_relationships
from core.config import LOG_ENCODING, LOG_ERROR_HANDLING


class JobStatus(Enum):
    WAITING = "waiting"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELED = "canceled"


@dataclass
class UseCaseJob:
    """In-memory job representation"""
    job_id: str
    snapshot_id: int
    business_context: str
    primary_audience: List[str]
    typical_questions: List[str]
    output_preference: str
    number_of_use_cases: int
    language: str
    sample_questions: Optional[List[str]] = None
    scope: str = "snapshot"
    table: Optional[str] = None
    column: Optional[str] = None
    
    status: JobStatus = JobStatus.WAITING
    progress: float = 0.0
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Results
    generated_use_cases: List[Dict[str, Any]] = field(default_factory=list)
    generation_log_id: Optional[int] = None


class UseCaseGenerator:
    """
    Use Case Generator Service
    
    Features:
    - Async job-based architecture
    - Database persistence
    - Real-time WebSocket updates
    - Comprehensive logging for debugging
    - Error isolation
    """
    
    def __init__(self):
        self._jobs: Dict[str, UseCaseJob] = {}
        self._processing_jobs: Set[str] = set()
    
    async def create_job(
        self,
        session: AsyncSession,
        snapshot_id: int,
        business_context: str,
        primary_audience: List[str],
        typical_questions: List[str],
        output_preference: str,
        number_of_use_cases: int,
        language: str,
        sample_questions: Optional[List[str]] = None,
        scope: str = "snapshot",
        table: Optional[str] = None,
        column: Optional[str] = None
    ) -> str:
        """
        Create a new use case generation job
        
        Returns:
            Job ID
        """
        job_id = f"usecase_{snapshot_id}_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"[USECASE_JOB] Creating job {job_id} for snapshot {snapshot_id}, scope: {scope}")
        
        # Create job object
        job = UseCaseJob(
            job_id=job_id,
            snapshot_id=snapshot_id,
            business_context=business_context,
            primary_audience=primary_audience,
            typical_questions=typical_questions,
            output_preference=output_preference,
            number_of_use_cases=number_of_use_cases,
            language=language,
            sample_questions=sample_questions or [],
            scope=scope,
            table=table,
            column=column
        )
        
        # Persist job to database
        await self._persist_job(session, job)
        
        # Store in memory
        self._jobs[job_id] = job
        
        logger.info(f"[USECASE_JOB] Job {job_id} created successfully")
        return job_id
    
    async def _persist_job(self, session: AsyncSession, job: UseCaseJob) -> None:
        """Persist job to database"""
        try:
            db_job = AIGenerationJob(
                job_id=job.job_id,
                snapshot_id=job.snapshot_id,
                status=job.status.value,
                total_tables=1,  # Use case generation is single-task
                completed_tables=0,
                progress_data=json.dumps({
                    "business_context": job.business_context,
                    "primary_audience": job.primary_audience,
                    "typical_questions": job.typical_questions,
                    "output_preference": job.output_preference,
                    "number_of_use_cases": job.number_of_use_cases,
                    "language": job.language,
                    "sample_questions": job.sample_questions,
                    "scope": job.scope,
                    "table": job.table,
                    "column": job.column
                })
            )
            session.add(db_job)
            await session.commit()
            logger.debug(f"[USECASE_JOB] Job {job.job_id} persisted to database")
        except Exception as e:
            await session.rollback()
            logger.error(f"[USECASE_JOB] Failed to persist job {job.job_id}: {e}")
            raise
    
    async def start_job(self, job_id: str) -> bool:
        """
        Start processing a job
        
        Returns:
            True if job was started successfully
        """
        # Load job from database if not in memory
        if job_id not in self._jobs:
            await self._load_job_from_db(job_id)
        
        if job_id not in self._jobs:
            logger.error(f"[USECASE_JOB] Job {job_id} not found")
            return False
        
        job = self._jobs[job_id]
        
        # Only start if in WAITING status
        if job.status != JobStatus.WAITING:
            logger.warning(f"[USECASE_JOB] Job {job_id} is not in WAITING status (current: {job.status.value})")
            return False
        
        # Check if already processing
        if job_id in self._processing_jobs:
            logger.warning(f"[USECASE_JOB] Job {job_id} is already being processed")
            return False
        
        # Update status
        job.status = JobStatus.PROCESSING
        job.updated_at = datetime.now(timezone.utc)
        self._processing_jobs.add(job_id)
        
        # Update database (with retry logic)
        await self._update_job_status(job_id, JobStatus.PROCESSING)
        
        # Broadcast status update
        await self._broadcast_job_update(job_id, "processing", 0.0)
        
        # Start processing in background
        asyncio.create_task(self._process_job(job_id))
        
        logger.info(f"[USECASE_JOB] Job {job_id} started processing")
        return True
    
    async def _load_job_from_db(self, job_id: str) -> None:
        """Load job from database"""
        try:
            async for session in get_db_session():
                try:
                    result = await session.execute(
                        select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                    )
                    db_job = result.scalar_one_or_none()
                    
                    if not db_job:
                        return
                    
                    progress_data = json.loads(db_job.progress_data or "{}")
                    
                    job = UseCaseJob(
                        job_id=db_job.job_id,
                        snapshot_id=db_job.snapshot_id,
                        business_context=progress_data.get("business_context", ""),
                        primary_audience=progress_data.get("primary_audience", []),
                        typical_questions=progress_data.get("typical_questions", []),
                        output_preference=progress_data.get("output_preference", ""),
                        number_of_use_cases=progress_data.get("number_of_use_cases", 5),
                        language=progress_data.get("language", "english"),
                        sample_questions=progress_data.get("sample_questions", []),
                        scope=progress_data.get("scope", "snapshot"),
                        table=progress_data.get("table"),
                        column=progress_data.get("column"),
                        status=JobStatus(db_job.status),
                        progress=db_job.completed_tables / max(db_job.total_tables, 1) * 100,
                        created_at=db_job.created_at or datetime.now(timezone.utc),
                        updated_at=db_job.updated_at or datetime.now(timezone.utc)
                    )
                    
                    self._jobs[job_id] = job
                    logger.info(f"[USECASE_JOB] Loaded job {job_id} from database")
                    break
                except Exception as e:
                    logger.error(f"[USECASE_JOB] Failed to load job {job_id}: {e}")
                    await session.rollback()
                    break
        except Exception as e:
            logger.error(f"[USECASE_JOB] Error loading job {job_id}: {e}")
    
    async def _process_job(self, job_id: str) -> None:
        """Process use case generation job"""
        job = self._jobs.get(job_id)
        if not job:
            logger.error(f"[USECASE_JOB] Job {job_id} not found for processing")
            return
        
        try:
            logger.info(f"[USECASE_JOB] Starting processing for job {job_id}")
            
            # Update progress: 10% - Initialization
            job.progress = 10.0
            await self._broadcast_job_update(job_id, "processing", 10.0)
            
            # Get database session
            async for session in get_db_session():
                try:
                    # Import helper functions from smart_use_case_builder
                    # These are utility functions for formatting data
                    from api.smart_use_case_builder import (
                        _minify_schema_metadata,
                        _format_data_dictionary,
                        _format_relationships,
                        build_use_case_generation_prompt,
                        SmartUseCaseBuilderRequest
                    )
                    
                    # Get snapshot
                    snapshot_result = await session.execute(
                        select(SchemaSnapshot).where(SchemaSnapshot.id == job.snapshot_id)
                    )
                    snapshot = snapshot_result.scalar_one_or_none()
                    if not snapshot:
                        raise ValueError(f"Snapshot {job.snapshot_id} not found")
                    
                    logger.info(f"[USECASE_JOB] Snapshot {job.snapshot_id} found")
                    
                    # Get database type from connection
                    database_type = None
                    try:
                        connection_result = await session.execute(
                            select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
                        )
                        connection = connection_result.scalar_one_or_none()
                        if connection:
                            database_type = connection.db_type.lower() if connection.db_type else None
                            logger.info(f"[USECASE_JOB] Database type: {database_type}")
                    except Exception as e:
                        logger.warning(f"[USECASE_JOB] Could not get database type: {e}")
                    
                    # Update progress: 20% - Schema loaded
                    job.progress = 20.0
                    await self._broadcast_job_update(job_id, "processing", 20.0)
                    
                    # Get active LLM model
                    model_result = await session.execute(
                        select(LLMModel).where(LLMModel.is_active == True)
                    )
                    active_model = model_result.scalar_one_or_none()
                    if not active_model:
                        raise ValueError("No active LLM model found")
                    
                    logger.info(f"[USECASE_JOB] Active model {active_model.id} found")
                    
                    # Get schema metadata
                    schema_query = select(SchemaMetadata).where(
                        SchemaMetadata.schema_snapshot_id == job.snapshot_id
                    )
                    if job.scope == "table" and job.table:
                        schema_query = schema_query.where(SchemaMetadata.table_name == job.table)
                    elif job.scope == "column" and job.table and job.column:
                        schema_query = schema_query.where(
                            and_(
                                SchemaMetadata.table_name == job.table,
                                SchemaMetadata.column_name == job.column
                            )
                        )
                    
                    schema_result = await session.execute(schema_query)
                    schema_metadata = schema_result.scalars().all()
                    
                    if not schema_metadata:
                        raise ValueError("No schema metadata found")
                    
                    # Minify schema
                    minified_schema = _minify_schema_metadata(schema_metadata)
                    logger.info(f"[USECASE_JOB] Minified schema: {len(minified_schema)} tables")
                    
                    # Update progress: 30% - Schema processed
                    job.progress = 30.0
                    await self._broadcast_job_update(job_id, "processing", 30.0)
                    
                    # Get data dictionary
                    dict_query = select(DataDictionary).where(
                        DataDictionary.schema_snapshot_id == job.snapshot_id
                    )
                    if job.scope == "table" and job.table:
                        dict_query = dict_query.where(DataDictionary.table_name == job.table)
                    elif job.scope == "column" and job.table and job.column:
                        dict_query = dict_query.where(
                            and_(
                                DataDictionary.table_name == job.table,
                                DataDictionary.column_name == job.column
                            )
                        )
                    
                    dict_result = await session.execute(dict_query)
                    data_dictionary_raw = dict_result.scalars().all()
                    data_dictionary = _format_data_dictionary(data_dictionary_raw)
                    logger.info(f"[USECASE_JOB] Data dictionary: {len(data_dictionary)} tables")
                    
                    # Get relationships
                    rel_query = select(Relationship).where(
                        Relationship.schema_snapshot_id == job.snapshot_id
                    )
                    if job.scope == "table" and job.table:
                        rel_query = rel_query.where(
                            (Relationship.source_table == job.table) | 
                            (Relationship.target_table == job.table)
                        )
                    elif job.scope == "column" and job.table and job.column:
                        rel_query = rel_query.where(
                            and_(
                                (Relationship.source_table == job.table) | (Relationship.target_table == job.table),
                                (Relationship.source_column == job.column) | (Relationship.target_column == job.column)
                            )
                        )
                    
                    rel_result = await session.execute(rel_query)
                    relationships_raw = rel_result.scalars().all()
                    relationships = _format_relationships(relationships_raw)
                    logger.info(f"[USECASE_JOB] Relationships: {len(relationships)} total")
                    
                    # Update progress: 40% - Context loaded
                    job.progress = 40.0
                    await self._broadcast_job_update(job_id, "processing", 40.0)
                    
                    # Build request object
                    request_obj = SmartUseCaseBuilderRequest(
                        snapshot_id=job.snapshot_id,
                        business_context=job.business_context,
                        primary_audience=job.primary_audience,
                        typical_questions=job.typical_questions,
                        output_preference=job.output_preference,
                        number_of_use_cases=job.number_of_use_cases,
                        language=job.language,
                        sample_questions=job.sample_questions,
                        scope=job.scope,
                        table=job.table,
                        column=job.column
                    )
                    
                    # NEW FLOW: Process each table separately with its own data
                    # Determine which tables to process
                    tables_to_process = list(minified_schema.keys())
                    if job.scope == "table" and job.table:
                        tables_to_process = [t for t in tables_to_process if job.table in t]
                    elif job.scope == "column" and job.table:
                        tables_to_process = [t for t in tables_to_process if job.table in t]
                    
                    # Limit to reasonable number
                    tables_to_process = tables_to_process[:50]
                    total_tables = len(tables_to_process)
                    
                    logger.info(f"[USECASE_JOB] Processing {total_tables} tables sequentially with per-table data")
                    
                    # Update progress: 50% - Starting table processing
                    job.progress = 50.0
                    await self._broadcast_job_update(job_id, "processing", 50.0, {
                        "current_table": None,
                        "total_tables": total_tables,
                        "processed_tables": 0
                    })
                    
                    # Connect to database once
                    db_connector = None
                    try:
                        db_connector = await create_db_connector_for_snapshot(job.snapshot_id, session)
                        if db_connector:
                            await db_connector.connect()
                            logger.info(f"[USECASE_JOB] Connected to database via DBConnector")
                    except Exception as e:
                        logger.warning(f"[USECASE_JOB] Database connection failed: {e}")
                    
                    # Import the single-table prompt builder
                    from api.smart_use_case_builder import build_single_table_use_case_prompt
                    
                    # Process each table sequentially
                    all_use_cases_data = []
                    processed_tables = 0
                    
                    for table_idx, table_key in enumerate(tables_to_process):
                        try:
                            logger.info(f"[USECASE_JOB] Processing table {table_idx + 1}/{total_tables}: {table_key}")
                            
                            # Update progress with current table info
                            progress_base = 50.0
                            progress_per_table = 45.0 / total_tables  # 50% to 95%
                            current_progress = progress_base + (table_idx * progress_per_table)
                            job.progress = current_progress
                            
                            await self._broadcast_job_update(job_id, "processing", current_progress, {
                                "current_table": table_key,
                                "total_tables": total_tables,
                                "processed_tables": processed_tables,
                                "message": f"Processing table {table_idx + 1}/{total_tables}: {table_key}"
                            })
                            
                            # Get schema for this table only
                            table_schema = minified_schema.get(table_key, {})
                            if not table_schema:
                                logger.warning(f"[USECASE_JOB] Schema not found for {table_key}, skipping")
                                continue
                            
                            # Get dictionary for this table only
                            table_dictionary = data_dictionary.get(table_key, {})
                            
                            # Get relationships for this table only
                            table_relationships = [
                                r for r in relationships 
                                if r.get("source_table") == table_key or r.get("target_table") == table_key
                            ]
                            
                            # Get sample data for this table (20-30 rows)
                            table_sample_data = []
                            table_row_count = None
                            
                            if db_connector:
                                try:
                                    if '.' in table_key:
                                        schema_name, table_name = table_key.split('.', 1)
                                    else:
                                        schema_name = None
                                        table_name = table_key
                                    
                                    full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name
                                    
                                    # Get 30 rows of sample data for this table
                                    logger.info(f"[USECASE_JOB] Sampling 30 rows from {full_table_name}")
                                    sample_rows = await db_connector.sample_rows(full_table_name, limit=30)
                                    if sample_rows:
                                        table_sample_data = sample_rows
                                        logger.info(f"[USECASE_JOB] Got {len(sample_rows)} sample rows from {table_key}")
                                    
                                    # Try to get row count
                                    try:
                                        if database_type == "sqlserver":
                                            count_query = f"SELECT COUNT(*) as cnt FROM [{schema_name}].[{table_name}]" if schema_name else f"SELECT COUNT(*) as cnt FROM [{table_name}]"
                                        elif database_type == "mysql":
                                            count_query = f"SELECT COUNT(*) as cnt FROM `{schema_name}`.`{table_name}`" if schema_name else f"SELECT COUNT(*) as cnt FROM `{table_name}`"
                                        elif database_type == "postgresql":
                                            count_query = f'SELECT COUNT(*) as cnt FROM "{schema_name}"."{table_name}"' if schema_name else f'SELECT COUNT(*) as cnt FROM "{table_name}"'
                                        else:
                                            count_query = f"SELECT COUNT(*) as cnt FROM {full_table_name}"
                                        
                                        count_result = await db_connector.execute_query(count_query, limit=1)
                                        if count_result and len(count_result) > 0:
                                            table_row_count = int(count_result[0].get('cnt', count_result[0].get(list(count_result[0].keys())[0], 0)))
                                    except Exception as e:
                                        logger.debug(f"[USECASE_JOB] Could not get row count for {table_key}: {e}")
                                
                                except Exception as e:
                                    logger.warning(f"[USECASE_JOB] Failed to sample data from {table_key}: {e}")
                            
                            # Build prompt for this single table
                            prompt = build_single_table_use_case_prompt(
                                request_obj,
                                table_key,
                                table_schema,
                                table_dictionary,
                                table_relationships,
                                table_sample_data,
                                job.language,
                                database_type=database_type,
                                table_row_count=table_row_count
                            )
                            
                            logger.info(f"[USECASE_JOB] Prompt built for {table_key}: {len(prompt)} characters")
                            
                            # Create LLM request for this table
                            llm_request = LLMRequest(
                                model_id=str(active_model.id),
                                messages=[Message(role=MessageRole.USER, content=prompt)],
                                temperature=active_model.temperature,
                                max_tokens=min(4096, active_model.max_tokens * 2)
                            )
                            
                            # Generate use cases for this table
                            logger.info(f"[USECASE_JOB] Sending request to LLM for table {table_key} (model {active_model.id})")
                            response = await generate_with_llm_service(session, llm_request)
                            generated_text = response.text
                            
                            logger.info(f"[USECASE_JOB] LLM response received for {table_key}: {len(generated_text)} characters")
                            
                            # Parse JSON response for this table
                            cleaned_text = generated_text.strip()
                            if cleaned_text.startswith('```json'):
                                cleaned_text = cleaned_text[7:]
                            elif cleaned_text.startswith('```'):
                                cleaned_text = cleaned_text[3:]
                            if cleaned_text.endswith('```'):
                                cleaned_text = cleaned_text[:-3]
                            cleaned_text = cleaned_text.strip()
                            
                            try:
                                table_use_cases = json.loads(cleaned_text)
                            except json.JSONDecodeError:
                                import re
                                json_match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
                                if json_match:
                                    extracted_json = json_match.group()
                                    extracted_json = re.sub(r',(\s*[}\]])', r'\1', extracted_json)
                                    table_use_cases = json.loads(extracted_json)
                                else:
                                    logger.warning(f"[USECASE_JOB] Could not parse JSON for {table_key}, skipping")
                                    continue
                            
                            if not isinstance(table_use_cases, list):
                                table_use_cases = [table_use_cases]
                            
                            # Add use cases from this table to the collection
                            all_use_cases_data.extend(table_use_cases)
                            processed_tables += 1
                            
                            logger.info(f"[USECASE_JOB] Table {table_key} completed: {len(table_use_cases)} use cases generated")
                            
                        except Exception as e:
                            logger.error(f"[USECASE_JOB] Error processing table {table_key}: {e}", exc_info=True)
                            # Continue with next table even if this one fails
                            continue
                    
                    # Disconnect database
                    if db_connector:
                        try:
                            await db_connector.disconnect()
                        except:
                            pass
                    
                    logger.info(f"[USECASE_JOB] All tables processed: {processed_tables}/{total_tables} tables, {len(all_use_cases_data)} total use cases")
                    
                    # Use the collected use cases
                    use_cases_data = all_use_cases_data
                    
                    # Update progress: 95% - All tables processed
                    job.progress = 95.0
                    await self._broadcast_job_update(job_id, "processing", 95.0, {
                        "current_table": None,
                        "total_tables": total_tables,
                        "processed_tables": processed_tables,
                        "message": f"Processed {processed_tables} tables, validating use cases..."
                    })
                    
                    # Validate use cases
                    validated_use_cases = []
                    for idx, uc_data in enumerate(use_cases_data):
                        if not isinstance(uc_data, dict):
                            logger.warning(f"[USECASE_JOB] Use case {idx + 1} is not a dictionary, skipping")
                            continue
                        
                        # Check if this is new format (has 'title' field) or old format
                        is_new_format = "title" in uc_data
                        logger.debug(f"[USECASE_JOB] Use case {idx + 1}: format={'new' if is_new_format else 'old'}, keys={list(uc_data.keys())[:10]}")
                        
                        if is_new_format:
                            # New format - extract from new structure
                            usecase_name = uc_data.get("title", "Unnamed Use Case")
                            description = uc_data.get("business_goal", "")
                            
                            logger.debug(f"[USECASE_JOB] New format use case: title='{usecase_name}', actor='{uc_data.get('actor', 'N/A')}'")
                            
                            # New format REQUIRES typical_questions/example_queries (added to prompt)
                            typical_questions = uc_data.get("typical_questions", [])
                            if not isinstance(typical_questions, list):
                                typical_questions = [typical_questions] if typical_questions else []
                            
                            example_queries = uc_data.get("example_queries", [])
                            if not isinstance(example_queries, list):
                                example_queries = [example_queries] if example_queries else []
                            
                            # Filter out questions that start with "Query:" or "SQL:" (invalid format)
                            # Process as pairs to maintain order and pairing
                            filtered_pairs = []
                            for q, query in zip(typical_questions, example_queries):
                                # Skip if either is missing (must have both)
                                if not q or not query:
                                    continue
                                
                                if isinstance(q, str):
                                    q_stripped = q.strip()
                                    # Skip questions that start with technical prefixes
                                    if q_stripped.lower().startswith(("query:", "sql:", "کوئری:", "سوال:")):
                                        logger.warning(f"[USECASE_JOB] Skipping invalid question format (starts with technical prefix): {q[:50]}...")
                                        continue
                                    
                                    # Add as a pair to maintain order
                                    filtered_pairs.append({
                                        "question": q,
                                        "query": query
                                    })
                            
                            # Extract filtered lists maintaining order
                            if filtered_pairs:
                                typical_questions = [pair["question"] for pair in filtered_pairs]
                                example_queries = [pair["query"] for pair in filtered_pairs]
                            
                            # Validate that we have at least 3 question-query pairs
                            if len(typical_questions) < 3:
                                logger.warning(f"[USECASE_JOB] Use case '{usecase_name}' has only {len(typical_questions)} questions, expected at least 3")
                            
                            if len(example_queries) < 3:
                                logger.warning(f"[USECASE_JOB] Use case '{usecase_name}' has only {len(example_queries)} queries, expected at least 3")
                            
                            # Final validation: ensure questions and queries match in count (should always be true after filtering)
                            if len(typical_questions) != len(example_queries):
                                min_count = min(len(typical_questions), len(example_queries))
                                logger.error(f"[USECASE_JOB] CRITICAL: Use case '{usecase_name}' has mismatched counts after filtering ({len(typical_questions)} questions vs {len(example_queries)} queries), truncating to {min_count}")
                                typical_questions = typical_questions[:min_count]
                                example_queries = example_queries[:min_count]
                                
                            validated_uc = {
                                "snapshot_id": uc_data.get("snapshot_id", job.snapshot_id),
                                # New format fields
                                "title": usecase_name,
                                "business_goal": description,
                                "actor": uc_data.get("actor", "General User"),
                                "preconditions": uc_data.get("preconditions", []),
                                "main_flow": uc_data.get("main_flow", []),
                                "alternative_flows": uc_data.get("alternative_flows", []),
                                "required_inputs": uc_data.get("required_inputs", []),
                                "sql_intent": uc_data.get("sql_intent", ""),
                                "expected_output": uc_data.get("expected_output", ""),
                                "validation_metrics": uc_data.get("validation_metrics", []),
                                "confidence_reference": uc_data.get("confidence_reference"),
                                "confidence_score": float(uc_data.get("confidence_score", 0.5)),
                                # Legacy fields for backward compatibility
                                "usecase_name": usecase_name,
                                "name": usecase_name,  # Also include 'name' for frontend compatibility
                                "description": description,
                                "scope": uc_data.get("scope", job.scope),
                                "table": uc_data.get("table") if uc_data.get("table") != "null" else job.table,
                                "column": uc_data.get("column") if uc_data.get("column") != "null" else job.column,
                                "expected_sql_patterns": uc_data.get("expected_sql_patterns", []),
                                "required_relations": uc_data.get("required_relations", []),
                                "edge_cases": uc_data.get("edge_cases", []) or uc_data.get("alternative_flows", []),
                                "sample_examples": uc_data.get("sample_examples", []),
                                "query_feasibility_score": float(uc_data.get("confidence_score", uc_data.get("query_feasibility_score", 0.5))),
                                "reasoning": uc_data.get("reasoning", "") or uc_data.get("sql_intent", ""),
                                # Questions and queries
                                "typical_questions": typical_questions if isinstance(typical_questions, list) else [typical_questions] if typical_questions else [],
                                "example_queries": example_queries if isinstance(example_queries, list) else [example_queries] if example_queries else [],
                                # Backward compatibility
                                "output_type": uc_data.get("output_type"),
                                "main_tables": uc_data.get("main_tables"),
                                "risk_notes": uc_data.get("risk_notes")
                            }
                        else:
                            # Old format - extract and validate typical_questions
                            typical_questions = uc_data.get("typical_questions", [])
                            if not isinstance(typical_questions, list):
                                typical_questions = [typical_questions] if typical_questions else []
                            
                            # Extract and validate example_queries
                            example_queries = uc_data.get("example_queries", [])
                            if not isinstance(example_queries, list):
                                example_queries = [example_queries] if example_queries else []
                            
                            usecase_name_for_log = uc_data.get("usecase_name") or uc_data.get("name") or uc_data.get("title", "Unknown")
                            logger.debug(f"[USECASE_JOB] Old format use case: name='{usecase_name_for_log}', questions={len(typical_questions)}, queries={len(example_queries)}")
                            
                            # Ensure at least 3 questions and queries (old format requirement)
                            if len(typical_questions) < 3:
                                logger.warning(f"[USECASE_JOB] Use case '{usecase_name_for_log}' has only {len(typical_questions)} questions, expected at least 3")
                            
                            if len(example_queries) < 3:
                                logger.warning(f"[USECASE_JOB] Use case '{usecase_name_for_log}' has only {len(example_queries)} queries, expected at least 3")
                            
                            # Ensure questions and queries match in count
                            if len(typical_questions) != len(example_queries):
                                min_count = min(len(typical_questions), len(example_queries))
                                logger.warning(f"[USECASE_JOB] Use case '{usecase_name_for_log}' has mismatched counts ({len(typical_questions)} questions vs {len(example_queries)} queries), truncating to {min_count}")
                                typical_questions = typical_questions[:min_count]
                                example_queries = example_queries[:min_count]
                            
                            # Filter out placeholder queries - MAINTAIN PAIRING AND ORDER
                            # Process as pairs to ensure questions and queries stay matched
                            filtered_pairs = []
                            for q_idx, (q, query) in enumerate(zip(typical_questions, example_queries)):
                                # Skip if either is missing (must have both)
                                if not q or not query:
                                    continue
                                
                                # Skip generic placeholder queries
                                if isinstance(query, str):
                                    query_lower = query.lower().strip()
                                    if "information_schema" in query_lower or "select * from information_schema" in query_lower:
                                        logger.warning(f"[USECASE_JOB] Skipping placeholder query for question {q_idx + 1}: {query[:50]}...")
                                        continue
                                
                                # Skip generic questions
                                if isinstance(q, str):
                                    q_lower = q.lower().strip()
                                    if "what information can i get" in q_lower or "what can i get" in q_lower:
                                        logger.warning(f"[USECASE_JOB] Skipping generic question {q_idx + 1}: {q[:50]}...")
                                        continue
                                
                                # Add as a pair to maintain order
                                filtered_pairs.append({
                                    "question": q,
                                    "query": query
                                })
                            
                            # Extract filtered lists maintaining order
                            if filtered_pairs:
                                filtered_questions = [pair["question"] for pair in filtered_pairs]
                                filtered_queries = [pair["query"] for pair in filtered_pairs]
                            else:
                                filtered_questions = []
                                filtered_queries = []
                            
                            # If we filtered out too many, keep at least the first 3 pairs
                            if len(filtered_questions) < 3 and len(typical_questions) >= 3:
                                filtered_questions = typical_questions[:3]
                                filtered_queries = example_queries[:3]
                                logger.warning(f"[USECASE_JOB] After filtering, use case has {len(filtered_questions)} questions, using first 3 pairs")
                            
                            usecase_name_old = uc_data.get("usecase_name") or uc_data.get("name", "Unnamed Use Case")
                            description_old = uc_data.get("description", "")
                            
                            validated_uc = {
                                "snapshot_id": uc_data.get("snapshot_id", job.snapshot_id),
                                # Legacy fields
                                "usecase_name": usecase_name_old,
                                "name": usecase_name_old,  # Also include 'name' for frontend compatibility
                                "description": description_old,
                                # New format fields (mapped from old)
                                "title": usecase_name_old,
                                "business_goal": description_old,
                                "scope": uc_data.get("scope", job.scope),
                                "table": uc_data.get("table") if uc_data.get("table") != "null" else job.table,
                                "column": uc_data.get("column") if uc_data.get("column") != "null" else job.column,
                                "expected_sql_patterns": uc_data.get("expected_sql_patterns", []),
                                "required_relations": uc_data.get("required_relations", []),
                                "edge_cases": uc_data.get("edge_cases", []),
                                "sample_examples": uc_data.get("sample_examples", []),
                                "query_feasibility_score": float(uc_data.get("query_feasibility_score", 0.5)),
                                "reasoning": uc_data.get("reasoning", ""),
                                # Validated questions and queries
                                "typical_questions": filtered_questions if filtered_questions else typical_questions[:3] if len(typical_questions) >= 3 else typical_questions,
                                "example_queries": filtered_queries if filtered_queries else example_queries[:3] if len(example_queries) >= 3 else example_queries,
                                # Backward compatibility
                                "output_type": uc_data.get("output_type"),
                                "main_tables": uc_data.get("main_tables"),
                                "risk_notes": uc_data.get("risk_notes")
                            }
                        
                        validated_use_cases.append(validated_uc)
                    
                    job.generated_use_cases = validated_use_cases
                    logger.info(f"[USECASE_JOB] Successfully generated {len(validated_use_cases)} use cases")
                    
                    # Create generation log
                    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
                    generation_log = AiGenerationLog(
                        schema_snapshot_id=job.snapshot_id,
                        model_id=active_model.id,
                        business_domain=job.business_context,
                        database_description="Smart Use Case Builder (Job-based)",
                        target_user=",".join(job.primary_audience) if job.primary_audience else "",
                        optional_notes=f"Scope: {job.scope}, Output: {job.output_preference}",
                        prompt_hash=prompt_hash
                    )
                    session.add(generation_log)
                    await session.flush()
                    
                    job.generation_log_id = generation_log.id
                    
                    # Update job status to done - use same session
                    job.status = JobStatus.DONE
                    job.progress = 100.0
                    job.updated_at = datetime.now(timezone.utc)
                    
                    # Update job status in database using same session
                    result = await session.execute(
                        select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                    )
                    db_job = result.scalar_one_or_none()
                    if db_job:
                        db_job.status = JobStatus.DONE.value
                        db_job.completed_tables = 1
                    
                    await session.commit()
                    
                    # Broadcast completion
                    await self._broadcast_job_update(job_id, "done", 100.0, {
                        "use_cases": validated_use_cases,
                        "generation_log_id": generation_log.id
                    })
                    
                    logger.info(f"[USECASE_JOB] Job {job_id} completed successfully")
                    break
                    
                except Exception as e:
                    await session.rollback()
                    error_msg = str(e)
                    try:
                        error_msg = error_msg.encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
                    except:
                        pass
                    
                    logger.error(f"[USECASE_JOB] Error processing job {job_id}: {error_msg}", exc_info=True)
                    
                    job.status = JobStatus.FAILED
                    job.error = error_msg
                    job.updated_at = datetime.now(timezone.utc)
                    
                    # Update job status in database using same session
                    try:
                        result = await session.execute(
                            select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                        )
                        db_job = result.scalar_one_or_none()
                        if db_job:
                            db_job.status = JobStatus.FAILED.value
                            db_job.completed_tables = 0
                            db_job.error_message = error_msg
                        await session.commit()
                    except Exception as update_error:
                        logger.error(f"[USECASE_JOB] Failed to update job status in error handler: {update_error}")
                        await session.rollback()
                    
                    await self._broadcast_job_update(job_id, "failed", job.progress, {"error": error_msg})
                    break
        
        except Exception as e:
            error_msg = str(e)
            try:
                error_msg = error_msg.encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            except:
                pass
            
            logger.error(f"[USECASE_JOB] Fatal error processing job {job_id}: {error_msg}", exc_info=True)
            
            job.status = JobStatus.FAILED
            job.error = error_msg
            job.updated_at = datetime.now(timezone.utc)
            
            # Try to update job status in database (with new session since we're outside the loop)
            try:
                async for session in get_db_session():
                    try:
                        result = await session.execute(
                            select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                        )
                        db_job = result.scalar_one_or_none()
                        if db_job:
                            db_job.status = JobStatus.FAILED.value
                            db_job.completed_tables = 0
                            db_job.error_message = error_msg
                        await session.commit()
                        break
                    except Exception as update_error:
                        logger.error(f"[USECASE_JOB] Failed to update job status: {update_error}")
                        await session.rollback()
                        break
            except Exception as e:
                logger.error(f"[USECASE_JOB] Error updating job status: {e}")
            
            await self._broadcast_job_update(job_id, "failed", job.progress, {"error": error_msg})
        
        finally:
            self._processing_jobs.discard(job_id)
    
    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None
    ) -> None:
        """Update job status in database with retry logic for SQLite lock errors"""
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                async for session in get_db_session():
                    try:
                        result = await session.execute(
                            select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                        )
                        db_job = result.scalar_one_or_none()
                        if db_job:
                            db_job.status = status.value
                            db_job.completed_tables = 1 if status == JobStatus.DONE else 0
                            if error:
                                db_job.error_message = error
                            await session.commit()
                        break
                    except Exception as e:
                        error_str = str(e).lower()
                        # Check if it's a lock error and we have retries left
                        if ("locked" in error_str or "database is locked" in error_str) and attempt < max_retries - 1:
                            await session.rollback()
                            logger.warning(f"[USECASE_JOB] Database locked, retrying ({attempt + 1}/{max_retries})...")
                            await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            logger.error(f"[USECASE_JOB] Failed to update job status: {e}")
                            await session.rollback()
                            break
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"[USECASE_JOB] Error updating job status, retrying: {e}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"[USECASE_JOB] Error updating job status after {max_retries} attempts: {e}")
    
    async def _broadcast_job_update(
        self,
        job_id: str,
        status: str,
        progress: float,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Broadcast job update via WebSocket"""
        try:
            from api.use_case_job_router import manager
            
            message = {
                "type": "job_status_update",
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            
            if data:
                message.update(data)
            
            await manager.broadcast_to_job(job_id, message)
        except ImportError:
            # WebSocket manager not available, skip silently
            pass
        except Exception as e:
            logger.debug(f"[USECASE_JOB] Failed to broadcast update: {e}")
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        # Load from database if not in memory
        if job_id not in self._jobs:
            await self._load_job_from_db(job_id)
        
        if job_id not in self._jobs:
            return None
        
        job = self._jobs[job_id]
        
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "progress": job.progress,
            "error": job.error,
            "use_cases": job.generated_use_cases,
            "generation_log_id": job.generation_log_id,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None
        }
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        if job_id not in self._jobs:
            await self._load_job_from_db(job_id)
        
        if job_id not in self._jobs:
            return False
        
        job = self._jobs[job_id]
        
        if job.status in [JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED]:
            return False
        
        job.status = JobStatus.CANCELED
        job.updated_at = datetime.now(timezone.utc)
        
        await self._update_job_status(job_id, JobStatus.CANCELED)
        await self._broadcast_job_update(job_id, "canceled", job.progress)
        
        self._processing_jobs.discard(job_id)
        
        logger.info(f"[USECASE_JOB] Job {job_id} canceled")
        return True


# Global singleton instance
use_case_generator = UseCaseGenerator()

