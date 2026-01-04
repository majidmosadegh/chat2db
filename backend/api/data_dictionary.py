"""
Data Dictionary API Module
FastAPI endpoints for data dictionary operations
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json
import csv
import io
from datetime import datetime, timezone
from loguru import logger

from .database import get_db_session, decrypt_password, build_connection_string
from .db_models import DataDictionary, SchemaSnapshot, SchemaMetadata, DatabaseConnection, AIGenerationJob

# Import core utilities for safe logging
from core.config import LOG_ENCODING, LOG_ERROR_HANDLING

class DataDictionaryResponse(BaseModel):
    tables: List[Dict[str, Any]]

router = APIRouter()

async def get_actual_row_count(snapshot_id: int, schema_name: str, table_name: str, session: AsyncSession) -> int:
    """Get actual row count from the database"""
    try:
        # Get database connection for this snapshot
        result = await session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            return 0

        # Get connection details
        conn_result = await session.execute(
            select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
        )
        connection = conn_result.scalar_one_or_none()
        if not connection:
            return 0

        # Decrypt password
        if connection.password_encrypted and connection.password_encrypted.strip():
            password = decrypt_password(connection.password_encrypted)
        else:
            password = ""  # Empty password for Windows Authentication

        # Build connection string
        conn_string = build_connection_string(
            connection.db_type, connection.host, connection.port,
            connection.username, password, connection.database_name
        )

        # Execute count query based on database type
        if connection.db_type.lower() == "sqlserver":
            # For SQL Server, use synchronous connection
            def get_count_sync():
                try:
                    import pyodbc
                    if connection.username and password:
                        odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={connection.host},{connection.port};DATABASE={connection.database_name};UID={connection.username};PWD={password}"
                    else:
                        odbc_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={connection.host},{connection.port};DATABASE={connection.database_name};Trusted_Connection=yes"

                    conn = pyodbc.connect(odbc_conn_str, timeout=10)
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM [{schema_name}].[{table_name}]")
                    result = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    return int(result[0]) if result else 0
                except Exception as e:
                    logger.warning(f"Failed to get row count for {schema_name}.{table_name}: {e}")
                    return 0

            # Run in thread pool for async
            import asyncio
            return await asyncio.get_event_loop().run_in_executor(None, get_count_sync)
        else:
            # For other databases, return 0 for now
            logger.warning(f"Row count not supported for database type: {connection.db_type}")
            return 0

    except Exception as e:
        logger.error(f"Error getting row count for {schema_name}.{table_name}: {e}")
        return 0

@router.get("/", response_model=DataDictionaryResponse)
async def get_data_dictionary(
    snapshot_id: int = Query(..., description="Schema snapshot ID"),
    session: AsyncSession = Depends(get_db_session)
):
    """Get data dictionary for a schema snapshot"""
    try:
        # Get all tables
        tables_query = select(
            SchemaMetadata.schema_name,
            SchemaMetadata.table_name
        ).where(
            SchemaMetadata.schema_snapshot_id == snapshot_id
        ).distinct().order_by(
            SchemaMetadata.schema_name,
            SchemaMetadata.table_name
        )

        tables_result = await session.execute(tables_query)
        tables_data = tables_result.all()

        result_tables = []

        for table_row in tables_data:
            schema_name, table_name = table_row

            # Get actual row count from database
            row_count = await get_actual_row_count(snapshot_id, schema_name, table_name, session)

            # Get columns (exclude table-level records with empty column_name)
            columns_query = select(
                SchemaMetadata.column_name,
                SchemaMetadata.column_type,
                SchemaMetadata.is_primary_key,
                SchemaMetadata.is_foreign_key
            ).where(
                and_(
                    SchemaMetadata.schema_snapshot_id == snapshot_id,
                    SchemaMetadata.schema_name == schema_name,
                    SchemaMetadata.table_name == table_name,
                    SchemaMetadata.column_name.isnot(None),
                    SchemaMetadata.column_name != ''  # Exclude empty column names
                )
            ).order_by(SchemaMetadata.column_order)

            columns_result = await session.execute(columns_query)
            columns_data = columns_result.all()

            # Get AI-generated descriptions
            table_dict = {}
            column_dict = {}

            try:
                dict_query = select(DataDictionary).where(
                and_(
                        DataDictionary.schema_snapshot_id == snapshot_id,
                        DataDictionary.schema_name == schema_name,
                        DataDictionary.table_name == table_name
                    )
                ).order_by(DataDictionary.id.desc())

                dict_result = await session.execute(dict_query)
                dict_entries = dict_result.scalars().all()

                for entry in dict_entries:
                    # Direct access to attributes with error handling
                    try:
                        col_name = entry.column_name
                    except AttributeError:
                        # Silently skip invalid entries
                        continue
                    if col_name is None or col_name == '':  # Table-level
                        # Description is already a string from database, SQLAlchemy handles UTF-8
                        description = entry.description or ''
                        table_dict = {
                            'description': description,
                            'is_ai_generated': entry.is_ai_generated
                        }
                    else:  # Column-level
                        try:
                            example_values = json.loads(entry.example_values or '[]')
                        except Exception:
                            # Silently use empty list if parsing fails
                            example_values = []

                        # SQLAlchemy already handles UTF-8 decoding from database
                        description = entry.description or ''
                        synonyms = entry.synonyms or ''
                        
                        # Filter JSON (dict_needs) for backward compatibility with old AI-generated entries
                        # Old entries may have dict_needs stored in synonyms field (legacy behavior)
                        # New AI-generated entries will have real synonyms as comma-separated strings
                        # For user-created entries, synonyms should be kept as-is (comma-separated string)
                        if entry.is_ai_generated and synonyms:
                            synonyms_stripped = synonyms.strip()
                            if synonyms_stripped.startswith('{') or synonyms_stripped.startswith('['):
                                try:
                                    # Try to parse as JSON - if it succeeds, it's dict_needs (old format), not synonyms
                                    parsed = json.loads(synonyms)
                                    # If it's a dict or list, it's definitely dict_needs (legacy), not synonyms
                                    if isinstance(parsed, (dict, list)):
                                        synonyms = ''  # It's dict_needs (legacy), not real synonyms
                                except (json.JSONDecodeError, ValueError, TypeError):
                                    # Not valid JSON, so it's real synonyms - keep as is
                                    pass

                        column_dict[col_name] = {
                            'description': description,
                            'example_values': example_values,
                            'synonyms': synonyms,
                            'is_ai_generated': entry.is_ai_generated
                        }
            except Exception as e:
                # Only log critical errors, not every table/column processing issue
                logger.debug(f"Failed to get descriptions for {schema_name}.{table_name}: {e}")

            columns = []
            for col_row in columns_data:
                col_name, col_type, is_pk, is_fk = col_row

                constraints = []
                if is_pk:
                    constraints.append("PK")
                if is_fk:
                    constraints.append("FK")
                constraints_str = " + ".join(constraints) if constraints else ""

                col_dict = column_dict.get(col_name, {})
                try:
                    example_values = col_dict.get('example_values', [])
                except:
                    example_values = []

                columns.append({
                    'name': col_name,
                    'type': col_type,
                    'constraints': constraints_str,
                    'description': col_dict.get('description', ''),
                    'example_values': example_values,
                    'synonyms': col_dict.get('synonyms', ''),
                    'is_ai_generated': col_dict.get('is_ai_generated', False)
                })

            table_info = {
                'schema_name': schema_name,
                'table_name': table_name,
                'row_count': row_count,
                'description': table_dict.get('description', ''),
                'columns': columns,
                'is_ai_generated': table_dict.get('is_ai_generated', False)
            }

            result_tables.append(table_info)

        return DataDictionaryResponse(tables=result_tables)

    except Exception as e:
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            logger.error(f"Failed to get data dictionary: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        except Exception as log_error:
            logger.error(f"Failed to get data dictionary: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to get data dictionary")

# REMOVED: Old AI generation endpoint - use /api/ai/dictionary/generate instead


# Removed: get_table_sample_data - now using core.db_utils.get_table_sample_data

# AI Generation endpoint for compatibility with frontend
class AIDictionaryGenerateRequest(BaseModel):
    snapshot_id: int
    business_domain: str
    database_description: str
    target_user: str
    language: Optional[str] = "persian"
    additional_notes: Optional[str] = None

class AIDictionaryGenerateResponse(BaseModel):
    success: bool
    message: str
    job_id: Optional[str] = None

@router.post("/ai-generate", response_model=AIDictionaryGenerateResponse)
async def generate_ai_dictionary(
    request: AIDictionaryGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Generate AI dictionary for a database snapshot - compatibility endpoint"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator, GenerationScope

        # Global generation - get all tables
        scope = GenerationScope.FULL_SNAPSHOT
        target_names = []  # Empty means all tables
        target_description = "entire database"

        # Use the new service
        job_id = await ai_dictionary_generator.create_job(
            session=session,
            snapshot_id=request.snapshot_id,
            business_domain=request.business_domain,
            language=request.language or "persian",
            audience=request.target_user,
            tone="professional",
            scope=scope,
            target_names=target_names,
            row_sample_limit=5
        )

        # Start job in background
        background_tasks.add_task(ai_dictionary_generator.start_job, job_id)

        logger.info(f"AI Dictionary generation job {job_id} started in background")

        return AIDictionaryGenerateResponse(
            success=True,
            message="AI dictionary generation started successfully",
            job_id=job_id
        )

    except Exception as e:
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to start AI dictionary generation: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to start AI dictionary generation: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to start AI dictionary generation")

@router.get("/ai-generate/status/{job_id}")
async def get_ai_generation_status(job_id: str):
    """Get AI dictionary generation job status - compatibility endpoint"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator
        
        # Get job status from the new generator service
        job_data = await ai_dictionary_generator.get_job_status(job_id)
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        # Convert to expected format
        table_tasks = job_data.get("table_tasks", {})
        total_tables = len(table_tasks)
        completed_tables = sum(1 for t in table_tasks.values() if isinstance(t, dict) and t.get("status") == "done")
        
        # Find current processing table
        current_table = None
        for table_key, task_data in table_tasks.items():
            if isinstance(task_data, dict) and task_data.get("status") == "processing":
                current_table = table_key
                break

        # Normalize status for frontend compatibility
        job_status = job_data.get("status", "waiting")
        # Convert "done" to "completed" for frontend
        if job_status == "done":
            job_status = "completed"
        
        status_data = {
            "job_id": job_data.get("job_id"),
            "status": job_status,
            "total_tables": total_tables,
            "completed_tables": completed_tables,
            "current_table": current_table,
            "progress": table_tasks,
            "message": f"Processing {completed_tables} of {total_tables} tables"
        }

        return status_data

    except HTTPException:
        raise
    except Exception as e:
        # Safe error logging for Windows encoding
        logger.error(f"Failed to get job status for {job_id}: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to get job status: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to get job status: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to get job status")

