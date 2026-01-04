from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
from datetime import datetime
import logging

from .db_models import (
    FineTuningSession, FineTuningQuestion, UseCase, UseCaseVersion,
    SchemaSnapshot, SchemaMetadata, DataDictionary, Relationship, LLMModel, DatabaseConnection, get_db_session
)
from config.config import DATABASE_URL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def fine_tuning_health_check():
    """Health check for fine-tuning module"""
    logger.info("Fine-tuning health check called")
    return {"status": "healthy", "module": "fine_tuning"}


# Pydantic Models for API
class FineTuningSessionCreate(BaseModel):
    use_case_id: int
    include_full_dictionary: bool = False
    questions_count: int = 5
    language: str = "english"  # "english" or "persian"


class FineTuningSessionResponse(BaseModel):
    id: int
    use_case_id: int
    status: str
    current_step: Optional[str]
    include_full_dictionary: bool
    questions_count: int
    language: str
    generated_questions_count: int
    approved_questions_count: int
    rejected_questions_count: int
    confidence_score: Optional[float]
    created_at: datetime


class FineTuningQuestionResponse(BaseModel):
    id: int
    question_index: int
    question_text: str
    is_user_edited: bool
    generated_sql: Optional[str]
    execution_status: Optional[str]
    execution_result: Optional[str]
    execution_error: Optional[str]
    user_approval: Optional[str]
    user_feedback: Optional[str]


class ContextPreviewResponse(BaseModel):
    tables: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    data_dictionary_coverage: Dict[str, Any]
    use_case_text: str


class QuestionGenerationRequest(BaseModel):
    session_id: int
    questions: List[str]


class SQLExecutionRequest(BaseModel):
    question_id: int
    approval: str  # "approved" or "rejected"
    feedback: Optional[str] = None


class UseCaseRefinementResponse(BaseModel):
    original_use_case: str
    refined_use_case: str
    summary_of_changes: str
    new_version_id: int


class LLMRequest(BaseModel):
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 2048


