"""
AI Data Dictionary Generator Service
Complete production-ready service with queue architecture, real-time updates, and full reliability
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, delete

from api.db_models import (
    AIGenerationJob, 
    AITableTask, 
    SchemaMetadata, 
    DataDictionary,
    SchemaSnapshot,
    DatabaseConnection
)
from services.db_connector_utils import create_db_connector_for_snapshot
from services.db_connector import DirectDatabaseConnector
from services.llm_service import LLMService
from api.database import get_db_session, decrypt_password
from core.db_utils import get_table_schema_with_relationships
from core.prompts.dictionary_prompts import build_dictionary_prompt, build_schema_context

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status enumeration"""
    WAITING = "waiting"
    PROCESSING = "processing"
    DONE = "done"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELED = "canceled"
    STOPPED = "stopped"


class GenerationScope(Enum):
    """Generation scope enumeration"""
    COLUMN = "column"
    TABLE = "table"
    MULTI_TABLE = "multi_table"
    FULL_SNAPSHOT = "full_snapshot"


@dataclass
class TableTask:
    """Represents a table generation task"""
    table_name: str
    schema_name: str
    status: JobStatus = JobStatus.WAITING
    progress: float = 0.0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        table_key = f"{self.schema_name}.{self.table_name}"
        return {
            "table": table_key,
            "status": self.status.value,
            "progress": int(self.progress),
            "error": self.error_message if self.status == JobStatus.FAILED else None
        }


@dataclass
class DictionaryJob:
    """Represents a dictionary generation job"""
    job_id: str
    snapshot_id: int
    scope: GenerationScope
    target_names: List[str]
    business_domain: str
    language: str
    audience: str
    tone: str
    status: JobStatus = JobStatus.WAITING
    table_tasks: Dict[str, TableTask] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    row_sample_limit: int = 5


