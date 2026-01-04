"""
Use Case Maturation API

Complete flow for continuous use case maturation:
1. Generate questions based on use case knowledge
2. Generate SQL queries
3. Execute and validate queries
4. Store successful question-query pairs
5. Allow user approval/rejection
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json
from datetime import datetime
from loguru import logger

from .db_models import (
    UseCase, MaturationSession, MaturationQuestion,
    SchemaSnapshot, LLMModel, FineTuningSession, FineTuningQuestion,
    DatabaseConnection, get_db_session
)
from services.maturation_engine import maturation_engine
from core.config import LOG_ENCODING, LOG_ERROR_HANDLING
from llm import ModelConnector, LLMRequest, Message, MessageRole
from llm.registry import initialize_registry, ConfigRegistryLoader
from .database import decrypt_api_key
from services.db_connector_utils import create_db_connector_for_snapshot

router = APIRouter()


# Request/Response Models
class MaturationSessionCreate(BaseModel):
    use_case_id: int
    language: str = "persian"
    questions_per_batch: int = 5
    max_retries_per_question: int = 3


class MaturationSessionResponse(BaseModel):
    id: int
    use_case_id: int
    schema_snapshot_id: int
    status: str
    current_step: Optional[str]
    language: str
    questions_per_batch: int
    total_questions_generated: int
    total_questions_processed: int
    successful_questions: int
    failed_questions: int
    stored_questions: int
    success_rate: Optional[float]
    created_at: datetime
    updated_at: datetime


class MaturationQuestionResponse(BaseModel):
    id: int
    question_index: int
    question_text: str
    is_user_edited: bool
    generated_sql: Optional[str]
    execution_status: Optional[str]
    execution_result: Optional[Any]
    execution_error: Optional[str]
    execution_duration_ms: Optional[int]
    retry_count: int
    user_approval: Optional[str]
    user_feedback: Optional[str]
    is_stored: bool
    created_at: datetime


class QuestionApprovalRequest(BaseModel):
    approval: str  # "approved" or "rejected"
    feedback: Optional[str] = None


class MaturationStatusResponse(BaseModel):
    session: MaturationSessionResponse
    questions: List[MaturationQuestionResponse]
    context_loaded: bool
    existing_test_results: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None


# Helper function to create background database session
def create_background_session():
    """Create a new database session factory for background tasks"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker
    from config.config import DATABASE_URL

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return async_session


# Endpoints