@router.get("/ai-jobs")
async def get_ai_jobs_for_snapshot(snapshot_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get all AI generation jobs for a snapshot"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator
        from api.db_models import AIGenerationJob
        import json

        result = await session.execute(
            select(AIGenerationJob).where(
                AIGenerationJob.snapshot_id == snapshot_id
            ).order_by(AIGenerationJob.created_at.desc())
        )
        jobs = result.scalars().all()

        jobs_list = []
        for job in jobs:
            # Try to get fresh status from generator service
            job_data = await ai_dictionary_generator.get_job_status(job.job_id)
            
            if job_data:
                # Get current processing table
                current_table = None
                table_tasks = job_data.get("table_tasks", {})
                for table_key, task_data in table_tasks.items():
                    if isinstance(task_data, dict) and task_data.get("status") == "processing":
                        current_table = table_key
                        break
                
                # Calculate completed tables (only DONE, not FAILED)
                completed_tables = sum(
                    1 for t in table_tasks.values() 
                    if isinstance(t, dict) and t.get("status") == "done"
                )
                
                # Normalize status for frontend compatibility
                job_status = job_data.get("status", job.status)
                if job_status == "done":
                    job_status = "completed"
                
                jobs_list.append({
                    "job_id": job.job_id,
                    "snapshot_id": job.snapshot_id,
                    "status": job_status,
                    "total_tables": len(table_tasks) if table_tasks else job.total_tables,
                    "completed_tables": completed_tables,
                    "current_table": current_table,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    "business_domain": job_data.get("business_domain"),
                    "database_description": job_data.get("database_description"),
                    "target_user": job_data.get("audience"),
                    "language": job_data.get("language")
                })
            else:
                # Fallback to database data
                progress_data = json.loads(job.progress_data or "{}") if job.progress_data else {}
                # Normalize status for frontend compatibility
                job_status = job.status
                if job_status == "done":
                    job_status = "completed"
                
                jobs_list.append({
                    "job_id": job.job_id,
                    "snapshot_id": job.snapshot_id,
                    "status": job_status,
                    "total_tables": job.total_tables,
                    "completed_tables": job.completed_tables,
                    "current_table": job.current_table,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    "business_domain": progress_data.get("business_domain"),
                    "database_description": progress_data.get("database_description"),
                    "target_user": progress_data.get("audience"),
                    "language": progress_data.get("language")
                })

        return {"jobs": jobs_list}

    except Exception as e:
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to get AI jobs: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to get AI jobs: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to get AI jobs")


# Add missing endpoint for frontend compatibility
class AITableGenerateRequest(BaseModel):
    snapshot_id: int
    table_name: str
    column_name: Optional[str] = None  # Optional for column-specific generation
    business_domain: str
    database_description: str
    target_user: str
    language: Optional[str] = "persian"
    additional_notes: Optional[str] = None

@router.post("/table/ai-generate", response_model=AIDictionaryGenerateResponse)
async def generate_ai_dictionary_for_table(
    request: AITableGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Generate AI dictionary for a specific table or column - frontend compatibility endpoint"""
    try:
        # Import the new service
        from services.ai_dictionary_generator import ai_dictionary_generator, GenerationScope

        # Determine scope and target names based on request
        if request.column_name:
            # Column-specific generation
            scope = GenerationScope.COLUMN
            target_names = [request.column_name]
            target_description = f"column {request.table_name}.{request.column_name}"
        else:
            # Table generation
            scope = GenerationScope.TABLE
            target_names = [request.table_name]
            target_description = f"table {request.table_name}"

        # Use the new service
        job_id = await ai_dictionary_generator.create_job(
            session=session,
            snapshot_id=request.snapshot_id,
            business_domain=request.business_domain,
            language=request.language or "persian",
            audience=request.target_user,  # target_user maps to audience
            tone="professional",
            scope=scope,
            target_names=target_names,
            row_sample_limit=5
        )

        # Start job in background
        background_tasks.add_task(ai_dictionary_generator.start_job, job_id)

        return AIDictionaryGenerateResponse(
            success=True,
            message=f"AI dictionary generation started for {target_description}",
            job_id=job_id
        )

    except Exception as e:
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to start AI dictionary generation for table: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to start AI dictionary generation for table: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to start AI dictionary generation for table")


# Test endpoint
@router.get("/test")
async def test_endpoint():
    return {"message": "API is working"}

# Job management endpoints
@router.post("/ai-jobs/{job_id}/start")
async def start_ai_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    """Start/resume an AI generation job"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator

        logger.info(f"Attempting to start job {job_id}")
        success = await ai_dictionary_generator.start_job(job_id)
        if success:
            logger.info(f"Job {job_id} started successfully")
            return {"success": True, "message": f"Job {job_id} started successfully"}
        else:
            logger.warning(f"Job {job_id} not found or cannot be started")
            raise HTTPException(
                status_code=404, 
                detail=f"Job {job_id} not found or cannot be started. Job may already be processing, completed, or canceled."
            )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Safe error logging for Windows encoding
        logger.error(f"Failed to start job {job_id}: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to start job: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to start job: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to start job")


@router.post("/ai-jobs/{job_id}/pause")
async def pause_ai_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    """Pause an AI generation job"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator

        success = await ai_dictionary_generator.pause_job(job_id)
        if success:
            return {"success": True, "message": f"Job {job_id} paused successfully"}
        else:
            # Get job status to provide more informative error
            job_data = await ai_dictionary_generator.get_job_status(job_id)
            if job_data:
                current_status = job_data.get("status", "unknown")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Job {job_id} cannot be paused. Current status: {current_status}. Only PROCESSING or WAITING jobs can be paused."
                )
            else:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to pause job: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to pause job: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to pause job")


@router.post("/ai-jobs/{job_id}/resume")
async def resume_ai_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    """Resume a paused AI generation job"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator

        logger.info(f"Attempting to resume job {job_id}")
        success = await ai_dictionary_generator.resume_job(job_id)
        if success:
            logger.info(f"Job {job_id} resumed successfully")
            return {"success": True, "message": f"Job {job_id} resumed successfully"}
        else:
            logger.warning(f"Job {job_id} not found or cannot be resumed")
            raise HTTPException(
                status_code=404, 
                detail=f"Job {job_id} not found or cannot be resumed. Job may not be in paused status."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume job {job_id}: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to resume job: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to resume job: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to resume job")


@router.post("/ai-jobs/{job_id}/stop")
async def stop_ai_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    """Stop/cancel an AI generation job"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator

        logger.info(f"Attempting to stop job {job_id}")
        success = await ai_dictionary_generator.cancel_job(job_id)
        if success:
            logger.info(f"Job {job_id} canceled successfully")
            return {"success": True, "message": f"Job {job_id} canceled successfully"}
        else:
            logger.warning(f"Job {job_id} not found or cannot be canceled")
            raise HTTPException(
                status_code=404, 
                detail=f"Job {job_id} not found or cannot be canceled. Job may already be completed or canceled."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop job {job_id}: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to cancel job: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to cancel job: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to cancel job")

@router.delete("/ai-jobs/{job_id}")
async def delete_ai_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    """Delete an AI generation job from database"""
    try:
        from api.db_models import AIGenerationJob
        from sqlalchemy import select, delete

        # First cancel the job if it's active
        from services.ai_dictionary_generator import ai_dictionary_generator
        await ai_dictionary_generator.cancel_job(job_id)

        # Delete from database
        result = await session.execute(
            delete(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
        )
        await session.commit()

        if result.rowcount > 0:
            return {"success": True, "message": f"Job {job_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to delete job: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to delete job: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to delete job")

@router.delete("/ai-jobs")
async def delete_all_ai_jobs(session: AsyncSession = Depends(get_db_session)):
    """Delete all AI generation jobs from database"""
    try:
        from api.db_models import AIGenerationJob
        from sqlalchemy import delete

        # Cancel all active jobs first
        from services.ai_dictionary_generator import ai_dictionary_generator
        for job_id in list(ai_dictionary_generator._jobs.keys()):
            try:
                await ai_dictionary_generator.cancel_job(job_id)
            except:
                pass

        # Delete all from database
        result = await session.execute(delete(AIGenerationJob))
        await session.commit()

        deleted_count = result.rowcount
        return {
            "success": True,
            "message": f"Deleted {deleted_count} AI generation job(s) successfully"
        }

    except Exception as e:
        await session.rollback()
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to delete jobs: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to delete jobs: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to delete jobs")

class DataDictionaryEntryRequest(BaseModel):
    schema_snapshot_id: int
    schema_name: str
    table_name: str
    column_name: Optional[str] = None
    description: Optional[str] = None
    example_values: Optional[List[str]] = None
    synonyms: Optional[str] = None
    is_sensitive: bool = False
    is_ai_generated: bool = False

@router.post("/")
async def create_or_update_dictionary_entry(
    request: DataDictionaryEntryRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Create or update a data dictionary entry"""
    try:
        from sqlalchemy import update as sql_update
        
        # Check if entry exists
        existing_query = select(DataDictionary).where(
            and_(
                DataDictionary.schema_snapshot_id == request.schema_snapshot_id,
                DataDictionary.schema_name == request.schema_name,
                DataDictionary.table_name == request.table_name,
                DataDictionary.column_name == (request.column_name if request.column_name else None)
            )
        )
        
        result = await session.execute(existing_query)
        existing_entry = result.scalar_one_or_none()
        
        # Prepare example_values as JSON
        example_values_json = None
        if request.example_values:
            example_values_json = json.dumps(request.example_values, ensure_ascii=False)
        
        if existing_entry:
            # Update existing entry
            existing_entry.description = request.description
            existing_entry.example_values = example_values_json
            existing_entry.synonyms = request.synonyms
            existing_entry.is_sensitive = request.is_sensitive
            existing_entry.is_ai_generated = request.is_ai_generated
            existing_entry.updated_at = datetime.now(timezone.utc)
            await session.commit()
            
            return {
                "success": True,
                "message": "Dictionary entry updated successfully",
                "id": existing_entry.id
            }
        else:
            # Create new entry
            new_entry = DataDictionary(
                schema_snapshot_id=request.schema_snapshot_id,
                schema_name=request.schema_name,
                table_name=request.table_name,
                column_name=request.column_name,
                description=request.description,
                example_values=example_values_json,
                synonyms=request.synonyms,
                is_sensitive=request.is_sensitive,
                is_ai_generated=request.is_ai_generated
            )
            session.add(new_entry)
            await session.commit()
            await session.refresh(new_entry)
            
            return {
                "success": True,
                "message": "Dictionary entry created successfully",
                "id": new_entry.id
            }
            
    except Exception as e:
        await session.rollback()
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            logger.error(f"Failed to save dictionary entry: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Failed to save dictionary entry: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to save dictionary entry: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to save dictionary entry")

@router.delete("/clean")
async def clean_all_dictionary_data(session: AsyncSession = Depends(get_db_session)):
    """Delete all AI generation jobs and dictionary entries (for testing/cleanup)"""
    try:
        from api.db_models import AIGenerationJob, DataDictionary, AITableTask
        from sqlalchemy import delete

        # Cancel all active jobs first
        from services.ai_dictionary_generator import ai_dictionary_generator
        for job_id in list(ai_dictionary_generator._jobs.keys()):
            try:
                await ai_dictionary_generator.cancel_job(job_id)
            except:
                pass

        # Delete all AI jobs (table tasks will be deleted by cascade)
        jobs_result = await session.execute(delete(AIGenerationJob))
        jobs_deleted = jobs_result.rowcount

        # Delete all dictionary entries (especially AI-generated ones)
        dict_result = await session.execute(delete(DataDictionary))
        dict_deleted = dict_result.rowcount

        await session.commit()

        return {
            "success": True,
            "message": f"Cleaned all dictionary data: {jobs_deleted} job(s) and {dict_deleted} dictionary entry/entries deleted"
        }

    except Exception as e:
        await session.rollback()
        # Safe error logging for Windows encoding
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to clean dictionary data: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to clean dictionary data: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to clean dictionary data")

@router.get("/export")
async def export_data_dictionary_csv(
    snapshot_id: int = Query(..., description="Schema snapshot ID"),
    session: AsyncSession = Depends(get_db_session)
):
    """Export data dictionary to CSV format"""
    try:
        # Get all dictionary entries for this snapshot
        dict_query = select(DataDictionary).where(
            DataDictionary.schema_snapshot_id == snapshot_id
        ).order_by(
            DataDictionary.schema_name,
            DataDictionary.table_name,
            DataDictionary.column_name
        )
        
        dict_result = await session.execute(dict_query)
        dict_entries = dict_result.scalars().all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Schema Name",
            "Table Name",
            "Column Name",
            "Description",
            "Example Values",
            "Synonyms",
            "Is AI Generated",
            "Is Sensitive",
            "Created At",
            "Updated At"
        ])
        
        # Write data rows
        for entry in dict_entries:
            # Handle example_values (JSON array)
            example_values_str = ""
            if entry.example_values:
                try:
                    example_list = json.loads(entry.example_values)
                    if isinstance(example_list, list):
                        example_values_str = "; ".join(str(v) for v in example_list if v)
                except:
                    example_values_str = str(entry.example_values)
            
            # Handle synonyms (filter JSON for backward compatibility)
            synonyms_str = entry.synonyms or ""
            if entry.is_ai_generated and synonyms_str:
                synonyms_stripped = synonyms_str.strip()
                if synonyms_stripped.startswith('{') or synonyms_stripped.startswith('['):
                    try:
                        parsed = json.loads(synonyms_str)
                        if isinstance(parsed, (dict, list)):
                            synonyms_str = ""  # It's dict_needs (legacy), not real synonyms
                    except:
                        pass
            
            # Format dates
            created_at_str = entry.created_at.isoformat() if entry.created_at else ""
            updated_at_str = entry.updated_at.isoformat() if entry.updated_at else ""
            
            writer.writerow([
                entry.schema_name or "",
                entry.table_name or "",
                entry.column_name or "",  # Empty for table-level entries
                entry.description or "",
                example_values_str,
                synonyms_str,
                "Yes" if entry.is_ai_generated else "No",
                "Yes" if entry.is_sensitive else "No",
                created_at_str,
                updated_at_str
            ])
        
        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Get snapshot name for filename
        snapshot_result = await session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        snapshot_name = snapshot.name if snapshot else f"snapshot_{snapshot_id}"
        
        # Clean filename (remove invalid characters)
        safe_filename = "".join(c for c in snapshot_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_filename = safe_filename.replace(' ', '_')
        filename = f"data_dictionary_{safe_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Return CSV file
        return Response(
            content=csv_content.encode('utf-8-sig'),  # UTF-8 with BOM for Excel compatibility
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            logger.error(f"Failed to export data dictionary: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Failed to export data dictionary: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to export data dictionary: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to export data dictionary")

@router.get("/test")
def test_endpoint():
    """Test endpoint"""
    return {"message": "Data dictionary API works"}