class AIDictionaryGenerator:
    """
    AI Data Dictionary Generator Service
    
    Features:
    - Async queue architecture with error isolation
    - Database persistence for all tasks
    - Real-time WebSocket updates
    - Stop/pause control per task
    - Database sampling with configurable limits
    - Schema compression before LLM
    """

    def __init__(self):
        self._jobs: Dict[str, DictionaryJob] = {}
        self._queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._max_workers = 3
        self._shutdown_event = asyncio.Event()
        self._llm_service = LLMService()
        self._llm_initialized = False
        self._processing_tasks: Set[str] = set()  # Track currently processing task keys

    async def initialize(self) -> None:
        """Initialize the service"""
        logger.info("Initializing AI Dictionary Generator service")
        # LLM service will be initialized on first use
        logger.info("AI Dictionary Generator service initialized")

    async def shutdown(self) -> None:
        """Shutdown the service gracefully"""
        logger.info("Shutting down AI Dictionary Generator service")
        self._shutdown_event.set()
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to complete
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        logger.info("AI Dictionary Generator service shutdown complete")

    async def create_job(
        self,
        session: AsyncSession,
        snapshot_id: int,
        business_domain: str,
        language: str,
        audience: str,
        tone: str,
        scope: GenerationScope,
        target_names: List[str],
        row_sample_limit: int = 5
    ) -> str:
        """
        Create a new dictionary generation job
        
        Args:
            session: Database session
            snapshot_id: Schema snapshot ID
            business_domain: Business domain context
            language: Output language
            audience: Target audience
            tone: Tone of descriptions
            scope: Generation scope
            target_names: Target table/column names
            row_sample_limit: Number of sample rows per table
            
        Returns:
            Job ID
        """
        job_id = f"dict_{snapshot_id}_{uuid.uuid4().hex[:8]}"
        
        # Determine target tables based on scope
        target_tables = await self._resolve_target_tables(
            session, snapshot_id, scope, target_names
        )
        
        if not target_tables:
            raise ValueError(f"No tables found for scope {scope.value} with targets {target_names}")
        
        # Create job object
        job = DictionaryJob(
            job_id=job_id,
            snapshot_id=snapshot_id,
            scope=scope,
            target_names=target_names,
            business_domain=business_domain,
            language=language,
            audience=audience,
            tone=tone,
            row_sample_limit=row_sample_limit,
        )
        
        # Adjust row sample limit based on scope
        # 3 rows when sampling all tables, 5 rows for specific tables
        if scope == GenerationScope.FULL_SNAPSHOT:
            job.row_sample_limit = 3
        else:
            job.row_sample_limit = 5
        
        # Create table tasks in memory
        for schema_name, table_name in target_tables:
            task = TableTask(
                table_name=table_name,
                schema_name=schema_name,
            )
            job.table_tasks[f"{schema_name}.{table_name}"] = task
        
        # Persist job to database FIRST
        await self._persist_job(session, job)
        
        # Create AITableTask records BEFORE queuing
        for table_key, table_task in job.table_tasks.items():
            db_task = AITableTask(
                job_id=job_id,
                snapshot_id=snapshot_id,
                table_name=table_key,
                status="waiting",
                progress=0.0,
                error=None
            )
            session.add(db_task)
        
        await session.commit()
        
        # Store job in memory
        self._jobs[job_id] = job
        
        logger.info(f"Created dictionary generation job {job_id} with {len(job.table_tasks)} tables")
        return job_id

    async def start_job(self, job_id: str) -> bool:
        """
        Start processing a job
        
        Args:
            job_id: Job ID to start
            
        Returns:
            True if job was started successfully
        """
        # Load job from database if not in memory
        if job_id not in self._jobs:
            await self._load_job_from_db(job_id)
        
        if job_id not in self._jobs:
            logger.error(f"Job {job_id} not found")
            return False
        
        job = self._jobs[job_id]
        
        # Only start if in WAITING status
        if job.status != JobStatus.WAITING:
            logger.warning(f"Job {job_id} is not in WAITING status (current: {job.status.value})")
            return False
        
        # Update job status
        job.status = JobStatus.PROCESSING
        job.updated_at = datetime.now(timezone.utc)
        
        # Persist job status
        async for session in get_db_session():
            try:
                result = await session.execute(
                    select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                )
                db_job = result.scalar_one_or_none()
                if db_job:
                    db_job.status = "processing"
                    await session.commit()
                break
            except Exception as e:
                logger.error(f"Failed to update job status: {e}")
                await session.rollback()
                break
        
        # Start worker tasks if not already running
        if not self._workers:
            for i in range(self._max_workers):
                if not self._shutdown_event.is_set():
                    worker = asyncio.create_task(self._process_queue_worker(i))
                    self._workers.append(worker)
        
        # Add all waiting table tasks to queue
        queued_count = 0
        for table_key, table_task in job.table_tasks.items():
            if table_task.status == JobStatus.WAITING:
                await self._queue.put((job_id, table_key))
                queued_count += 1
        
        logger.info(f"Started job {job_id} with {queued_count} table tasks queued")
        return True

    async def stop_table_task(self, job_id: str, table_name: str) -> bool:
        """
        Stop a specific table task
        
        Args:
            job_id: Job ID
            table_name: Table name (schema.table format)
            
        Returns:
            True if task was stopped
        """
        if job_id not in self._jobs:
            await self._load_job_from_db(job_id)
        
        if job_id not in self._jobs:
            return False
        
        job = self._jobs[job_id]
        if table_name not in job.table_tasks:
            return False
        
        task = job.table_tasks[table_name]
        
        # Can stop if waiting or processing
        if task.status in [JobStatus.WAITING, JobStatus.PROCESSING]:
            task.status = JobStatus.STOPPED
            task.error_message = "Task stopped by user"
            job.updated_at = datetime.now(timezone.utc)
            
            # Update in database
            async for session in get_db_session():
                try:
                    result = await session.execute(
                        select(AITableTask).where(
                            and_(
                                AITableTask.job_id == job_id,
                                AITableTask.table_name == table_name
                            )
                        )
                    )
                    db_task = result.scalar_one_or_none()
                    if db_task:
                        db_task.status = "stopped"
                        db_task.error = "Task stopped by user"
                        await session.commit()
                    
                    # Send WebSocket update
                    await self._broadcast_task_update(job_id, table_name, "stopped", 0.0, "Task stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Failed to stop task: {e}")
                    await session.rollback()
                    break
            
            logger.info(f"Stopped table task {table_name} in job {job_id}")
            return True
        
        return False

    async def pause_table_task(self, job_id: str, table_name: str) -> bool:
        """
        Pause a specific table task
        
        Args:
            job_id: Job ID
            table_name: Table name (schema.table format)
            
        Returns:
            True if task was paused
        """
        if job_id not in self._jobs:
            return False
        
        job = self._jobs[job_id]
        if table_name not in job.table_tasks:
            return False
        
        task = job.table_tasks[table_name]
        
        if task.status == JobStatus.PROCESSING:
            task.status = JobStatus.PAUSED
            task.error_message = "Task paused by user"
            
            # Update in database
            async for session in get_db_session():
                try:
                    result = await session.execute(
                        select(AITableTask).where(
                            and_(
                                AITableTask.job_id == job_id,
                                AITableTask.table_name == table_name
                            )
                        )
                    )
                    db_task = result.scalar_one_or_none()
                    if db_task:
                        db_task.status = "paused"
                        await session.commit()
                    
                    await self._broadcast_task_update(job_id, table_name, "paused", task.progress, "Task paused by user")
                    break
                except Exception as e:
                    logger.error(f"Failed to pause task: {e}")
                    await session.rollback()
                    break
            
            logger.info(f"Paused table task {table_name} in job {job_id}")
            return True
        
        return False

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel an entire job
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if job was canceled
        """
        if job_id not in self._jobs:
            await self._load_job_from_db(job_id)
        
        if job_id not in self._jobs:
            # Try to cancel directly in database
            async for session in get_db_session():
                try:
                    result = await session.execute(
                        select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                    )
                    db_job = result.scalar_one_or_none()
                    if db_job and db_job.status in ["waiting", "processing", "paused"]:
                        db_job.status = "canceled"
                        await session.commit()
                        return True
                    break
                except Exception as e:
                    logger.error(f"Failed to cancel job: {e}")
                    await session.rollback()
                    break
            return False
        
        job = self._jobs[job_id]
        if job.status in [JobStatus.WAITING, JobStatus.PROCESSING, JobStatus.PAUSED]:
            job.status = JobStatus.CANCELED
            job.updated_at = datetime.now(timezone.utc)
            
            # Cancel all table tasks
            async for session in get_db_session():
                try:
                    # Update job
                    result = await session.execute(
                        select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                    )
                    db_job = result.scalar_one_or_none()
                    if db_job:
                        db_job.status = "canceled"
                    
                    # Update all tasks
                    result = await session.execute(
                        select(AITableTask).where(AITableTask.job_id == job_id)
                    )
                    db_tasks = result.scalars().all()
                    for db_task in db_tasks:
                        if db_task.status in ["waiting", "processing", "paused"]:
                            db_task.status = "canceled"
                            db_task.error = "Job canceled by user"
                    
                    await session.commit()
                    
                    # Send WebSocket update
                    await self._broadcast_job_update(job_id, "canceled", 0.0)
                    break
                except Exception as e:
                    logger.error(f"Failed to cancel job: {e}")
                    await session.rollback()
                    break
            
            logger.info(f"Canceled job {job_id}")
            return True
        
        return False

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status dictionary or None if not found
        """
        # Load from database
        async for session in get_db_session():
            try:
                # Get job
                result = await session.execute(
                    select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                )
                db_job = result.scalar_one_or_none()
                
                if not db_job:
                    return None
                
                # Get table tasks
                tasks_result = await session.execute(
                    select(AITableTask).where(AITableTask.job_id == job_id)
                )
                db_tasks = tasks_result.scalars().all()
                
                # Build table_tasks dictionary
                table_tasks_dict = {}
                for task in db_tasks:
                    table_tasks_dict[task.table_name] = {
                        "status": task.status,
                        "progress": task.progress,
                        "error": task.error
                    }
                
                return {
                    "job_id": db_job.job_id,
                    "snapshot_id": db_job.snapshot_id,
                    "status": db_job.status,
                    "total_tables": db_job.total_tables,
                    "completed_tables": db_job.completed_tables,
                    "progress": db_job.progress if db_job.progress is not None else 0.0,
                    "table_tasks": table_tasks_dict
                }
            except Exception as e:
                logger.error(f"Error loading job status: {e}")
                return None

    async def _resolve_target_tables(
        self,
        session: AsyncSession,
        snapshot_id: int,
        scope: GenerationScope,
        target_names: List[str]
    ) -> List[tuple]:
        """
        Resolve target tables based on scope and target names
        
        Returns:
            List of (schema_name, table_name) tuples
        """
        try:
            if scope == GenerationScope.FULL_SNAPSHOT:
                # Get all tables
                result = await session.execute(
                    select(
                        SchemaMetadata.schema_name,
                        SchemaMetadata.table_name
                    ).where(
                        SchemaMetadata.schema_snapshot_id == snapshot_id
                    ).distinct().order_by(
                        SchemaMetadata.schema_name,
                        SchemaMetadata.table_name
                    )
                )
                return list(result.all())
            
            elif scope == GenerationScope.TABLE:
                # Get specific tables
                tables = []
                for target in target_names:
                    # Handle schema.table format or just table name
                    if '.' in target:
                        schema_name, table_name = target.split('.', 1)
                    else:
                        # Try to find table in any schema
                        result = await session.execute(
                            select(
                                SchemaMetadata.schema_name,
                                SchemaMetadata.table_name
                            ).where(
                                and_(
                                    SchemaMetadata.schema_snapshot_id == snapshot_id,
                                    SchemaMetadata.table_name == target
                                )
                            ).distinct().limit(1)
                        )
                        row = result.first()
                        if row:
                            schema_name, table_name = row
                        else:
                            continue
                    
                    # Verify table exists
                    result = await session.execute(
                        select(SchemaMetadata).where(
                            and_(
                                SchemaMetadata.schema_snapshot_id == snapshot_id,
                                SchemaMetadata.schema_name == schema_name,
                                SchemaMetadata.table_name == table_name
                            )
                        ).limit(1)
                    )
                    if result.scalar_one_or_none():
                        tables.append((schema_name, table_name))
                
                return tables
            
            elif scope == GenerationScope.COLUMN:
                # Get tables containing the specified columns
                tables = []
                for target in target_names:
                    result = await session.execute(
                        select(
                            SchemaMetadata.schema_name,
                            SchemaMetadata.table_name
                        ).where(
                            and_(
                                SchemaMetadata.schema_snapshot_id == snapshot_id,
                                SchemaMetadata.column_name == target
                            )
                        ).distinct().limit(1)
                    )
                    row = result.first()
                    if row:
                        tables.append(row)
                
                return tables
            
            else:
                return []
        
        except Exception as e:
            logger.error(f"Failed to resolve target tables: {e}")
            return []

    async def _persist_job(self, session: AsyncSession, job: DictionaryJob) -> None:
        """Persist job to database"""
        try:
            # Check if job exists
            result = await session.execute(
                select(AIGenerationJob).where(AIGenerationJob.job_id == job.job_id)
            )
            db_job = result.scalar_one_or_none()
            
            if db_job:
                # Update existing job
                db_job.status = job.status.value
                db_job.total_tables = len(job.table_tasks)
                db_job.completed_tables = sum(
                    1 for t in job.table_tasks.values() 
                    if t.status == JobStatus.DONE
                )
                db_job.progress = (db_job.completed_tables / db_job.total_tables * 100) if db_job.total_tables > 0 else 0.0
            else:
                # Create new job
                db_job = AIGenerationJob(
                    job_id=job.job_id,
                    snapshot_id=job.snapshot_id,
                    status=job.status.value,
                    total_tables=len(job.table_tasks),
                    completed_tables=0,
                    progress=0.0
                )
                session.add(db_job)
            
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist job: {e}")
            await session.rollback()
            raise

    async def _load_job_from_db(self, job_id: str) -> None:
        """Load job from database into memory"""
        async for session in get_db_session():
            try:
                # Get job
                result = await session.execute(
                    select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                )
                db_job = result.scalar_one_or_none()
                
                if not db_job:
                    return
                
                # Get table tasks
                tasks_result = await session.execute(
                    select(AITableTask).where(AITableTask.job_id == job_id)
                )
                db_tasks = tasks_result.scalars().all()
                
                # Determine scope and target_names from job metadata
                # For now, we'll use a simple approach - if we can't determine, use FULL_SNAPSHOT
                scope = GenerationScope.FULL_SNAPSHOT
                target_names = []
                
                # Reconstruct job
                job = DictionaryJob(
                    job_id=db_job.job_id,
                    snapshot_id=db_job.snapshot_id,
                    scope=scope,
                    target_names=target_names,
                    business_domain="",  # Will need to be stored if needed
                    language="persian",
                    audience="",
                    tone="professional",
                    status=JobStatus(db_job.status),
                    row_sample_limit=5
                )
                
                # Reconstruct table tasks
                for db_task in db_tasks:
                    schema_name, table_name = db_task.table_name.split('.', 1) if '.' in db_task.table_name else ("", db_task.table_name)
                    task = TableTask(
                        table_name=table_name,
                        schema_name=schema_name,
                        status=JobStatus(db_task.status),
                        progress=db_task.progress,
                        error_message=db_task.error
                    )
                    job.table_tasks[db_task.table_name] = task
                
                self._jobs[job_id] = job
                break
            except Exception as e:
                logger.error(f"Failed to load job from database: {e}")
                break

    async def _process_queue_worker(self, worker_id: int) -> None:
        """
        Worker task that processes queue items
        
        This worker NEVER crashes the queue loop on failure.
        Each table task runs in its own try/except isolation.
        """
        logger.info(f"Queue worker {worker_id} started")
        
        while not self._shutdown_event.is_set():
            try:
                # Get next task from queue with timeout
                try:
                    job_id, table_key = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check if task is already being processed
                task_key = f"{job_id}:{table_key}"
                if task_key in self._processing_tasks:
                    logger.debug(f"Task {task_key} already being processed, skipping")
                    continue
                
                # Check if job exists
                if job_id not in self._jobs:
                    await self._load_job_from_db(job_id)
                
                if job_id not in self._jobs:
                    logger.warning(f"Job {job_id} not found, skipping task {table_key}")
                    continue
                
                job = self._jobs[job_id]
                
                # Check if job is canceled or stopped
                if job.status in [JobStatus.CANCELED, JobStatus.STOPPED]:
                    logger.debug(f"Job {job_id} is {job.status.value}, skipping task {table_key}")
                    continue
                
                # Check if table task exists
                if table_key not in job.table_tasks:
                    logger.warning(f"Table task {table_key} not found in job {job_id}")
                    continue
                
                table_task = job.table_tasks[table_key]
                
                # Check if task should be processed
                if table_task.status not in [JobStatus.WAITING, JobStatus.PAUSED]:
                    logger.debug(f"Task {table_key} is not in WAITING/PAUSED status (current: {table_task.status.value})")
                    continue
                
                # Process task in isolation
                self._processing_tasks.add(task_key)
                try:
                    await self._process_table_task(job, table_task, table_key)
                except Exception as e:
                    # Log error but don't crash
                    logger.error(f"Error processing table task {table_key}: {e}", exc_info=True)
                    # Mark task as failed
                    table_task.status = JobStatus.FAILED
                    table_task.error_message = str(e)[:500]  # Limit error message length
                    
                    # Update in database
                    async for session in get_db_session():
                        try:
                            result = await session.execute(
                                select(AITableTask).where(
                                    and_(
                                        AITableTask.job_id == job_id,
                                        AITableTask.table_name == table_key
                                    )
                                )
                            )
                            db_task = result.scalar_one_or_none()
                            if db_task:
                                db_task.status = "failed"
                                db_task.error = table_task.error_message
                                await session.commit()
                            break
                        except Exception as db_error:
                            logger.error(f"Failed to update failed task in DB: {db_error}")
                            await session.rollback()
                            break
                    
                    # Send WebSocket update
                    await self._broadcast_task_update(job_id, table_key, "failed", 0.0, table_task.error_message)
                
                finally:
                    self._processing_tasks.discard(task_key)
                    self._queue.task_done()
            
            except Exception as e:
                # Never crash the worker loop
                logger.error(f"Error in queue worker {worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before continuing
        
        logger.info(f"Queue worker {worker_id} stopped")

    async def _process_table_task(
        self,
        job: DictionaryJob,
        table_task: TableTask,
        table_key: str
    ) -> None:
        """
        Process a single table task
        
        This method:
        1. Samples data from database
        2. Gets schema information
        3. Compresses/minifies schema
        4. Calls LLM
        5. Parses response
        6. Saves dictionary results
        7. Updates task status
        """
        schema_name, table_name = table_key.split('.', 1) if '.' in table_key else ("", table_key)
        
        logger.info(f"Processing table task {table_key} for job {job.job_id}")
        
        # Update status to processing
        table_task.status = JobStatus.PROCESSING
        table_task.progress = 10.0
        table_task.started_at = datetime.now(timezone.utc)
        
        # Update in database
        async for session in get_db_session():
            try:
                result = await session.execute(
                    select(AITableTask).where(
                        and_(
                            AITableTask.job_id == job.job_id,
                            AITableTask.table_name == table_key
                        )
                    )
                )
                db_task = result.scalar_one_or_none()
                if db_task:
                    db_task.status = "processing"
                    db_task.progress = 10.0
                    await session.commit()
                break
            except Exception as e:
                logger.error(f"Failed to update task status: {e}")
                await session.rollback()
                break
        
        # Send WebSocket update
        await self._broadcast_task_update(job.job_id, table_key, "processing", 10.0, None)
        
        db_connector = None
        try:
            # Get database connector
            async for session in get_db_session():
                db_connector = await create_db_connector_for_snapshot(job.snapshot_id, session)
                if db_connector:
                    await db_connector.connect()
                    break
            
            if not db_connector:
                raise Exception("Failed to create database connector")
            
            # Sample data from database
            table_task.progress = 30.0
            await self._broadcast_task_update(job.job_id, table_key, "processing", 30.0, None)
            
            sample_data = []
            try:
                full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name
                sample_data = await db_connector.sample_rows(full_table_name, limit=job.row_sample_limit)
            except Exception as e:
                logger.warning(f"Failed to sample data from {table_key}: {e}")
                # Continue without sample data
            
            # Get schema information
            table_task.progress = 50.0
            await self._broadcast_task_update(job.job_id, table_key, "processing", 50.0, None)
            
            schema_info = None
            async for session in get_db_session():
                try:
                    schema_info = await get_table_schema_with_relationships(
                        snapshot_id=job.snapshot_id,
                        schema_name=schema_name,
                        table_name=table_name,
                        session=session
                    )
                    break
                except Exception as e:
                    logger.warning(f"Failed to get schema info for {table_key}: {e}")
                    break
            
            if not schema_info:
                raise Exception("Failed to get schema information")
            
            # Compress/minify schema before passing to LLM
            schema_info = self._compress_schema(schema_info)
            
            # Initialize LLM service if needed
            if not self._llm_initialized:
                async for session in get_db_session():
                    try:
                        await self._llm_service.initialize(session)
                        self._llm_initialized = True
                        break
                    except Exception as e:
                        logger.error(f"Failed to initialize LLM service: {e}")
                        raise
            
            # Get active model
            async for session in get_db_session():
                try:
                    models = await self._llm_service.get_active_models(session)
                    if not models:
                        raise Exception("No active LLM models found")
                    
                    # Use first active model
                    model_id = models[0]["id"]
                    break
                except Exception as e:
                    logger.error(f"Failed to get active model: {e}")
                    raise
            
            # Get database type
            db_type = "Unknown"
            async for session in get_db_session():
                try:
                    result = await session.execute(
                        select(SchemaSnapshot).where(SchemaSnapshot.id == job.snapshot_id)
                    )
                    snapshot = result.scalar_one_or_none()
                    if snapshot:
                        conn_result = await session.execute(
                            select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
                        )
                        connection = conn_result.scalar_one_or_none()
                        if connection:
                            db_type = connection.db_type
                    break
                except Exception as e:
                    logger.warning(f"Failed to get database type: {e}")
                    break
            
            # Build prompt
            table_task.progress = 60.0
            await self._broadcast_task_update(job.job_id, table_key, "processing", 60.0, None)
            
            prompt = build_dictionary_prompt(
                job=job,
                table_task=table_task,
                schema_info=schema_info,
                sample_data=sample_data,
                db_type=db_type
            )
            
            # Call LLM
            table_task.progress = 70.0
            await self._broadcast_task_update(job.job_id, table_key, "processing", 70.0, None)
            
            async for session in get_db_session():
                try:
                    llm_response = await self._llm_service.generate_text(
                        session=session,
                        model_id=model_id,
                        prompt=prompt,
                        temperature=0.7
                    )
                    break
                except Exception as e:
                    logger.error(f"LLM generation failed: {e}")
                    raise
            
            # Parse LLM response
            table_task.progress = 80.0
            await self._broadcast_task_update(job.job_id, table_key, "processing", 80.0, None)
            
            dictionary_result = self._parse_llm_response(llm_response.text, schema_name, table_name)
            
            # Save dictionary results to database
            table_task.progress = 90.0
            await self._broadcast_task_update(job.job_id, table_key, "processing", 90.0, None)
            
            async for session in get_db_session():
                try:
                    await self._save_dictionary_results(
                        session=session,
                        snapshot_id=job.snapshot_id,
                        schema_name=schema_name,
                        table_name=table_name,
                        dictionary_result=dictionary_result,
                        sample_data=sample_data
                    )
                    break
                except Exception as e:
                    logger.error(f"Failed to save dictionary results: {e}")
                    raise
            
            # Mark task as done
            table_task.status = JobStatus.DONE
            table_task.progress = 100.0
            table_task.completed_at = datetime.now(timezone.utc)
            
            # Update in database
            async for session in get_db_session():
                try:
                    result = await session.execute(
                        select(AITableTask).where(
                            and_(
                                AITableTask.job_id == job.job_id,
                                AITableTask.table_name == table_key
                            )
                        )
                    )
                    db_task = result.scalar_one_or_none()
                    if db_task:
                        db_task.status = "done"
                        db_task.progress = 100.0
                        await session.commit()
                    break
                except Exception as e:
                    logger.error(f"Failed to update task status: {e}")
                    await session.rollback()
                    break
            
            # Update job completion
            await self._update_job_completion(job)
            
            # Send WebSocket update
            await self._broadcast_task_update(job.job_id, table_key, "done", 100.0, None)
            
            logger.info(f"Completed table task {table_key} for job {job.job_id}")
        
        finally:
            # Disconnect database connector
            if db_connector:
                try:
                    await db_connector.disconnect()
                except Exception as e:
                    logger.warning(f"Failed to disconnect database connector: {e}")

    def _compress_schema(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress/minify schema before passing to LLM
        
        Args:
            schema_info: Original schema information
            
        Returns:
            Compressed schema information
        """
        compressed = {
            "schema_name": schema_info.get("schema_name", ""),
            "table_name": schema_info.get("table_name", ""),
            "columns": []
        }
        
        # Compress columns - only keep essential info
        for col in schema_info.get("columns", [])[:100]:  # Limit to 100 columns
            compressed_col = {
                "name": col.get("name", ""),
                "data_type": col.get("data_type", ""),
                "is_primary_key": col.get("is_primary_key", False),
                "is_foreign_key": col.get("is_foreign_key", False)
            }
            compressed["columns"].append(compressed_col)
        
        # Keep relationships but limit
        relationships = schema_info.get("relationships", [])
        compressed["relationships"] = relationships[:50]  # Limit to 50 relationships
        
        return compressed

    def _parse_llm_response(self, response_text: str, schema_name: str, table_name: str) -> Dict[str, Any]:
        """
        Parse LLM response into dictionary result structure
        
        Expected format from prompt:
        {
          "table_name": "schema.table",
          "business_description": "...",
          "usage_notes": "...",
          "sample_insights": [...],
          "columns": [
            {
              "name": "col_name",
              "type": "data_type",
              "description": "...",
              "example": "...",
              "use_cases": [...],
              "synonyms": [...]
            }
          ]
        }
        
        Args:
            response_text: Raw LLM response text
            schema_name: Schema name
            table_name: Table name
            
        Returns:
            Parsed dictionary result
        """
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split('\n')
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line (```)
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = '\n'.join(lines)
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Ensure proper structure - convert to expected format
            if isinstance(result, dict):
                # If columns is a list, convert to dict format for easier processing
                if "columns" in result and isinstance(result["columns"], list):
                    columns_dict = {}
                    for col in result["columns"]:
                        if isinstance(col, dict) and "name" in col:
                            col_name = col["name"]
                            columns_dict[col_name] = col
                    result["columns"] = columns_dict
                return result
            else:
                # If it's a list, wrap in dict
                return {"tables": result if isinstance(result, list) else [result]}
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Return minimal structure on parse error
            return {
                "table_name": f"{schema_name}.{table_name}",
                "business_description": "Failed to parse LLM response",
                "columns": {}
            }

    async def _save_dictionary_results(
        self,
        session: AsyncSession,
        snapshot_id: int,
        schema_name: str,
        table_name: str,
        dictionary_result: Dict[str, Any],
        sample_data: List[Dict[str, Any]]
    ) -> None:
        """
        Save dictionary results to database
        
        Saves:
        - Table-level description
        - Column-level descriptions with examples and dictionary needs
        """
        try:
            # Delete all existing entries for this table (both table-level and column-level)
            # Simple approach: delete old, create new
            delete_result = await session.execute(
                delete(DataDictionary).where(
                    and_(
                        DataDictionary.schema_snapshot_id == snapshot_id,
                        DataDictionary.schema_name == schema_name,
                        DataDictionary.table_name == table_name
                    )
                )
            )
            deleted_count = delete_result.rowcount
            if deleted_count > 0:
                logger.debug(f"Deleted {deleted_count} existing dictionary entries for {schema_name}.{table_name}")
            
            # Extract table description (combine business_description and usage_notes)
            business_desc = dictionary_result.get("business_description", "")
            usage_notes = dictionary_result.get("usage_notes", "")
            table_description = f"{business_desc}\n{usage_notes}".strip() if usage_notes else business_desc
            if not table_description:
                table_description = dictionary_result.get("table_description") or dictionary_result.get("description", "")
            
            # Create new table-level dictionary entry
            table_dict = DataDictionary(
                schema_snapshot_id=snapshot_id,
                schema_name=schema_name,
                table_name=table_name,
                column_name=None,  # NULL for table-level
                description=table_description,
                example_values=None,
                synonyms=None,
                is_sensitive=False,
                is_ai_generated=True
            )
            session.add(table_dict)
            
            # Extract column descriptions
            columns = dictionary_result.get("columns", {})
            if isinstance(columns, dict):
                for col_name, col_info in columns.items():
                    if isinstance(col_info, dict):
                        col_description = col_info.get("description", "")
                        col_example = col_info.get("example", "")
                        
                        # Get real sample example from sample_data if available
                        real_example = None
                        if sample_data:
                            for row in sample_data:
                                if col_name in row and row[col_name] is not None:
                                    real_example = str(row[col_name])[:100]  # Limit length
                                    break
                        
                        # Use LLM example if no real example available
                        if not real_example and col_example:
                            real_example = col_example[:100]
                        
                        # Build example_values JSON array (single example as per requirements)
                        example_values_json = json.dumps([real_example]) if real_example else None
                        
                        # Extract synonyms from LLM response
                        synonyms_list = col_info.get("synonyms", [])
                        if not isinstance(synonyms_list, list):
                            synonyms_list = []
                        
                        # Convert synonyms list to comma-separated string (max 3 synonyms)
                        synonyms_str = None
                        if synonyms_list:
                            # Filter out empty strings and limit to 3
                            valid_synonyms = [s.strip() for s in synonyms_list[:3] if s and s.strip()]
                            if valid_synonyms:
                                synonyms_str = ", ".join(valid_synonyms)
                        
                        # Create new column-level dictionary entry
                        # (Old entries already deleted above)
                        col_dict = DataDictionary(
                            schema_snapshot_id=snapshot_id,
                            schema_name=schema_name,
                            table_name=table_name,
                            column_name=col_name,
                            description=col_description,
                            example_values=example_values_json,
                            synonyms=synonyms_str,  # Store real synonyms as comma-separated string
                            is_sensitive=False,
                            is_ai_generated=True
                        )
                        session.add(col_dict)
            
            await session.commit()
        
        except Exception as e:
            logger.error(f"Failed to save dictionary results: {e}")
            await session.rollback()
            raise

    async def _update_job_completion(self, job: DictionaryJob) -> None:
        """Update job completion status and progress"""
        async for session in get_db_session():
            try:
                result = await session.execute(
                    select(AIGenerationJob).where(AIGenerationJob.job_id == job.job_id)
                )
                db_job = result.scalar_one_or_none()
                
                if db_job:
                    # Count completed tables
                    completed_count = sum(
                        1 for t in job.table_tasks.values() 
                        if t.status == JobStatus.DONE
                    )
                    
                    db_job.completed_tables = completed_count
                    db_job.progress = (completed_count / db_job.total_tables * 100) if db_job.total_tables > 0 else 0.0
                    
                    # Check if job is complete
                    if completed_count >= db_job.total_tables:
                        db_job.status = "done"
                        job.status = JobStatus.DONE
                    
                    await session.commit()
                    
                    # Send job progress update
                    await self._broadcast_job_update(job.job_id, db_job.status, db_job.progress)
                break
            except Exception as e:
                logger.error(f"Failed to update job completion: {e}")
                await session.rollback()
                break

    async def _broadcast_task_update(
        self,
        job_id: str,
        table_name: str,
        status: str,
        progress: float,
        error: Optional[str]
    ) -> None:
        """Broadcast task update via WebSocket"""
        try:
            # Lazy import to avoid circular dependency
            from api.dictionary_job_router import manager
            
            await manager.broadcast_to_job(job_id, {
                "type": "table_status_update",
                "job_id": job_id,
                "table_name": table_name,
                "status": status,
                "progress": progress,
                "error": error,
                "timestamp": datetime.now(timezone.utc).timestamp()
            })
        except ImportError:
            # WebSocket manager not available, skip silently
            pass
        except Exception as e:
            logger.debug(f"Failed to broadcast task update: {e}")

    async def _broadcast_job_update(
        self,
        job_id: str,
        status: str,
        progress: float
    ) -> None:
        """Broadcast job update via WebSocket"""
        try:
            from api.dictionary_job_router import manager
            
            await manager.broadcast_to_job(job_id, {
                "type": "job_status_update",
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "timestamp": datetime.now(timezone.utc).timestamp()
            })
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Failed to broadcast job update: {e}")


# Global singleton instance
ai_dictionary_generator = AIDictionaryGenerator()