@router.delete("/use-cases/{use_case_id}/fine-tuning-sessions")
async def delete_fine_tuning_sessions(
    use_case_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Delete all fine-tuning sessions for a use case"""
    logger.info(f"[MATURATION] Deleting fine-tuning sessions for use case {use_case_id}")
    
    try:
        # Get all fine-tuning sessions for this use case
        sessions_result = await session.execute(
            select(FineTuningSession).where(FineTuningSession.use_case_id == use_case_id)
        )
        sessions = sessions_result.scalars().all()
        
        deleted_count = 0
        for ft_session in sessions:
            # Delete questions first (cascade should handle this, but being explicit)
            await session.execute(
                delete(FineTuningQuestion).where(FineTuningQuestion.session_id == ft_session.id)
            )
            # Delete session
            await session.delete(ft_session)
            deleted_count += 1
        
        await session.commit()
        
        logger.info(f"[MATURATION] Deleted {deleted_count} fine-tuning sessions")
        return {"message": f"Deleted {deleted_count} fine-tuning session(s)", "deleted_count": deleted_count}
    
    except Exception as e:
        await session.rollback()
        logger.error(f"[MATURATION] Failed to delete fine-tuning sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete fine-tuning sessions: {str(e)}")


@router.post("/sessions", response_model=MaturationSessionResponse)
async def create_maturation_session(
    request: MaturationSessionCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new maturation session for a use case"""
    logger.info(f"[MATURATION] Creating session for use case {request.use_case_id}")
    
    try:
        # Delete any existing fine-tuning sessions first
        sessions_result = await session.execute(
            select(FineTuningSession).where(FineTuningSession.use_case_id == request.use_case_id)
        )
        sessions = sessions_result.scalars().all()
        
        for ft_session in sessions:
            # Delete questions first
            await session.execute(
                delete(FineTuningQuestion).where(FineTuningQuestion.session_id == ft_session.id)
            )
            # Delete session
            await session.delete(ft_session)
        
        await session.flush()
        
        # Validate use case
        result = await session.execute(
            select(UseCase).where(UseCase.id == request.use_case_id)
        )
        use_case = result.scalar_one_or_none()
        if not use_case:
            raise HTTPException(status_code=404, detail="Use case not found")
        
        # Get active LLM model
        model_result = await session.execute(
            select(LLMModel).where(LLMModel.is_active == True)
        )
        active_model = model_result.scalar_one_or_none()
        if not active_model:
            raise HTTPException(status_code=400, detail="No active LLM model found")
        
        # Create session
        maturation_session = MaturationSession(
            use_case_id=request.use_case_id,
            schema_snapshot_id=use_case.schema_snapshot_id,
            model_id=active_model.id,
            language=request.language,
            questions_per_batch=request.questions_per_batch,
            max_retries_per_question=request.max_retries_per_question,
            status="created",
            current_step="loading_context"
        )
        
        session.add(maturation_session)
        await session.commit()
        await session.refresh(maturation_session)
        
        logger.info(f"[MATURATION] Created session {maturation_session.id}")
        
        return MaturationSessionResponse(
            id=maturation_session.id,
            use_case_id=maturation_session.use_case_id,
            schema_snapshot_id=maturation_session.schema_snapshot_id,
            status=maturation_session.status,
            current_step=maturation_session.current_step,
            language=maturation_session.language,
            questions_per_batch=maturation_session.questions_per_batch,
            total_questions_generated=maturation_session.total_questions_generated,
            total_questions_processed=maturation_session.total_questions_processed,
            successful_questions=maturation_session.successful_questions,
            failed_questions=maturation_session.failed_questions,
            stored_questions=maturation_session.stored_questions,
            success_rate=maturation_session.success_rate,
            created_at=maturation_session.created_at,
            updated_at=maturation_session.updated_at
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MATURATION] Failed to create session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.post("/sessions/{session_id}/start")
async def start_maturation(
    session_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Start the maturation process"""
    logger.info(f"[MATURATION] Starting session {session_id}")
    
    try:
        # Validate session
        result = await session.execute(
            select(MaturationSession).where(MaturationSession.id == session_id)
        )
        maturation_session = result.scalar_one_or_none()
        if not maturation_session:
            logger.error(f"[MATURATION] Session {session_id} not found")
            raise HTTPException(status_code=404, detail="Maturation session not found")
        
        if maturation_session.status not in ["created", "paused"]:
            logger.warning(f"[MATURATION] Session {session_id} cannot be started from status: {maturation_session.status}")
            raise HTTPException(
                status_code=400,
                detail=f"Session cannot be started from status: {maturation_session.status}"
            )
        
        # Update status
        maturation_session.status = "generating"
        maturation_session.current_step = "initializing"
        await session.commit()
        logger.info(f"[MATURATION] Session {session_id} status updated to 'generating'")
        
        # Start background task
        background_tasks.add_task(process_maturation_session, session_id)
        logger.info(f"[MATURATION] Background task scheduled for session {session_id}")
        
        return {"message": "Maturation process started", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MATURATION] Failed to start session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


async def test_existing_queries_internal(
    use_case_id: int,
    session: AsyncSession
) -> Dict[str, Any]:
    """Internal function to test existing queries (used in maturation process)"""
    # Get use case
    result = await session.execute(
        select(UseCase).where(UseCase.id == use_case_id)
    )
    use_case = result.scalar_one_or_none()
    if not use_case:
        return {
            "total_queries": 0,
            "tested_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "results": []
        }
    
    # Get existing questions and queries
    existing_questions = []
    existing_queries = []
    try:
        existing_questions = json.loads(use_case.example_questions or "[]")
        existing_queries = json.loads(use_case.example_queries or "[]")
    except:
        pass
    
    if not existing_queries:
        return {
            "total_queries": 0,
            "tested_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "results": []
        }
    
    # Test each query
    results = []
    successful_count = 0
    failed_count = 0
    
    for idx, (question, query) in enumerate(zip(existing_questions, existing_queries)):
        if not query:
            continue
        
        try:
            # Execute query using maturation engine's execute_sql method
            success, result, error = await maturation_engine.execute_sql(
                query,
                use_case.schema_snapshot_id,
                session
            )
            
            if success:
                successful_count += 1
                results.append({
                    "index": idx,
                    "question": question if idx < len(existing_questions) else None,
                    "query": query,
                    "status": "success",
                    "result_count": len(result) if isinstance(result, list) else 0,
                    "error": None,
                    "sample_result": result[:3] if isinstance(result, list) and len(result) > 0 else None
                })
            else:
                failed_count += 1
                results.append({
                    "index": idx,
                    "question": question if idx < len(existing_questions) else None,
                    "query": query,
                    "status": "failed",
                    "result_count": 0,
                    "error": error,
                    "sample_result": None
                })
        except Exception as e:
            failed_count += 1
            results.append({
                "index": idx,
                "question": question if idx < len(existing_questions) else None,
                "query": query,
                "status": "error",
                "result_count": 0,
                "error": str(e),
                "sample_result": None
            })
    
    return {
        "total_queries": len(existing_queries),
        "tested_queries": len(results),
        "successful_queries": successful_count,
        "failed_queries": failed_count,
        "success_rate": successful_count / len(results) if results else 0,
        "results": results
    }


async def analyze_use_case_queries_internal(
    use_case_id: int,
    session: AsyncSession
) -> Dict[str, Any]:
    """Internal function to analyze queries (used in maturation process)"""
    # Test all queries
    test_result = await test_existing_queries_internal(use_case_id, session)
    
    # Analyze results
    failed_queries = [r for r in test_result["results"] if r["status"] != "success"]
    successful_queries = [r for r in test_result["results"] if r["status"] == "success"]
    
    recommendations = []
    
    if failed_queries:
        recommendations.append({
            "type": "remove_failed",
            "priority": "high",
            "message": f"{len(failed_queries)} query(ies) failed execution. Consider removing them.",
            "failed_indices": [r["index"] for r in failed_queries],
            "failed_queries": [
                {
                    "index": r["index"],
                    "question": r["question"],
                    "error": r["error"]
                }
                for r in failed_queries
            ]
        })
    
    if test_result["tested_queries"] > 0 and test_result["success_rate"] < 0.5:
        recommendations.append({
            "type": "low_success_rate",
            "priority": "high",
            "message": f"Success rate is {test_result['success_rate']:.1%}. Most queries are failing.",
            "suggestion": "Review and regenerate queries based on latest schema and sample data."
        })
    
    if len(successful_queries) < 3:
        recommendations.append({
            "type": "insufficient_queries",
            "priority": "medium",
            "message": f"Only {len(successful_queries)} successful query(ies). Use case needs at least 3.",
            "suggestion": "Run maturation process to generate more successful queries."
        })
    
    return {
        "use_case_id": use_case_id,
        "summary": {
            "total_queries": test_result["total_queries"],
            "successful": test_result["successful_queries"],
            "failed": test_result["failed_queries"],
            "success_rate": test_result["success_rate"]
        },
        "recommendations": recommendations,
        "detailed_results": test_result["results"]
    }


async def process_maturation_session(session_id: int):
    """Background task to process maturation session"""
    logger.info(f"[MATURATION] Background task started for session {session_id}")
    async_session = create_background_session()
    
    try:
        async with async_session() as session:
            try:
                logger.info(f"[MATURATION] Processing session {session_id}")
                
                # Get session
                result = await session.execute(
                    select(MaturationSession).where(MaturationSession.id == session_id)
                )
                maturation_session = result.scalar_one_or_none()
                if not maturation_session:
                    logger.error(f"[MATURATION] Session {session_id} not found")
                    return
                
                # Get use case
                use_case_result = await session.execute(
                    select(UseCase).where(UseCase.id == maturation_session.use_case_id)
                )
                use_case = use_case_result.scalar_one_or_none()
                if not use_case:
                    logger.error(f"[MATURATION] Use case {maturation_session.use_case_id} not found")
                    maturation_session.status = "failed"
                    await session.commit()
                    return
                
                # Step 1: Test existing queries first
                maturation_session.current_step = "testing_existing_queries"
                maturation_session.status = "processing"
                await session.commit()
                
                # Test existing queries in use case
                existing_test_results = await test_existing_queries_internal(
                    use_case.id,
                    session
                )
                logger.info(
                    f"[MATURATION] Tested existing queries: "
                    f"{existing_test_results['successful_queries']} successful, "
                    f"{existing_test_results['failed_queries']} failed"
                )
                
                # Store test results in session metadata
                session_metadata = {}
                try:
                    if maturation_session.session_metadata:
                        session_metadata = json.loads(maturation_session.session_metadata)
                except:
                    pass
                session_metadata["existing_test_results"] = existing_test_results
                maturation_session.session_metadata = json.dumps(session_metadata, ensure_ascii=False)
                await session.commit()
                
                # Load context
                maturation_session.current_step = "loading_context"
                await session.commit()
                
                context = await maturation_engine.load_context(
                    maturation_session.schema_snapshot_id,
                    session
                )
                
                # Generate questions
                maturation_session.current_step = "generating_questions"
                await session.commit()
                
                questions = await maturation_engine.generate_questions(
                    use_case,
                    context,
                    count=maturation_session.questions_per_batch,
                    language=maturation_session.language,
                    session=session,
                    session_id=session_id  # Pass session_id to check for duplicates in current session
                )
                
                maturation_session.total_questions_generated += len(questions)
                await session.commit()
                
                # Get last processed index from session metadata (for resume support)
                session_metadata = {}
                try:
                    if maturation_session.session_metadata:
                        session_metadata = json.loads(maturation_session.session_metadata)
                except:
                    pass
                last_processed_index = session_metadata.get("last_processed_question_index", -1)
                
                # Process each question
                for idx, question_text in enumerate(questions):
                    try:
                        # Check if paused
                        await session.refresh(maturation_session)
                        if maturation_session.status == "paused":
                            logger.info(f"[MATURATION] Session {session_id} paused at question {idx}")
                            # Save current index for resume
                            session_metadata["last_processed_question_index"] = idx - 1
                            maturation_session.session_metadata = json.dumps(session_metadata, ensure_ascii=False)
                            await session.commit()
                            return
                        
                        # Skip if already processed (resume support)
                        if idx <= last_processed_index:
                            logger.info(f"[MATURATION] Skipping question {idx} (already processed)")
                            continue
                        
                        # Calculate progress percentage
                        total_steps = len(questions) + 2  # questions + testing_existing + analyzing
                        current_step_num = idx + 1 + 1  # +1 for testing_existing, +1 for current question
                        progress_percentage = (current_step_num / total_steps) * 100
                        
                        # Calculate ETA (estimated time to arrival)
                        if maturation_session.total_questions_processed > 0 and maturation_session.average_execution_time_ms:
                            avg_time_seconds = maturation_session.average_execution_time_ms / 1000.0
                            remaining_questions = len(questions) - idx
                            estimated_seconds = remaining_questions * avg_time_seconds
                            eta_minutes = int(estimated_seconds / 60)
                            eta_seconds = int(estimated_seconds % 60)
                            eta_text = f"{eta_minutes}m {eta_seconds}s" if eta_minutes > 0 else f"{eta_seconds}s"
                        else:
                            eta_text = "calculating..."
                        
                        maturation_session.current_step = f"processing_question_{idx + 1}_of_{len(questions)} ({progress_percentage:.1f}% - ETA: {eta_text})"
                        
                        # Update last processed index and progress
                        session_metadata["last_processed_question_index"] = idx
                        session_metadata["progress_percentage"] = progress_percentage
                        session_metadata["eta"] = eta_text
                        maturation_session.session_metadata = json.dumps(session_metadata, ensure_ascii=False)
                        await session.commit()
                        
                        # Create question record
                        max_index_result = await session.execute(
                            select(func.max(MaturationQuestion.question_index))
                            .where(MaturationQuestion.session_id == session_id)
                        )
                        max_index = max_index_result.scalar() or -1
                        
                        maturation_question = MaturationQuestion(
                            session_id=session_id,
                            question_index=max_index + 1,
                            question_text=question_text,
                            execution_status="pending"
                        )
                        session.add(maturation_question)
                        await session.flush()
                        
                        # Update status to generating_sql
                        maturation_question.execution_status = "generating_sql"
                        await session.commit()
                        
                        # Process question
                        import time
                        start_time = time.time()
                        
                        processed = await maturation_engine.process_question(
                            question_text,
                            use_case,
                            context,
                            maturation_session.schema_snapshot_id,
                            maturation_session.language,
                            session
                        )
                        
                        execution_duration = int((time.time() - start_time) * 1000)
                        
                        # Update average execution time for ETA calculation
                        if maturation_session.total_questions_processed > 0:
                            current_avg = maturation_session.average_execution_time_ms or 0
                            new_avg = ((current_avg * (maturation_session.total_questions_processed - 1)) + execution_duration) / maturation_session.total_questions_processed
                            maturation_session.average_execution_time_ms = new_avg
                        else:
                            maturation_session.average_execution_time_ms = execution_duration
                        
                        # Update question with results
                        maturation_question.generated_sql = processed.generated_sql
                        maturation_question.execution_status = processed.execution_status
                        maturation_question.execution_error = processed.execution_error
                        maturation_question.retry_count = processed.retry_count
                        maturation_question.execution_duration_ms = execution_duration
                        
                        if processed.execution_result:
                            # Limit result size for storage
                            result_data = processed.execution_result
                            if isinstance(result_data, list) and len(result_data) > 50:
                                result_data = result_data[:50]  # Limit to 50 rows
                            maturation_question.execution_result = json.dumps(
                                result_data,
                                ensure_ascii=False
                            )
                        
                        if processed.execution_status == "success":
                            maturation_session.successful_questions += 1
                        else:
                            maturation_session.failed_questions += 1
                        
                        maturation_session.total_questions_processed += 1
                        
                        # Calculate success rate
                        if maturation_session.total_questions_processed > 0:
                            maturation_session.success_rate = (
                                maturation_session.successful_questions /
                                maturation_session.total_questions_processed
                            )
                        
                        await session.commit()
                        logger.info(
                            f"[MATURATION] Question {idx + 1}/{len(questions)} processed: "
                            f"status={processed.execution_status}, retries={processed.retry_count}"
                        )
                        
                    except Exception as e:
                        logger.error(f"[MATURATION] Error processing question {idx + 1}: {e}", exc_info=True)
                        # Mark question as failed
                        try:
                            maturation_question.execution_status = "error"
                            maturation_question.execution_error = str(e)
                            maturation_session.failed_questions += 1
                            maturation_session.total_questions_processed += 1
                            await session.commit()
                        except:
                            pass
                        # Continue with next question
                        continue
                
                # Step 3: Final analysis and recommendations
                maturation_session.current_step = "analyzing_results"
                await session.commit()
                
                # Get final analysis
                final_analysis = await analyze_use_case_queries_internal(
                    use_case.id,
                    session
                )
                
                # Store analysis in session metadata
                session_metadata = {}
                try:
                    if maturation_session.session_metadata:
                        session_metadata = json.loads(maturation_session.session_metadata)
                except:
                    pass
                session_metadata["analysis"] = final_analysis
                maturation_session.session_metadata = json.dumps(session_metadata, ensure_ascii=False)
                
                logger.info(
                    f"[MATURATION] Final analysis: "
                    f"Total queries: {final_analysis['summary']['total_queries']}, "
                    f"Success rate: {final_analysis['summary']['success_rate']:.1%}, "
                    f"Recommendations: {len(final_analysis['recommendations'])}"
                )
                
                # Update session status
                maturation_session.status = "completed"
                maturation_session.current_step = None
                await session.commit()
                
                logger.info(
                    f"[MATURATION] Session {session_id} completed: "
                    f"{maturation_session.successful_questions} successful, "
                    f"{maturation_session.failed_questions} failed"
                )
                
            except Exception as e:
                logger.error(f"[MATURATION] Error processing session {session_id}: {e}", exc_info=True)
                try:
                    await session.refresh(maturation_session)
                    maturation_session.status = "failed"
                    maturation_session.current_step = f"error: {str(e)[:100]}"
                    await session.commit()
                except Exception as commit_error:
                    logger.error(f"[MATURATION] Failed to update session status: {commit_error}", exc_info=True)
    except Exception as outer_error:
            logger.error(f"[MATURATION] Critical error in background task for session {session_id}: {outer_error}", exc_info=True)
            # Try to update session status even if we can't create a session
            try:
                async_session = create_background_session()
                async with async_session() as error_session:
                    result = await error_session.execute(
                        select(MaturationSession).where(MaturationSession.id == session_id)
                    )
                    error_maturation_session = result.scalar_one_or_none()
                    if error_maturation_session:
                        error_maturation_session.status = "failed"
                        error_maturation_session.current_step = f"critical_error: {str(outer_error)[:100]}"
                        await error_session.commit()
            except Exception as final_error:
                logger.error(f"[MATURATION] Failed to update session status after critical error: {final_error}", exc_info=True)


@router.get("/sessions/use-case/{use_case_id}")
async def get_sessions_for_use_case(
    use_case_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Get all maturation sessions for a use case"""
    result = await session.execute(
        select(MaturationSession)
        .where(MaturationSession.use_case_id == use_case_id)
        .order_by(MaturationSession.created_at.desc())
    )
    sessions = result.scalars().all()
    
    return {
        "sessions": [
            {
                "id": s.id,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "total_questions_generated": s.total_questions_generated,
                "successful_questions": s.successful_questions,
                "stored_questions": s.stored_questions
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}/status", response_model=MaturationStatusResponse)
async def get_maturation_status(
    session_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Get current status of maturation session"""
    # Get session
    result = await session.execute(
        select(MaturationSession).where(MaturationSession.id == session_id)
    )
    maturation_session = result.scalar_one_or_none()
    if not maturation_session:
        raise HTTPException(status_code=404, detail="Maturation session not found")
    
    # Get questions
    questions_result = await session.execute(
        select(MaturationQuestion)
        .where(MaturationQuestion.session_id == session_id)
        .order_by(MaturationQuestion.question_index)
    )
    questions = questions_result.scalars().all()
    
    # Format questions
    question_responses = []
    for q in questions:
        execution_result = None
        if q.execution_result:
            try:
                execution_result = json.loads(q.execution_result)
            except:
                execution_result = q.execution_result
        
        question_responses.append(MaturationQuestionResponse(
            id=q.id,
            question_index=q.question_index,
            question_text=q.question_text,
            is_user_edited=q.is_user_edited,
            generated_sql=q.generated_sql,
            execution_status=q.execution_status,
            execution_result=execution_result,
            execution_error=q.execution_error,
            execution_duration_ms=q.execution_duration_ms,
            retry_count=q.retry_count,
            user_approval=q.user_approval,
            user_feedback=q.user_feedback,
            is_stored=q.is_stored,
            created_at=q.created_at
        ))
    
    # Get existing queries test results if session is testing or completed
    existing_test_results = None
    analysis = None
    try:
        if maturation_session.current_step and (
            "testing_existing_queries" in str(maturation_session.current_step) or
            "analyzing_results" in str(maturation_session.current_step) or
            maturation_session.status == "completed"
        ):
            try:
                existing_test_results = await test_existing_queries_internal(
                    maturation_session.use_case_id,
                    session
                )
                analysis = await analyze_use_case_queries_internal(
                    maturation_session.use_case_id,
                    session
                )
            except Exception as e:
                logger.warning(f"[MATURATION] Failed to get test results: {e}", exc_info=True)
                # Set empty results on error
                existing_test_results = None
                analysis = None
    except Exception as e:
        logger.error(f"[MATURATION] Error in get_maturation_status: {e}", exc_info=True)
        # Continue without test results
        existing_test_results = None
        analysis = None
    
    return MaturationStatusResponse(
        session=MaturationSessionResponse(
            id=maturation_session.id,
            use_case_id=maturation_session.use_case_id,
            schema_snapshot_id=maturation_session.schema_snapshot_id,
            status=maturation_session.status,
            current_step=maturation_session.current_step,
            language=maturation_session.language,
            questions_per_batch=maturation_session.questions_per_batch,
            total_questions_generated=maturation_session.total_questions_generated,
            total_questions_processed=maturation_session.total_questions_processed,
            successful_questions=maturation_session.successful_questions,
            failed_questions=maturation_session.failed_questions,
            stored_questions=maturation_session.stored_questions,
            success_rate=maturation_session.success_rate,
            created_at=maturation_session.created_at,
            updated_at=maturation_session.updated_at
        ),
        questions=question_responses,
        context_loaded=True,
        existing_test_results=existing_test_results,
        analysis=analysis
    )


@router.post("/questions/{question_id}/approve")
async def approve_question(
    question_id: int,
    request: QuestionApprovalRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Approve or reject a question"""
    # Get question
    result = await session.execute(
        select(MaturationQuestion).where(MaturationQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Update approval
    question.user_approval = request.approval
    question.user_feedback = request.feedback
    
    # If approved and execution was successful, store in use case
    if request.approval == "approved" and question.execution_status == "success" and not question.is_stored:
        # Get use case
        session_result = await session.execute(
            select(MaturationSession).where(MaturationSession.id == question.session_id)
        )
        maturation_session = session_result.scalar_one_or_none()
        
        if maturation_session:
            use_case_result = await session.execute(
                select(UseCase).where(UseCase.id == maturation_session.use_case_id)
            )
            use_case = use_case_result.scalar_one_or_none()
            
            if use_case:
                # Get existing questions and queries
                existing_questions = []
                existing_queries = []
                try:
                    existing_questions = json.loads(use_case.example_questions or "[]")
                    existing_queries = json.loads(use_case.example_queries or "[]")
                except:
                    pass
                
                # Add new question and query (maintain pairing)
                if question.generated_sql:
                    # Only add if we have both question and query to maintain pairing
                    existing_questions.append(question.question_text)
                    existing_queries.append(question.generated_sql)
                else:
                    logger.warning(f"[MATURATION] Question {question_id} approved but has no SQL, skipping")
                
                # Update use case
                use_case.example_questions = json.dumps(existing_questions, ensure_ascii=False)
                use_case.example_queries = json.dumps(existing_queries, ensure_ascii=False)
                
                question.is_stored = True
                maturation_session.stored_questions += 1
    
    await session.commit()
    
    return {"message": f"Question {request.approval} successfully"}


@router.post("/sessions/{session_id}/pause")
async def pause_maturation(
    session_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Pause maturation process"""
    result = await session.execute(
        select(MaturationSession).where(MaturationSession.id == session_id)
    )
    maturation_session = result.scalar_one_or_none()
    if not maturation_session:
        raise HTTPException(status_code=404, detail="Maturation session not found")
    
    if maturation_session.status != "processing":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause session with status: {maturation_session.status}"
        )
    
    maturation_session.status = "paused"
    await session.commit()
    
    return {"message": "Maturation paused"}


@router.post("/sessions/{session_id}/resume")
async def resume_maturation(
    session_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Resume paused maturation process"""
    result = await session.execute(
        select(MaturationSession).where(MaturationSession.id == session_id)
    )
    maturation_session = result.scalar_one_or_none()
    if not maturation_session:
        raise HTTPException(status_code=404, detail="Maturation session not found")
    
    if maturation_session.status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume session with status: {maturation_session.status}"
        )
    
    maturation_session.status = "generating"
    await session.commit()
    
    background_tasks.add_task(process_maturation_session, session_id)
    
    return {"message": "Maturation resumed"}


@router.post("/use-cases/{use_case_id}/test-queries")
async def test_use_case_queries(
    use_case_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Test all existing queries in a use case and return success/failure results"""
    logger.info(f"[MATURATION] Testing queries for use case {use_case_id}")
    
    # Get use case
    result = await session.execute(
        select(UseCase).where(UseCase.id == use_case_id)
    )
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get existing questions and queries
    existing_questions = []
    existing_queries = []
    try:
        existing_questions = json.loads(use_case.example_questions or "[]")
        existing_queries = json.loads(use_case.example_queries or "[]")
    except:
        pass
    
    if not existing_queries:
        return {
            "use_case_id": use_case_id,
            "total_queries": 0,
            "tested_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "results": []
        }
    
    # Test each query
    results = []
    successful_count = 0
    failed_count = 0
    
    for idx, (question, query) in enumerate(zip(existing_questions, existing_queries)):
        if not query:
            continue
        
        try:
            # Execute query
            success, result, error = await maturation_engine.execute_sql(
                query,
                use_case.schema_snapshot_id,
                session
            )
            
            if success:
                successful_count += 1
                results.append({
                    "index": idx,
                    "question": question if idx < len(existing_questions) else None,
                    "query": query,
                    "status": "success",
                    "result_count": len(result) if isinstance(result, list) else 0,
                    "error": None,
                    "sample_result": result[:3] if isinstance(result, list) and len(result) > 0 else None
                })
            else:
                failed_count += 1
                results.append({
                    "index": idx,
                    "question": question if idx < len(existing_questions) else None,
                    "query": query,
                    "status": "failed",
                    "result_count": 0,
                    "error": error,
                    "sample_result": None
                })
        except Exception as e:
            failed_count += 1
            results.append({
                "index": idx,
                "question": question if idx < len(existing_questions) else None,
                "query": query,
                "status": "error",
                "result_count": 0,
                "error": str(e),
                "sample_result": None
            })
    
    return {
        "use_case_id": use_case_id,
        "total_queries": len(existing_queries),
        "tested_queries": len(results),
        "successful_queries": successful_count,
        "failed_queries": failed_count,
        "success_rate": successful_count / len(results) if results else 0,
        "results": results
    }


@router.post("/use-cases/{use_case_id}/remove-queries")
async def remove_failed_queries(
    use_case_id: int,
    request: Dict[str, Any],  # {"indices": [0, 2, 5]} - indices of queries to remove
    session: AsyncSession = Depends(get_db_session)
):
    """Remove specific queries (by index) from use case"""
    logger.info(f"[MATURATION] Removing queries from use case {use_case_id}")
    
    indices_to_remove = request.get("indices", [])
    if not indices_to_remove:
        raise HTTPException(status_code=400, detail="No indices provided")
    
    # Get use case
    result = await session.execute(
        select(UseCase).where(UseCase.id == use_case_id)
    )
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get existing questions and queries
    existing_questions = []
    existing_queries = []
    try:
        existing_questions = json.loads(use_case.example_questions or "[]")
        existing_queries = json.loads(use_case.example_queries or "[]")
    except:
        pass
    
    # Remove queries at specified indices (in reverse order to maintain indices)
    indices_to_remove_sorted = sorted(set(indices_to_remove), reverse=True)
    
    removed_count = 0
    for idx in indices_to_remove_sorted:
        if 0 <= idx < len(existing_queries):
            existing_queries.pop(idx)
            if idx < len(existing_questions):
                existing_questions.pop(idx)
            removed_count += 1
    
    # Update use case
    use_case.example_questions = json.dumps(existing_questions, ensure_ascii=False)
    use_case.example_queries = json.dumps(existing_queries, ensure_ascii=False)
    
    await session.commit()
    
    logger.info(f"[MATURATION] Removed {removed_count} queries from use case {use_case_id}")
    
    return {
        "message": f"Removed {removed_count} query(ies) from use case",
        "removed_count": removed_count,
        "remaining_queries": len(existing_queries)
    }


@router.post("/use-cases/{use_case_id}/add-queries")
async def add_successful_queries(
    use_case_id: int,
    request: Dict[str, Any],  # {"questions": ["q1", "q2"], "queries": ["sql1", "sql2"]}
    session: AsyncSession = Depends(get_db_session)
):
    """Add successful questions and queries to use case"""
    logger.info(f"[MATURATION] Adding queries to use case {use_case_id}")
    
    new_questions = request.get("questions", [])
    new_queries = request.get("queries", [])
    
    if not new_questions or not new_queries:
        raise HTTPException(status_code=400, detail="Both questions and queries must be provided")
    
    if len(new_questions) != len(new_queries):
        raise HTTPException(status_code=400, detail="Number of questions must match number of queries")
    
    # Get use case
    result = await session.execute(
        select(UseCase).where(UseCase.id == use_case_id)
    )
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get existing questions and queries
    existing_questions = []
    existing_queries = []
    try:
        existing_questions = json.loads(use_case.example_questions or "[]")
        existing_queries = json.loads(use_case.example_queries or "[]")
    except:
        pass
    
    # Add new questions and queries
    existing_questions.extend(new_questions)
    existing_queries.extend(new_queries)
    
    # Update use case
    use_case.example_questions = json.dumps(existing_questions, ensure_ascii=False)
    use_case.example_queries = json.dumps(existing_queries, ensure_ascii=False)
    
    await session.commit()
    
    logger.info(f"[MATURATION] Added {len(new_questions)} queries to use case {use_case_id}")
    
    return {
        "message": f"Added {len(new_questions)} query(ies) to use case",
        "added_count": len(new_questions),
        "total_queries": len(existing_queries)
    }


async def analyze_use_case_queries_internal(
    use_case_id: int,
    session: AsyncSession
) -> Dict[str, Any]:
    """Internal function to analyze queries (used in maturation process)"""
    # Test all queries
    test_result = await test_existing_queries_internal(use_case_id, session)
    
    # Analyze results
    failed_queries = [r for r in test_result["results"] if r["status"] != "success"]
    successful_queries = [r for r in test_result["results"] if r["status"] == "success"]
    
    recommendations = []
    
    if failed_queries:
        recommendations.append({
            "type": "remove_failed",
            "priority": "high",
            "message": f"{len(failed_queries)} query(ies) failed execution. Consider removing them.",
            "failed_indices": [r["index"] for r in failed_queries],
            "failed_queries": [
                {
                    "index": r["index"],
                    "question": r["question"],
                    "error": r["error"]
                }
                for r in failed_queries
            ]
        })
    
    if test_result["tested_queries"] > 0 and test_result["success_rate"] < 0.5:
        recommendations.append({
            "type": "low_success_rate",
            "priority": "high",
            "message": f"Success rate is {test_result['success_rate']:.1%}. Most queries are failing.",
            "suggestion": "Review and regenerate queries based on latest schema and sample data."
        })
    
    if len(successful_queries) < 3:
        recommendations.append({
            "type": "insufficient_queries",
            "priority": "medium",
            "message": f"Only {len(successful_queries)} successful query(ies). Use case needs at least 3.",
            "suggestion": "Run maturation process to generate more successful queries."
        })
    
    return {
        "use_case_id": use_case_id,
        "summary": {
            "total_queries": test_result["total_queries"],
            "successful": test_result["successful_queries"],
            "failed": test_result["failed_queries"],
            "success_rate": test_result["success_rate"]
        },
        "recommendations": recommendations,
        "detailed_results": test_result["results"]
    }


@router.get("/use-cases/{use_case_id}/analyze")
async def analyze_use_case_queries(
    use_case_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Analyze all queries in use case and provide recommendations"""
    logger.info(f"[MATURATION] Analyzing queries for use case {use_case_id}")
    return await analyze_use_case_queries_internal(use_case_id, session)


# Maturation Cycle - Complete Flow
class MaturationFeedbackRequest(BaseModel):
    """Feedback for maturation cycle"""
    session_id: int
    user_feedback: Optional[str] = None
    approved_questions: List[int] = []  # Question IDs that were approved
    rejected_questions: List[int] = []  # Question IDs that were rejected
    improvement_suggestions: Optional[str] = None  # User suggestions for improvement


class UseCaseImprovementRequest(BaseModel):
    """Request to improve use case based on maturation results"""
    use_case_id: int
    maturation_results: Dict[str, Any]  # Results from maturation session
    user_feedback: Optional[str] = None
    improvement_suggestions: Optional[str] = None


@router.post("/sessions/{session_id}/collect-feedback")
async def collect_maturation_feedback(
    session_id: int,
    request: MaturationFeedbackRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Collect feedback from maturation session and prepare for use case improvement"""
    logger.info(f"[MATURATION] Collecting feedback for session {session_id}")
    
    # Get session
    result = await session.execute(
        select(MaturationSession).where(MaturationSession.id == session_id)
    )
    maturation_session = result.scalar_one_or_none()
    if not maturation_session:
        raise HTTPException(status_code=404, detail="Maturation session not found")
    
    # Get all questions from session
    questions_result = await session.execute(
        select(MaturationQuestion).where(MaturationQuestion.session_id == session_id)
    )
    questions = questions_result.scalars().all()
    
    # Collect results
    successful_questions = []
    failed_questions = []
    approved_questions = []
    rejected_questions = []
    
    for q in questions:
        if q.execution_status == "success":
            successful_questions.append({
                "id": q.id,
                "question": q.question_text,
                "sql": q.generated_sql,
                "result_count": len(json.loads(q.execution_result)) if q.execution_result else 0,
                "user_approval": q.user_approval,
                "user_feedback": q.user_feedback
            })
            if q.user_approval == "approved":
                approved_questions.append(q.id)
            elif q.user_approval == "rejected":
                rejected_questions.append(q.id)
        else:
            failed_questions.append({
                "id": q.id,
                "question": q.question_text,
                "sql": q.generated_sql,
                "error": q.execution_error,
                "retry_count": q.retry_count
            })
    
    # Get use case
    use_case_result = await session.execute(
        select(UseCase).where(UseCase.id == maturation_session.use_case_id)
    )
    use_case = use_case_result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get existing questions and queries
    existing_questions = []
    existing_queries = []
    try:
        existing_questions = json.loads(use_case.example_questions or "[]")
        existing_queries = json.loads(use_case.example_queries or "[]")
    except:
        pass
    
    # Prepare maturation results summary
    maturation_results = {
        "session_id": session_id,
        "use_case_id": use_case.id,
        "total_questions_generated": maturation_session.total_questions_generated,
        "total_questions_processed": maturation_session.total_questions_processed,
        "successful_questions": maturation_session.successful_questions,
        "failed_questions": maturation_session.failed_questions,
        "stored_questions": maturation_session.stored_questions,
        "success_rate": maturation_session.success_rate,
        "successful_questions_details": successful_questions,
        "failed_questions_details": failed_questions,
        "approved_questions": approved_questions,
        "rejected_questions": rejected_questions,
        "existing_questions_count": len(existing_questions),
        "existing_queries_count": len(existing_queries),
        "user_feedback": request.user_feedback,
        "improvement_suggestions": request.improvement_suggestions
    }
    
    return {
        "message": "Feedback collected successfully",
        "maturation_results": maturation_results,
        "ready_for_improvement": True
    }


@router.get("/use-cases/{use_case_id}/improvement-status")
async def get_improvement_status(
    use_case_id: int,
    started_at: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session)
):
    """Check if use case improvement has completed by comparing updated_at with started_at"""
    result = await session.execute(
        select(UseCase).where(UseCase.id == use_case_id)
    )
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    if not started_at:
        return {
            "status": "unknown",
            "message": "No start time provided"
        }
    
    try:
        # Parse start time (handle both with and without Z)
        if started_at.endswith('Z'):
            start_time = datetime.fromisoformat(started_at[:-1] + '+00:00')
        else:
            start_time = datetime.fromisoformat(started_at)
        
        # Compare updated_at with start_time
        # If updated_at is after start_time, improvement likely completed
        if use_case.updated_at:
            # Convert to UTC for comparison if needed
            updated_at_utc = use_case.updated_at
            if updated_at_utc.tzinfo is None:
                # If naive datetime, assume UTC
                from datetime import timezone
                updated_at_utc = updated_at_utc.replace(tzinfo=timezone.utc)
            
            if start_time.tzinfo is None:
                from datetime import timezone
                start_time = start_time.replace(tzinfo=timezone.utc)
            
            if updated_at_utc > start_time:
                return {
                    "status": "completed",
                    "message": "Use case has been updated",
                    "updated_at": use_case.updated_at.isoformat()
                }
        
        return {
            "status": "processing",
            "message": "Improvement in progress",
            "started_at": started_at
        }
    except Exception as e:
        logger.error(f"[MATURATION] Error checking improvement status: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/use-cases/{use_case_id}/improve")
async def improve_use_case_with_llm(
    use_case_id: int,
    request: UseCaseImprovementRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Improve use case based on maturation results using LLM"""
    logger.info(f"[MATURATION] Improving use case {use_case_id} with LLM")
    
    # Get use case
    result = await session.execute(
        select(UseCase).where(UseCase.id == use_case_id)
    )
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")
    
    # Get active LLM model
    model_result = await session.execute(
        select(LLMModel).where(LLMModel.is_active == True)
    )
    active_model = model_result.scalar_one_or_none()
    if not active_model:
        raise HTTPException(status_code=400, detail="No active LLM model found")
    
    # Get schema snapshot
    snapshot_result = await session.execute(
        select(SchemaSnapshot).where(SchemaSnapshot.id == use_case.schema_snapshot_id)
    )
    snapshot = snapshot_result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Schema snapshot not found")
    
    # Get database type
    db_connector = None
    database_type = "sqlserver"  # Default
    try:
        db_connector = await create_db_connector_for_snapshot(use_case.schema_snapshot_id, session)
        if db_connector:
            # DirectDatabaseConnector has db_type as attribute, not method
            database_type = db_connector.db_type or "sqlserver"
            await db_connector.disconnect()
    except Exception as e:
        logger.warning(f"[MATURATION] Could not get database type: {e}")
        # Fallback: get from snapshot connection
        try:
            snapshot_result = await session.execute(
                select(SchemaSnapshot).where(SchemaSnapshot.id == use_case.schema_snapshot_id)
            )
            snapshot = snapshot_result.scalar_one_or_none()
            if snapshot:
                from api.db_models import DatabaseConnection
                conn_result = await session.execute(
                    select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
                )
                connection = conn_result.scalar_one_or_none()
                if connection and connection.db_type:
                    database_type = connection.db_type.lower()
        except:
            pass
    
    # Load context similar to maturation engine (this will be done in background task)
    # We pass snapshot_id and other info to background task
    logger.info(f"[MATURATION] Starting improvement background task for use case {use_case_id}")
    
    # Start improvement in background
    background_tasks.add_task(
        improve_use_case_background,
        use_case_id,
        active_model.id,
        request.maturation_results,
        request.user_feedback,
        request.improvement_suggestions,
        database_type
    )
    
    # Store improvement start time to track completion
    improvement_start_time = datetime.utcnow()
    
    return {
        "message": "Use case improvement started",
        "use_case_id": use_case_id,
        "status": "processing",
        "started_at": improvement_start_time.isoformat() + "Z"
    }


def build_use_case_improvement_prompt(
    use_case: UseCase,
    maturation_results: Dict[str, Any],
    context: Any,  # MaturationContext
    user_feedback: Optional[str],
    improvement_suggestions: Optional[str],
    database_type: str = "sqlserver"
) -> str:
    """Build prompt for improving use case based on maturation results"""
    
    # Get existing questions and queries
    existing_questions = []
    existing_queries = []
    try:
        existing_questions = json.loads(use_case.example_questions or "[]")
        existing_queries = json.loads(use_case.example_queries or "[]")
    except:
        pass
    
    # Format successful questions
    successful_questions_text = ""
    if maturation_results.get("successful_questions_details"):
        successful_questions_text = "\nSUCCESSFUL QUESTIONS FROM MATURATION:\n"
        for sq in maturation_results["successful_questions_details"][:10]:  # Limit to 10
            successful_questions_text += f"- Question: {sq['question']}\n"
            successful_questions_text += f"  SQL: {sq['sql']}\n"
            successful_questions_text += f"  Result Count: {sq['result_count']}\n"
            if sq.get('user_feedback'):
                successful_questions_text += f"  User Feedback: {sq['user_feedback']}\n"
            successful_questions_text += "\n"
    
    # Format failed questions
    failed_questions_text = ""
    if maturation_results.get("failed_questions_details"):
        failed_questions_text = "\nFAILED QUESTIONS FROM MATURATION (LEARN FROM THESE):\n"
        for fq in maturation_results["failed_questions_details"][:5]:  # Limit to 5
            failed_questions_text += f"- Question: {fq['question']}\n"
            if fq.get('sql'):
                failed_questions_text += f"  SQL: {fq['sql']}\n"
            if fq.get('error'):
                failed_questions_text += f"  Error: {fq['error']}\n"
            failed_questions_text += "\n"
    
    # Format context
    context_text = maturation_engine._format_context_for_prompt(context)
    
    # Get business context and other use case metadata
    business_context = use_case.business_context or "Not specified"
    primary_audience = []
    try:
        primary_audience = json.loads(use_case.primary_audience or "[]")
    except:
        pass
    
    # Format sample data more explicitly
    sample_data_text = ""
    if context.sample_data:
        sample_data_text = "\nSAMPLE DATA (5 unique rows per table - USE THESE TO UNDERSTAND DATA PATTERNS):\n"
        for table_key, rows in context.sample_data.items():
            if rows and len(rows) > 0:
                sample_data_text += f"\nTable: {table_key}\n"
                for i, row in enumerate(rows[:5], 1):
                    sample_data_text += f"  Row {i}: {json.dumps(row, ensure_ascii=False)}\n"
        sample_data_text += "\nIMPORTANT: Use the sample data above to understand:\n"
        sample_data_text += "- Actual data types and formats in the database\n"
        sample_data_text += "- Real values and patterns (dates, numbers, strings)\n"
        sample_data_text += "- Data relationships and business context\n"
        sample_data_text += "- Generate questions that match these actual data patterns\n"
    
    # SQL Server specific rules
    sql_server_rules = ""
    if database_type.lower() == "sqlserver":
        sql_server_rules = """
SQL SERVER (T-SQL) SPECIFIC RULES:
- Use SQL Server syntax: TOP instead of LIMIT
- Use SQL Server functions: ISNULL, COALESCE, CAST, CONVERT
- Use SQL Server date functions: GETDATE(), DATEADD, DATEDIFF
- For Unicode strings (Persian/Arabic/etc): ALWAYS use N'...' prefix (e.g., N'سلف', N'داخلی')
- For string date columns: Use LIKE N'YYYY%' or SUBSTRING, NOT YEAR() or MONTH()
- Avoid unsupported functions from other databases
"""
    
    prompt = f"""You are a Use Case Improvement AI. Your task is to improve an existing use case based on maturation results, user feedback, and complete database context.

DATABASE TYPE: {database_type.upper()}

{sql_server_rules}

CURRENT USE CASE:
- Name: {use_case.name}
- Business Goal: {use_case.business_goal}
- Business Context: {business_context}
- Output Style: {use_case.output_style}
- Primary Audience: {', '.join(primary_audience) if primary_audience else 'Not specified'}
- Existing Questions: {len(existing_questions)}
- Existing Queries: {len(existing_queries)}

EXISTING QUESTIONS AND QUERIES:
{chr(10).join([f"Q{i+1}: {q}" for i, q in enumerate(existing_questions)]) if existing_questions else "None"}
{chr(10).join([f"SQL{i+1}: {q[:200]}..." if len(q) > 200 else f"SQL{i+1}: {q}" for i, q in enumerate(existing_queries)]) if existing_queries else "None"}

{context_text}

{sample_data_text}

MATURATION RESULTS:
- Total Questions Generated: {maturation_results.get('total_questions_generated', 0)}
- Successful: {maturation_results.get('successful_questions', 0)}
- Failed: {maturation_results.get('failed_questions', 0)}
- Success Rate: {maturation_results.get('success_rate', 0):.1%}
- Stored: {maturation_results.get('stored_questions', 0)}

{successful_questions_text}

{failed_questions_text}

USER FEEDBACK:
{user_feedback if user_feedback else "No specific feedback provided"}

IMPROVEMENT SUGGESTIONS:
{improvement_suggestions if improvement_suggestions else "No specific suggestions provided"}

YOUR TASK:
1. Analyze the maturation results and identify patterns
2. Learn from successful questions - what made them work?
3. Learn from failed questions - what went wrong?
4. Improve the use case by:
   - Enhancing business_goal with insights from successful queries
   - **MANDATORY: Include ALL successful questions from maturation in typical_questions**
   - **MANDATORY: Include ALL successful queries from maturation in example_queries**
   - **MANDATORY: Keep ALL existing successful questions and queries (don't remove them)**
   - **MANDATORY: Ensure at least 5-10 questions total (combine existing + successful from maturation)**
   - Removing or fixing patterns that led to failures
   - Improving preconditions, main_flow, and alternative_flows based on actual execution results
   - Updating validation_metrics based on real execution data

5. Return an IMPROVED use case in the same JSON format as the original, but with:
   - Enhanced business_goal (incorporate learnings)
   - Updated typical_questions (MUST include ALL existing questions + ALL successful questions from maturation)
   - Updated example_queries (MUST include ALL existing queries + ALL successful queries from maturation)
   - Improved preconditions, main_flow, alternative_flows
   - Better validation_metrics
   
CRITICAL REQUIREMENTS:
- **MUST include ALL {len(maturation_results.get('successful_questions_details', []))} successful questions from maturation**
- **MUST include ALL {len(maturation_results.get('successful_questions_details', []))} successful queries from maturation**
- **MUST keep ALL {len(existing_questions)} existing questions**
- **MUST keep ALL {len(existing_queries)} existing queries**
- **Total questions should be at least {max(5, len(existing_questions) + len(maturation_results.get('successful_questions_details', [])))}**
- **Total queries should be at least {max(5, len(existing_queries) + len(maturation_results.get('successful_questions_details', [])))}**
- **DO NOT remove existing questions/queries unless they failed in maturation**
- **DO NOT generate only 1 question - you MUST include ALL successful ones**

OUTPUT FORMAT:
Return a JSON object with the improved use case structure:
{{
  "name": "Improved use case name",
  "business_goal": "Enhanced business goal with learnings from maturation",
  "preconditions": ["Updated based on actual execution"],
  "main_flow": ["Updated steps based on successful queries"],
  "alternative_flows": ["Updated based on failures"],
  "required_inputs": ["Updated based on successful queries"],
  "sql_intent": "Updated intent based on successful SQL patterns",
  "expected_output": "Updated based on actual results",
  "validation_metrics": ["Updated based on real execution"],
  "typical_questions": ["List of improved questions - include successful ones from maturation"],
  "example_queries": ["List of improved queries - include successful SQL from maturation"]
}}

CRITICAL RULES:
- Keep all successful questions and queries from maturation
- Remove or fix patterns that led to failures
- Enhance descriptions based on actual execution results
- Maintain the same scope and actor
- Use actual table/column names from the DATABASE SCHEMA section above
- Use actual business terminology from the DATA DICTIONARY section above
- Reference actual relationships from the RELATIONSHIPS section above
- Use actual data patterns from the SAMPLE DATA section above
- Ensure all queries are valid SQL for {database_type.upper()}
- Follow SQL Server specific rules if database is SQL Server (TOP, N'...' for Unicode, etc.)
- Questions must be natural language (no technical prefixes like "Query:", "SQL:")
- Queries must match questions one-to-one (same order, same count)
- Base improvements on actual execution results from maturation
- Use real values from sample data, not generic placeholders

OUTPUT REQUIREMENTS:
- Return a COMPLETE JSON object with ALL fields filled
- typical_questions must be an array with at least {max(5, len(existing_questions) + len(maturation_results.get('successful_questions_details', [])))}
- example_queries must be an array with the SAME count as typical_questions
- Each query must answer its corresponding question (index 0 answers index 0, etc.)
- All fields must be filled (don't leave any field empty or null)
- Use actual table/column names from schema, not placeholders

Return ONLY valid JSON. No markdown, no explanations, no code blocks. Pure JSON starting with {{ and ending with }}.
"""
    
    return prompt


async def improve_use_case_background(
    use_case_id: int,
    model_id: int,
    maturation_results: Dict[str, Any],
    user_feedback: Optional[str],
    improvement_suggestions: Optional[str],
    database_type: str = "sqlserver"
):
    """Background task to improve use case using LLM"""
    async_session = create_background_session()
    
    try:
        async with async_session() as session:
            try:
                logger.info(f"[MATURATION] Starting use case improvement for {use_case_id}")
                
                # Get use case
                result = await session.execute(
                    select(UseCase).where(UseCase.id == use_case_id)
                )
                use_case = result.scalar_one_or_none()
                if not use_case:
                    logger.error(f"[MATURATION] Use case {use_case_id} not found")
                    return
                
                # Get model
                model_result = await session.execute(
                    select(LLMModel).where(LLMModel.id == model_id)
                )
                active_model = model_result.scalar_one_or_none()
                if not active_model:
                    logger.error(f"[MATURATION] Model {model_id} not found")
                    return
                
                # Load context
                logger.info(f"[MATURATION] Loading context for snapshot {use_case.schema_snapshot_id}")
                context = await maturation_engine.load_context(
                    use_case.schema_snapshot_id,
                    session
                )
                logger.info(f"[MATURATION] Context loaded successfully")
                
                # Build improvement prompt
                logger.info(f"[MATURATION] Building improvement prompt")
                improvement_prompt = build_use_case_improvement_prompt(
                    use_case,
                    maturation_results,
                    context,
                    user_feedback,
                    improvement_suggestions,
                    database_type
                )
                logger.info(f"[MATURATION] Improvement prompt built, length: {len(improvement_prompt)}")
                
                # Initialize ModelConnector
                config = {"models": []}
                provider_map = {
                    "OpenAI": "openai",
                    "Ollama": "ollama",
                    "vLLM": "vllm",
                }
                provider = provider_map.get(active_model.service_name, "custom")
                
                config["models"].append({
                    "id": str(active_model.id),
                    "provider": provider,
                    "base_url": active_model.base_url,
                    "model_name": active_model.model_name,
                    "api_key": decrypt_api_key(active_model.api_key) if active_model.api_key else None,
                    "supports_chat": True,
                    "supports_json": provider == "openai",
                    "max_tokens": active_model.max_tokens,
                    "is_active": True,
                    "timeout_seconds": 1800.0,
                })
                
                loader = ConfigRegistryLoader(config)
                registry = initialize_registry(loader)
                await registry.load()
                
                connector = ModelConnector(registry)
                await connector.initialize()
                
                logger.info(f"[MATURATION] Calling LLM for improvement")
                # Generate improved use case
                # Use higher max_tokens for complete use case structure
                max_tokens_for_improvement = min(active_model.max_tokens or 4096, 4096)
                llm_request = LLMRequest(
                    model_id=str(active_model.id),
                    messages=[Message(role=MessageRole.USER, content=improvement_prompt)],
                    temperature=0.3,  # Lower temperature for improvement
                    max_tokens=max_tokens_for_improvement
                )
                logger.info(f"[MATURATION] LLM request: max_tokens={max_tokens_for_improvement}, prompt_length={len(improvement_prompt)}")
                
                response = await connector.generate(llm_request)
                improved_text = response.text.strip()
                logger.info(f"[MATURATION] LLM response received, length: {len(improved_text)}")
                
                # Clean JSON
                if improved_text.startswith('```json'):
                    improved_text = improved_text[7:]
                elif improved_text.startswith('```'):
                    improved_text = improved_text[3:]
                if improved_text.endswith('```'):
                    improved_text = improved_text[:-3]
                improved_text = improved_text.strip()
                
                # Parse improved use case
                logger.info(f"[MATURATION] Parsing improved use case JSON")
                try:
                    improved_uc = json.loads(improved_text)
                    logger.info(f"[MATURATION] Successfully parsed JSON")
                except json.JSONDecodeError as e:
                    logger.error(f"[MATURATION] Failed to parse improved use case JSON: {e}")
                    logger.error(f"[MATURATION] Response (first 1000 chars): {improved_text[:1000]}")
                    # Try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'\{.*\}', improved_text, re.DOTALL)
                    if json_match:
                        try:
                            improved_uc = json.loads(json_match.group())
                            logger.info(f"[MATURATION] Successfully extracted JSON from markdown")
                        except:
                            logger.error(f"[MATURATION] Failed to parse extracted JSON")
                            return
                    else:
                        return
                
                # Update use case with improved data
                logger.info(f"[MATURATION] Updating use case with improved data")
                
                # Update name if provided
                if improved_uc.get("name"):
                    use_case.name = improved_uc.get("name")
                    logger.info(f"[MATURATION] Updated name: {use_case.name}")
                
                # Update business_goal if provided
                if improved_uc.get("business_goal"):
                    use_case.business_goal = improved_uc.get("business_goal")
                    logger.info(f"[MATURATION] Updated business_goal")
                
                # Update business_context if provided (can be enhanced based on maturation)
                if improved_uc.get("business_context"):
                    use_case.business_context = improved_uc.get("business_context")
                    logger.info(f"[MATURATION] Updated business_context")
                
                # Update questions and queries - MAINTAIN ORDER AND PAIRING
                improved_questions = improved_uc.get("typical_questions", [])
                improved_queries = improved_uc.get("example_queries", [])
                
                # Get existing questions and queries as pairs
                existing_pairs = []
                try:
                    existing_questions = json.loads(use_case.example_questions or "[]")
                    existing_queries = json.loads(use_case.example_queries or "[]")
                    # Create pairs to maintain order
                    for i in range(min(len(existing_questions), len(existing_queries))):
                        existing_pairs.append({
                            "question": existing_questions[i],
                            "query": existing_queries[i]
                        })
                except:
                    existing_pairs = []
                
                # Create pairs from improved use case (from LLM)
                improved_pairs = []
                for i in range(min(len(improved_questions), len(improved_queries))):
                    improved_pairs.append({
                        "question": improved_questions[i],
                        "query": improved_queries[i]
                    })
                
                # Track seen pairs to avoid duplicates
                # Use question text as key (not full pair) to detect similar questions
                seen_questions = set()
                final_pairs = []
                
                # Priority 1: Add ALL successful pairs from maturation FIRST (these are tested and working)
                if maturation_results.get("successful_questions_details"):
                    for sq in maturation_results["successful_questions_details"]:
                        question_text = sq.get("question", "").strip()
                        sql_text = sq.get("sql", "").strip()
                        
                        if question_text and sql_text:
                            question_key = question_text.strip().lower()
                            if question_key not in seen_questions:
                                final_pairs.append({
                                    "question": question_text,
                                    "query": sql_text
                                })
                                seen_questions.add(question_key)
                                logger.info(f"[MATURATION] Added successful pair from maturation: {question_text[:50]}...")
                
                # Priority 2: Add existing pairs that are not already in final_pairs (keep existing working pairs)
                for pair in existing_pairs:
                    question_key = pair["question"].strip().lower()
                    if question_key not in seen_questions:
                        final_pairs.append(pair)
                        seen_questions.add(question_key)
                        logger.debug(f"[MATURATION] Kept existing pair: {pair['question'][:50]}...")
                
                # Priority 3: Add improved pairs from LLM (only if they don't duplicate existing/successful ones)
                for pair in improved_pairs:
                    question_key = pair["question"].strip().lower()
                    if question_key not in seen_questions:
                        # Validate that question and query are both present and non-empty
                        if pair.get("question") and pair.get("query"):
                            final_pairs.append(pair)
                            seen_questions.add(question_key)
                            logger.debug(f"[MATURATION] Added improved pair: {pair['question'][:50]}...")
                        else:
                            logger.warning(f"[MATURATION] Skipping improved pair with missing question or query")
                
                # Extract final lists maintaining order
                final_questions = [pair["question"] for pair in final_pairs]
                final_queries = [pair["query"] for pair in final_pairs]
                
                # Ensure we have at least 3 pairs (minimum requirement)
                if len(final_pairs) < 3:
                    logger.warning(f"[MATURATION] Only {len(final_pairs)} pairs after improvement, expected at least 3")
                
                logger.info(f"[MATURATION] Final count: {len(final_pairs)} pairs (questions and queries matched)")
                
                # Update use case with merged questions and queries (order preserved)
                use_case.example_questions = json.dumps(final_questions, ensure_ascii=False)
                use_case.example_queries = json.dumps(final_queries, ensure_ascii=False)
                
                # Update typical_questions if provided (for reference)
                if improved_uc.get("typical_questions"):
                    # typical_questions is already merged above, but we can also store it separately
                    use_case.typical_questions = json.dumps(improved_questions, ensure_ascii=False)
                
                # Update primary_audience if provided
                if improved_uc.get("primary_audience"):
                    if isinstance(improved_uc.get("primary_audience"), list):
                        use_case.primary_audience = json.dumps(improved_uc.get("primary_audience"), ensure_ascii=False)
                    else:
                        use_case.primary_audience = improved_uc.get("primary_audience")
                
                # Note: Fields like preconditions, main_flow, alternative_flows, required_inputs, 
                # sql_intent, expected_output, validation_metrics are not stored in UseCase model
                # but are part of the improved JSON. They can be logged or stored in a future enhancement.
                if improved_uc.get("preconditions"):
                    logger.info(f"[MATURATION] Preconditions provided (not stored in model): {improved_uc.get('preconditions')}")
                if improved_uc.get("main_flow"):
                    logger.info(f"[MATURATION] Main flow provided (not stored in model): {len(improved_uc.get('main_flow', []))} steps")
                if improved_uc.get("alternative_flows"):
                    logger.info(f"[MATURATION] Alternative flows provided (not stored in model): {len(improved_uc.get('alternative_flows', []))} flows")
                
                await session.commit()
                
                logger.info(
                    f"[MATURATION] Use case {use_case_id} improved successfully: "
                    f"{len(improved_questions)} questions, {len(improved_queries)} queries"
                )
                
            except Exception as e:
                logger.error(f"[MATURATION] Error improving use case {use_case_id}: {e}", exc_info=True)
    except Exception as outer_error:
        logger.error(f"[MATURATION] Critical error in improvement task: {outer_error}", exc_info=True)