# Helper function to create background database session
def create_background_session():
    """Create a new database session factory for background tasks"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return async_session


# Helper function to get database connection details
async def get_db_connection_for_snapshot(snapshot_id: int, session: AsyncSession):
    """Get database connection details for a snapshot"""
    logger.info(f"Getting database connection for snapshot {snapshot_id}")

    result = await session.execute(
        select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        logger.error(f"Schema snapshot {snapshot_id} not found")
        raise HTTPException(status_code=404, detail="Schema snapshot not found")

    logger.info(f"Found snapshot {snapshot_id}, connection_id: {snapshot.connection_id}")

    # Get connection details
    conn_result = await session.execute(
        select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
    )
    connection = conn_result.scalar_one_or_none()
    if not connection:
        logger.error(f"Database connection {snapshot.connection_id} not found")
        raise HTTPException(status_code=404, detail="Database connection not found")

    logger.info(f"Found database connection: {connection.db_type} - {connection.database_name}")
    return connection


# STEP 1: Create Fine-Tuning Session
@router.post("/sessions", response_model=FineTuningSessionResponse)
async def create_fine_tuning_session(
    request: FineTuningSessionCreate,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Create a new fine-tuning session for a use case"""
    logger.info(f"Creating fine-tuning session for use case {request.use_case_id}")

    try:
        # Validate use case exists
        logger.info(f"Validating use case {request.use_case_id}")
        result = await db_session.execute(select(UseCase).where(UseCase.id == request.use_case_id))
        use_case = result.scalar_one_or_none()
        if not use_case:
            logger.error(f"Use case {request.use_case_id} not found")
            raise HTTPException(status_code=404, detail="Use case not found")

        logger.info(f"Use case found: {use_case.name}, schema_snapshot_id: {use_case.schema_snapshot_id}")

        # Get active LLM model
        logger.info("Looking for active LLM model")
        model_result = await db_session.execute(select(LLMModel).where(LLMModel.is_active == True))
        active_model = model_result.scalar_one_or_none()
        if not active_model:
            logger.error("No active LLM model found")
            raise HTTPException(status_code=400, detail="No active LLM model found")

        logger.info(f"Active model found: {active_model.name} (ID: {active_model.id})")

        # Create session
        logger.info(f"Creating fine-tuning session record with language: {request.language}")
        fine_tuning_session = FineTuningSession(
            use_case_id=request.use_case_id,
            schema_snapshot_id=use_case.schema_snapshot_id,
            model_id=active_model.id,
            include_full_dictionary=request.include_full_dictionary,
            questions_count=request.questions_count,
            language=request.language,
            status="created",
            current_step="context_preview"
        )

        db_session.add(fine_tuning_session)
        await db_session.commit()
        await db_session.refresh(fine_tuning_session)

        logger.info(f"Successfully created fine-tuning session {fine_tuning_session.id}")
        return FineTuningSessionResponse(
            id=fine_tuning_session.id,
            use_case_id=fine_tuning_session.use_case_id,
            status=fine_tuning_session.status,
            current_step=fine_tuning_session.current_step,
            include_full_dictionary=fine_tuning_session.include_full_dictionary,
            questions_count=fine_tuning_session.questions_count,
            language=fine_tuning_session.language,
            generated_questions_count=fine_tuning_session.generated_questions_count,
            approved_questions_count=fine_tuning_session.approved_questions_count,
            rejected_questions_count=fine_tuning_session.rejected_questions_count,
            confidence_score=fine_tuning_session.confidence_score,
            created_at=fine_tuning_session.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating fine-tuning session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# STEP 1: Get Context Preview
@router.get("/sessions/{session_id}/context", response_model=ContextPreviewResponse)
async def get_context_preview(
    session_id: int,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get context preview for fine-tuning session"""
    logger.info(f"Fetching context preview for session {session_id}")

    try:
        # Get session
        logger.info(f"Looking up fine-tuning session {session_id}")
        result = await db_session.execute(
            select(FineTuningSession).where(FineTuningSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.error(f"Fine-tuning session {session_id} not found")
            raise HTTPException(status_code=404, detail="Fine-tuning session not found")

        logger.info(f"Found session {session_id}, use_case_id: {session.use_case_id}, schema_snapshot_id: {session.schema_snapshot_id}")

        # Get use case
        logger.info(f"Fetching use case {session.use_case_id}")
        use_case_result = await db_session.execute(
            select(UseCase).where(UseCase.id == session.use_case_id)
        )
        use_case = use_case_result.scalar_one()
        logger.info(f"Found use case: {use_case.name}")

        # Get schema metadata (tables)
        logger.info(f"Fetching schema metadata for snapshot {session.schema_snapshot_id}")
        schema_result = await db_session.execute(
            select(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == session.schema_snapshot_id)
        )
        schema_metadata = schema_result.scalars().all()
        logger.info(f"Found {len(schema_metadata)} schema metadata entries")

        # Group by table
        logger.info("Processing schema metadata into table structure")
        tables = {}
        for meta in schema_metadata:
            if meta.table_name not in tables:
                tables[meta.table_name] = {
                    "name": meta.table_name,
                    "columns": [],
                    "row_count": meta.row_count or 0
                }
            tables[meta.table_name]["columns"].append({
                "name": meta.column_name,
                "type": meta.column_type,
                "is_primary_key": meta.is_primary_key,
                "is_foreign_key": meta.is_foreign_key
            })
        logger.info(f"Processed {len(tables)} tables")

        # Get relationships
        logger.info("Fetching relationships")
        relationships_result = await db_session.execute(
            select(Relationship).where(Relationship.schema_snapshot_id == session.schema_snapshot_id)
        )
        relationships = relationships_result.scalars().all()
        logger.info(f"Found {len(relationships)} relationships")

        relationships_data = []
        for rel in relationships:
            relationships_data.append({
                "source_table": rel.source_table,
                "source_column": rel.source_column,
                "target_table": rel.target_table,
                "target_column": rel.target_column,
                "relationship_type": rel.relationship_type,
                "join_type": rel.join_type,
                "description": rel.description
            })

        # Get data dictionary coverage
        logger.info("Fetching data dictionary entries")
        dict_result = await db_session.execute(
            select(DataDictionary).where(DataDictionary.schema_snapshot_id == session.schema_snapshot_id)
        )
        data_dict_entries = dict_result.scalars().all()
        logger.info(f"Found {len(data_dict_entries)} data dictionary entries")

        coverage = {
            "total_tables": len(tables),
            "tables_with_descriptions": len(set(entry.table_name for entry in data_dict_entries if not entry.column_name)),
            "total_columns": sum(len(table["columns"]) for table in tables.values()),
            "columns_with_descriptions": len([entry for entry in data_dict_entries if entry.column_name]),
            "coverage_percentage": 0
        }

        total_describable = coverage["total_tables"] + coverage["total_columns"]
        described_items = coverage["tables_with_descriptions"] + coverage["columns_with_descriptions"]
        coverage["coverage_percentage"] = (described_items / total_describable * 100) if total_describable > 0 else 0

        logger.info(f"Coverage calculated: {coverage['coverage_percentage']:.1f}%")

        logger.info(f"Successfully prepared context preview for session {session_id}")
        return ContextPreviewResponse(
            tables=list(tables.values()),
            relationships=relationships_data,
            data_dictionary_coverage=coverage,
            use_case_text=use_case.business_goal
        )

    except Exception as e:
        logger.error(f"Error in get_context_preview for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# STEP 2: Generate Questions
@router.post("/sessions/{session_id}/generate-questions")
async def generate_questions(
    session_id: int,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Generate questions for fine-tuning session"""
    logger.info(f"Generating questions for session {session_id}")

    try:
        # Get session
        result = await db_session.execute(
            select(FineTuningSession).where(FineTuningSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.error(f"Session {session_id} not found for question generation")
            raise HTTPException(status_code=404, detail="Fine-tuning session not found")

        logger.info(f"Session found, current status: {session.status}, updating to generating_questions")

        # Update session status
        session.status = "generating_questions"
        session.current_step = "question_generation"
        await db_session.commit()
        logger.info(f"Session {session_id} status updated to generating_questions")

        # Add background task for question generation
        background_tasks.add_task(generate_questions_background, session_id)
        logger.info(f"Background task added for session {session_id}")

        return {"message": "Question generation started", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error starting question generation for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def generate_questions_background(session_id: int):
    """Background task to generate questions using AI"""
    from .llm import generate_text  # Import the LLM function

    # Create new session for background task
    async_session = create_background_session()

    async with async_session() as session:
        try:
            logger.info(f"Background task: Looking up session {session_id}")
            # Get session and related data
            result = await session.execute(
                select(FineTuningSession).where(FineTuningSession.id == session_id)
            )
            fine_tuning_session = result.scalar_one()
            logger.info(f"Background task: Found session, use_case_id: {fine_tuning_session.use_case_id}")

            # Get use case and schema data
            use_case_result = await session.execute(
                select(UseCase).where(UseCase.id == fine_tuning_session.use_case_id)
            )
            use_case = use_case_result.scalar_one()

            # Get schema snapshot
            snapshot_result = await session.execute(
                select(SchemaSnapshot).where(SchemaSnapshot.id == fine_tuning_session.schema_snapshot_id)
            )
            snapshot = snapshot_result.scalar_one()

            # Build context for AI
            context_parts = []

            # Add schema info
            schema_result = await session.execute(
                select(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == fine_tuning_session.schema_snapshot_id)
            )
            schema_metadata = schema_result.scalars().all()

            tables_info = {}
            for meta in schema_metadata:
                if meta.table_name not in tables_info:
                    tables_info[meta.table_name] = []
                tables_info[meta.table_name].append(f"{meta.column_name} ({meta.column_type})")

            context_parts.append("DATABASE SCHEMA:")
            for table_name, columns in tables_info.items():
                context_parts.append(f"Table: {table_name}")
                context_parts.append(f"Columns: {', '.join(columns)}")
                context_parts.append("")

            # Add data dictionary if requested
            if fine_tuning_session.include_full_dictionary:
                dict_result = await session.execute(
                    select(DataDictionary).where(DataDictionary.schema_snapshot_id == fine_tuning_session.schema_snapshot_id)
                )
                data_dict_entries = dict_result.scalars().all()

                if data_dict_entries:
                    context_parts.append("DATA DICTIONARY:")
                    for entry in data_dict_entries:
                        if entry.column_name:
                            context_parts.append(f"{entry.table_name}.{entry.column_name}: {entry.description or 'No description'}")
                        else:
                            context_parts.append(f"Table {entry.table_name}: {entry.description or 'No description'}")
                    context_parts.append("")

            # Add relationships
            rel_result = await session.execute(
                select(Relationship).where(Relationship.schema_snapshot_id == fine_tuning_session.schema_snapshot_id)
            )
            relationships = rel_result.scalars().all()

            if relationships:
                context_parts.append("TABLE RELATIONSHIPS:")
                for rel in relationships:
                    context_parts.append(f"{rel.source_table}.{rel.source_column} -> {rel.target_table}.{rel.target_column} ({rel.join_type})")
                context_parts.append("")

            # Build the prompt based on selected language
            if fine_tuning_session.language == "persian":
                prompt = f"""You are a Persian-speaking data analyst assistant.

Given:
{"".join(context_parts)}
Business use case: {use_case.business_goal}

Generate {fine_tuning_session.questions_count} realistic business questions in Persian (Farsi).

Rules:
- Questions must be in natural Persian language
- Questions must be answerable with this schema
- No SQL terms in questions
- Vary complexity from simple to complex
- No duplicates
- Focus on business analysis and reporting questions

Return a numbered list in Persian."""
            else:  # english
                prompt = f"""You are a data analyst assistant.

Given:
{"".join(context_parts)}
Business use case: {use_case.business_goal}

Generate {fine_tuning_session.questions_count} realistic business questions.

Rules:
- Questions must be answerable with this schema
- No SQL terms
- Vary complexity
- No duplicates

Return a numbered list."""

            # Call AI to generate questions
            llm_request = LLMRequest(prompt=prompt)
            llm_response = await generate_text(llm_request, session)

            # Parse the response to extract questions
            response_text = llm_response.response.strip()
            logger.info(f"Raw LLM response: {response_text[:300]}...")

            response_lines = response_text.split('\n')
            questions = []

            for line in response_lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # Remove numbering/prefixes
                    if line[0].isdigit():
                        # Find the first non-digit character after optional dot
                        parts = line.split('.', 1)
                        if len(parts) > 1:
                            question = parts[1].strip()
                        else:
                            question = line
                    elif line.startswith('-') or line.startswith('•'):
                        question = line[1:].strip()
                    else:
                        question = line

                    # Clean up the question
                    question = question.strip()
                    if question and len(question) > 5:  # Minimum length check
                        questions.append(question)

            # If no questions were extracted, try fallback parsing
            if not questions:
                logger.warning("No questions extracted from LLM response, using fallback parsing")
                # Split by double newlines or look for numbered items
                paragraphs = response_text.split('\n\n')
                for para in paragraphs:
                    para = para.strip()
                    if para and len(para) > 10:
                        # Clean and add as question
                        clean_para = para.replace('\n', ' ').strip()
                        if clean_para:
                            questions.append(clean_para)

            # Limit to requested count
            questions = questions[:fine_tuning_session.questions_count]

            # If still no questions, use language-appropriate fallbacks
            if not questions:
                if fine_tuning_session.language == "persian":
                    logger.warning("Using Persian fallback questions")
                    questions = [
                        "چه نوع داده‌هایی در بازار انرژی وجود دارد؟",
                        "چند رکورد در جدول اصلی وجود دارد؟",
                        "ساختار داده‌های معاملات انرژی چگونه است؟",
                        "کدام ستون‌ها شامل اطلاعات تاریخ هستند؟"
                    ][:fine_tuning_session.questions_count]
                else:
                    logger.warning("Using English fallback questions")
                    questions = [
                        "What types of data exist in the energy market?",
                        "How many records are there in the main table?",
                        "What is the structure of energy trading data?",
                        "Which columns contain date information?"
                    ][:fine_tuning_session.questions_count]

            logger.info(f"Extracted {len(questions)} questions: {questions[:2]}...")

            # Create question records - add to existing questions instead of replacing
            # Get current max index
            max_index_result = await session.execute(
                select(func.max(FineTuningQuestion.question_index))
                .where(FineTuningQuestion.session_id == session_id)
            )
            max_index = max_index_result.scalar() or -1

            # Create question records starting from next index
            for i, question_text in enumerate(questions):
                question = FineTuningQuestion(
                    session_id=session_id,
                    question_index=max_index + 1 + i,
                    question_text=question_text,
                    is_user_edited=False
                )
                session.add(question)

            # Update session - add to existing count
            logger.info(f"Background task: Successfully generated {len(questions)} questions")
            fine_tuning_session.status = "questions_generated"
            fine_tuning_session.generated_questions_count = (fine_tuning_session.generated_questions_count or 0) + len(questions)

            await session.commit()
            await session.refresh(fine_tuning_session)
            logger.info(f"Background task: Session {session_id} updated to status: {fine_tuning_session.status}, total questions_count: {fine_tuning_session.generated_questions_count}")

        except Exception as e:
            logger.error(f"Background task: Error generating questions for session {session_id}: {str(e)}", exc_info=True)
            # Update session with error
            try:
                await session.execute(
                    update(FineTuningSession)
                    .where(FineTuningSession.id == session_id)
                    .values(status="failed", current_step="question_generation")
                )
                await session.commit()
            except Exception as update_error:
                logger.error(f"Background task: Failed to update session status: {str(update_error)}", exc_info=True)
                # Ensure session is closed even if commit fails
                await session.close()


# STEP 2: Get Generated Questions
@router.get("/sessions/{session_id}/questions", response_model=List[FineTuningQuestionResponse])
async def get_generated_questions(
    session_id: int,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get generated questions for a session"""
    logger.info(f"Fetching questions for session {session_id}")

    try:
        result = await db_session.execute(
            select(FineTuningQuestion)
            .where(FineTuningQuestion.session_id == session_id)
            .order_by(FineTuningQuestion.question_index)
        )
        questions = result.scalars().all()
        logger.info(f"Found {len(questions)} questions for session {session_id}")

        return [
            FineTuningQuestionResponse(
                id=q.id,
                question_index=q.question_index,
                question_text=q.question_text,
                is_user_edited=q.is_user_edited,
                generated_sql=q.generated_sql,
                execution_status=q.execution_status,
                execution_result=q.execution_result,
                execution_error=q.execution_error,
                user_approval=q.user_approval,
                user_feedback=q.user_feedback
            )
            for q in questions
        ]

    except Exception as e:
        logger.error(f"Error fetching questions for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# STEP 2: Update Questions (for user editing)
@router.put("/sessions/{session_id}/questions")
async def update_questions(
    session_id: int,
    request: QuestionGenerationRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Update questions in the session (user edits)"""
    # Delete existing questions
    existing_questions = (await db_session.execute(
        select(FineTuningQuestion).where(FineTuningQuestion.session_id == session_id)
    )).scalars().all()

    for q in existing_questions:
        await db_session.delete(q)

    # Add updated questions
    for i, question_text in enumerate(request.questions):
        question = FineTuningQuestion(
            session_id=session_id,
            question_index=i,
            question_text=question_text,
            is_user_edited=True
        )
        db_session.add(question)

    # Update session
    await db_session.execute(
        update(FineTuningSession)
        .where(FineTuningSession.id == session_id)
        .values(generated_questions_count=len(request.questions))
    )

    await db_session.commit()

    return {"message": "Questions updated successfully"}


# STEP 3: Generate SQL for Question
@router.post("/questions/{question_id}/generate-sql")
async def generate_sql_for_question(
    question_id: int,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Generate SQL for a specific question"""
    # Get question
    result = await db_session.execute(
        select(FineTuningQuestion).where(FineTuningQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Update question status
    question.execution_status = "generating_sql"
    await db_session.commit()

    # Add background task
    background_tasks.add_task(generate_sql_background, question_id)

    return {"message": "SQL generation started", "question_id": question_id}


async def generate_sql_background(question_id: int):
    """Background task to generate SQL using AI"""
    # Create new session for background task
    async_session = create_background_session()

    async with async_session() as session:
        try:
            # Get question and related data
            question_result = await session.execute(
                select(FineTuningQuestion).where(FineTuningQuestion.id == question_id)
            )
            question = question_result.scalar_one()

            # Get session and use case
            session_result = await session.execute(
                select(FineTuningSession).where(FineTuningSession.id == question.session_id)
            )
            fine_tuning_session = session_result.scalar_one()

            use_case_result = await session.execute(
                select(UseCase).where(UseCase.id == fine_tuning_session.use_case_id)
            )
            use_case = use_case_result.scalar_one()

            # Build context for AI
            context_parts = []

            # Add schema info
            schema_result = await session.execute(
                select(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == fine_tuning_session.schema_snapshot_id)
            )
            schema_metadata = schema_result.scalars().all()

            tables_info = {}
            for meta in schema_metadata:
                if meta.table_name not in tables_info:
                    tables_info[meta.table_name] = []
                tables_info[meta.table_name].append(f"{meta.column_name} ({meta.column_type})")

            context_parts.append("DATABASE SCHEMA:")
            for table_name, columns in tables_info.items():
                context_parts.append(f"Table: {table_name}")
                context_parts.append(f"Columns: {', '.join(columns)}")
                context_parts.append("")

            # Add data dictionary (VERY IMPORTANT)
            dict_result = await session.execute(
                select(DataDictionary).where(DataDictionary.schema_snapshot_id == fine_tuning_session.schema_snapshot_id)
            )
            data_dict_entries = dict_result.scalars().all()

            if data_dict_entries:
                context_parts.append("DATA DICTIONARY:")
                for entry in data_dict_entries:
                    if entry.column_name:
                        context_parts.append(f"{entry.table_name}.{entry.column_name}: {entry.description or 'No description'}")
                        if entry.example_values:
                            try:
                                examples = json.loads(entry.example_values)
                                context_parts.append(f"  Examples: {', '.join(examples[:3])}")
                            except:
                                pass
                    else:
                        context_parts.append(f"Table {entry.table_name}: {entry.description or 'No description'}")
                context_parts.append("")

            # Add relationships
            rel_result = await session.execute(
                select(Relationship).where(Relationship.schema_snapshot_id == fine_tuning_session.schema_snapshot_id)
            )
            relationships = rel_result.scalars().all()

            if relationships:
                context_parts.append("TABLE RELATIONSHIPS:")
                for rel in relationships:
                    context_parts.append(f"{rel.source_table}.{rel.source_column} -> {rel.target_table}.{rel.target_column} ({rel.join_type}: {rel.description})")
                context_parts.append("")

            # Build the prompt
            prompt = f"""You are a Text-to-SQL expert for Persian business data.

Context:
{"".join(context_parts)}
Use case: {use_case.business_goal}

Persian Question: {question.question_text}

Rules:
- Generate ONE SELECT query only
- Use explicit JOINs when needed
- Use only existing tables and columns from schema
- Prefer data dictionary descriptions over guessing
- Handle Persian column/table names correctly
- No hallucination - only use provided schema
- Return clean, executable SQL

Return ONLY the SQL query, no explanations."""

            # Call AI to generate SQL
            llm_request = LLMRequest(prompt=prompt, temperature=0.1, max_tokens=1024)
            from .llm import generate_text
            llm_response = await generate_text(llm_request, session)

            # Extract SQL from response
            sql = llm_response.response.strip()

            # Clean up the SQL (remove markdown formatting if present)
            if sql.startswith("```sql"):
                sql = sql[6:]
            if sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]

            sql = sql.strip()

            # Update question with generated SQL
            question.generated_sql = sql
            question.execution_status = "sql_generated"

            await session.commit()

        except Exception as e:
            logger.error(f"Background task: Error generating SQL for question {question_id}: {str(e)}", exc_info=True)
            # Update question with error
            try:
                await session.execute(
                    update(FineTuningQuestion)
                    .where(FineTuningQuestion.id == question_id)
                    .values(
                        sql_generation_error=str(e),
                        execution_status="sql_generation_failed"
                    )
                )
                await session.commit()
            except Exception as update_error:
                logger.error(f"Background task: Failed to update question status: {str(update_error)}", exc_info=True)
                await session.close()


# STEP 3: Execute SQL for Question
@router.post("/questions/{question_id}/execute")
async def execute_sql_for_question(
    question_id: int,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Execute SQL for a specific question"""
    # Get question
    result = await db_session.execute(
        select(FineTuningQuestion).where(FineTuningQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if not question.generated_sql:
        raise HTTPException(status_code=400, detail="No SQL generated for this question")

    # Update question status
    question.execution_status = "executing"
    await db_session.commit()

    # Add background task
    background_tasks.add_task(execute_sql_background, question_id)

    return {"message": "SQL execution started", "question_id": question_id}


async def execute_sql_background(question_id: int):
    """Background task to execute SQL"""
    logger.info(f"Starting background SQL execution for question {question_id}")

    import time

    # Create new session for background task
    async_session = create_background_session()

    async with async_session() as session:
        try:
            logger.info(f"Background task: Looking up question {question_id}")
            # Get question and session data
            question_result = await session.execute(
                select(FineTuningQuestion).where(FineTuningQuestion.id == question_id)
            )
            question = question_result.scalar_one()
            logger.info(f"Background task: Found question, SQL length: {len(question.generated_sql or '')}")

            session_result = await session.execute(
                select(FineTuningSession).where(FineTuningSession.id == question.session_id)
            )
            fine_tuning_session = session_result.scalar_one()
            logger.info(f"Background task: Found session {fine_tuning_session.id}")

            # Get database connection
            logger.info("Background task: Getting database connection")
            connection = await get_db_connection_for_snapshot(fine_tuning_session.schema_snapshot_id, session)

            # Import database connector service
            from services.db_connector import DirectDatabaseConnector

            connector = DirectDatabaseConnector(
                db_type=connection.db_type,
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=connection.password_encrypted,
                database=connection.database_name
            )

            # Execute query
            logger.info("Background task: Executing SQL query")
            start_time = time.time()
            try:
                results = await connector.execute_query(question.generated_sql, limit=100)  # Limit results for safety
                execution_time = int((time.time() - start_time) * 1000)
                logger.info(f"Background task: Query executed successfully in {execution_time}ms, {len(results)} rows returned")

                # Store results
                question.execution_result = json.dumps(results)
                question.execution_status = "success"
                question.execution_duration_ms = execution_time

            except Exception as exec_error:
                execution_time = int((time.time() - start_time) * 1000)
                logger.error(f"Background task: Query execution failed: {str(exec_error)}")
                question.execution_error = str(exec_error)
                question.execution_status = "error"
                question.execution_duration_ms = execution_time

            await session.commit()
            logger.info(f"Background task: Question {question_id} execution completed")

        except Exception as e:
            logger.error(f"Background task: Error in execute_sql_background for question {question_id}: {str(e)}", exc_info=True)
            # Update question with error
            try:
                await session.execute(
                    update(FineTuningQuestion)
                    .where(FineTuningQuestion.id == question_id)
                    .values(
                        execution_error=str(e),
                        execution_status="execution_failed"
                    )
                )
                await session.commit()
            except Exception as update_error:
                logger.error(f"Background task: Failed to update question status: {str(update_error)}", exc_info=True)
                await session.close()


# STEP 3: Submit User Feedback for Question
@router.post("/questions/{question_id}/feedback")
async def submit_question_feedback(
    question_id: int,
    request: SQLExecutionRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Submit user approval/rejection and feedback for a question"""
    # Get question
    result = await db_session.execute(
        select(FineTuningQuestion).where(FineTuningQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Update question
    question.user_approval = request.approval
    question.user_feedback = request.feedback

    # Update session counters
    session_result = await db_session.execute(
        select(FineTuningSession).where(FineTuningSession.id == question.session_id)
    )
    session = session_result.scalar_one()

    if request.approval == "approved":
        session.approved_questions_count = session.approved_questions_count + 1
    elif request.approval == "rejected":
        session.rejected_questions_count = session.rejected_questions_count + 1

    # Calculate confidence score
    total_processed = session.approved_questions_count + session.rejected_questions_count
    if total_processed > 0:
        session.confidence_score = session.approved_questions_count / total_processed

    await db_session.commit()

    return {"message": "Feedback submitted successfully"}


# STEP 4: Generate Use Case Refinement
@router.post("/sessions/{session_id}/refine-use-case", response_model=UseCaseRefinementResponse)
async def refine_use_case(
    session_id: int,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Generate refined use case based on execution results"""
    # Get session
    result = await db_session.execute(
        select(FineTuningSession).where(FineTuningSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Fine-tuning session not found")

    # Update session status
    session.status = "refining_use_case"
    session.current_step = "use_case_refinement"
    await db_session.commit()

    # Get use case and questions
    use_case_result = await db_session.execute(
        select(UseCase).where(UseCase.id == session.use_case_id)
    )
    use_case = use_case_result.scalar_one()

    questions_result = await db_session.execute(
        select(FineTuningQuestion)
        .where(FineTuningQuestion.session_id == session_id)
        .order_by(FineTuningQuestion.question_index)
    )
    questions = questions_result.scalars().all()

    # Build refinement prompt
    prompt_parts = []
    prompt_parts.append(f"Original use case: {use_case.business_goal}")
    prompt_parts.append("")

    prompt_parts.append("Tested questions:")
    for q in questions:
        prompt_parts.append(f"Question: {q.question_text}")
        prompt_parts.append(f"SQL: {q.generated_sql or 'No SQL generated'}")

        if q.execution_status == "success":
            prompt_parts.append("Execution result: SUCCESS")
        elif q.execution_status == "error":
            prompt_parts.append(f"Execution error: {q.execution_error}")
        else:
            prompt_parts.append("Execution result: Not executed")

        prompt_parts.append(f"User approval: {q.user_approval or 'Not reviewed'}")
        if q.user_feedback:
            prompt_parts.append(f"User feedback: {q.user_feedback}")
        prompt_parts.append("")

    prompt_parts.append("Schema + dictionary + relations: [Already known from context]")

    prompt = f"""You are refining a business use case for a Text-to-SQL system.

{"".join(prompt_parts)}

Task:
Improve the use case by:
- Clarifying ambiguities
- Making table/column usage explicit
- Preventing previously failed SQL patterns

Rules:
- Do NOT change business intent
- Only add clarifications
- Keep it concise

Return:
1. Updated use case text
2. Short summary of changes"""

    # Call AI for refinement
    llm_request = LLMRequest(prompt=prompt, temperature=0.3, max_tokens=1024)
    from .llm import generate_text
    llm_response = await generate_text(llm_request, db_session)

    # Parse response
    response_text = llm_response.response.strip()
    parts = response_text.split('\n\n', 1)

    if len(parts) >= 2:
        refined_use_case = parts[0].strip()
        summary = parts[1].strip()
    else:
        # Fallback parsing
        lines = response_text.split('\n')
        refined_use_case = lines[0] if lines else "Unable to refine use case"
        summary = " ".join(lines[1:]) if len(lines) > 1 else "No summary available"

    # Create new use case version
    # Get next version number
    version_result = await db_session.execute(
        select(func.max(UseCaseVersion.version_number))
        .where(UseCaseVersion.original_use_case_id == use_case.id)
    )
    max_version = version_result.scalar() or 0
    next_version = max_version + 1

    use_case_version = UseCaseVersion(
        original_use_case_id=use_case.id,
        schema_snapshot_id=use_case.schema_snapshot_id,
        version_number=next_version,
        version_description=f"Fine-tuned based on {session.approved_questions_count} approved and {session.rejected_questions_count} rejected questions",
        name=use_case.name,
        business_goal=refined_use_case,
        example_questions=use_case.example_questions,
        example_queries=use_case.example_queries,
        output_style=use_case.output_style,
        is_ai_generated=True,
        business_context=use_case.business_context,
        primary_audience=use_case.primary_audience,
        typical_questions=use_case.typical_questions,
        output_preference=use_case.output_preference,
        dictionary_version=use_case.dictionary_version,
        relationships_version=use_case.relationships_version,
        confidence_score=session.confidence_score
    )

    db_session.add(use_case_version)

    # Update session
    session.status = "completed"
    session.current_step = None
    session.refined_use_case_version_id = use_case_version.id

    await db_session.commit()
    await db_session.refresh(use_case_version)

    return UseCaseRefinementResponse(
        original_use_case=use_case.business_goal,
        refined_use_case=refined_use_case,
        summary_of_changes=summary,
        new_version_id=use_case_version.id
    )


# Get Session Status
@router.post("/sessions/{session_id}/force-complete-questions")
async def force_complete_questions(session_id: int, db_session: AsyncSession = Depends(get_db_session)):
    """Force complete question generation for testing"""
    logger.info(f"Forcing question generation completion for session {session_id}")

    try:
        result = await db_session.execute(
            select(FineTuningSession).where(FineTuningSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Delete existing questions first
        existing_questions = (await db_session.execute(
            select(FineTuningQuestion).where(FineTuningQuestion.session_id == session_id)
        )).scalars().all()

        for q in existing_questions:
            await db_session.delete(q)

        # Add dummy questions based on language
        if session.language == "persian":
            dummy_questions = [
                "چه نوع داده‌هایی در بازار انرژی وجود دارد؟",
                "چند رکورد در جدول اصلی وجود دارد؟",
                "ساختار داده‌های معاملات انرژی چگونه است؟",
                "کدام ستون‌ها شامل اطلاعات تاریخ هستند؟",
                "شناسه‌های کلیدی در مجموعه داده چیست؟"
            ]
        else:
            dummy_questions = [
                "What types of data exist in the energy market?",
                "How many records are there in the main table?",
                "What is the structure of energy trading data?",
                "Which columns contain date information?",
                "What are the key identifiers in the dataset?"
            ]

        for i, question_text in enumerate(dummy_questions):
            question = FineTuningQuestion(
                session_id=session_id,
                question_index=i,
                question_text=question_text,
                is_user_edited=False
            )
            db_session.add(question)

        # Update session
        session.status = "questions_generated"
        session.generated_questions_count = len(dummy_questions)

        await db_session.commit()

        logger.info(f"Force completed questions for session {session_id}")
        return {"message": f"Added {len(dummy_questions)} Persian questions"}

    except Exception as e:
        logger.error(f"Error force completing questions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/questions/{question_id}/force-complete-sql")
async def force_complete_sql(question_id: int, db_session: AsyncSession = Depends(get_db_session)):
    """Force complete SQL generation for testing"""
    logger.info(f"Forcing SQL completion for question {question_id}")

    try:
        result = await db_session.execute(
            select(FineTuningQuestion).where(FineTuningQuestion.id == question_id)
        )
        question = result.scalar_one_or_none()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Add mock SQL
        mock_sql = "SELECT id, name, date_created FROM energy_trading_data LIMIT 10;"
        question.generated_sql = mock_sql
        question.execution_status = "sql_generated"

        await db_session.commit()

        logger.info(f"Force completed SQL for question {question_id}")
        return {"message": "Mock SQL added", "sql": mock_sql}

    except Exception as e:
        logger.error(f"Error force completing SQL: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}", response_model=FineTuningSessionResponse)
async def get_session_status(
    session_id: int,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get fine-tuning session status"""
    logger.debug(f"Getting status for session {session_id}")

    result = await db_session.execute(
        select(FineTuningSession).where(FineTuningSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        logger.warning(f"Session {session_id} not found")
        raise HTTPException(status_code=404, detail="Fine-tuning session not found")

    return FineTuningSessionResponse(
        id=session.id,
        use_case_id=session.use_case_id,
        status=session.status,
        current_step=session.current_step,
        include_full_dictionary=session.include_full_dictionary,
        questions_count=session.questions_count,
        language=session.language,
        generated_questions_count=session.generated_questions_count,
        approved_questions_count=session.approved_questions_count,
        rejected_questions_count=session.rejected_questions_count,
        confidence_score=session.confidence_score,
        created_at=session.created_at
    )