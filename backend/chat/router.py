from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from loguru import logger
from pydantic import BaseModel
from datetime import datetime
import uuid
import json

from .engine import ChatEngine
from .schemas import ChatRequest, ChatResponse, ChatLanguage
from api.database import get_db_session
from api.db_models import ChatBot, ChatSession, ChatMessage, SchemaSnapshot, LLMModel

router = APIRouter(tags=["chat"])


# Pydantic models for API responses
class ChatBotResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    snapshot_id: int
    snapshot_name: Optional[str] = None
    model_id: int
    model_name: Optional[str] = None
    language: str
    session_count: int
    total_message_count: int
    last_activity_at: Optional[datetime]
    created_at: datetime


class CreateChatBotRequest(BaseModel):
    name: str
    description: Optional[str] = None
    snapshot_id: int
    model_id: int
    language: str


class ChatSessionResponse(BaseModel):
    id: int
    bot_id: int
    conversation_id: str
    title: Optional[str]
    message_count: int
    last_activity_at: datetime
    created_at: datetime


class CreateChatSessionRequest(BaseModel):
    title: Optional[str] = None


class CreateChatSessionResponse(BaseModel):
    conversation_id: str
    session: ChatSessionResponse


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    generated_sql: Optional[str] = None
    execution_status: Optional[str] = None
    row_count: Optional[int] = None
    execution_time_ms: Optional[int] = None
    metadata: Optional[dict] = None
    created_at: datetime


class ChatSessionDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]


class ChatBotDetailResponse(BaseModel):
    bot: ChatBotResponse
    sessions: List[ChatSessionResponse]


# ===== ChatBot Endpoints =====

@router.get("/bots", response_model=List[ChatBotResponse])
async def list_chat_bots(
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all chat bots ordered by last activity"""
    try:
        stmt = (
            select(ChatBot)
            .order_by(ChatBot.last_activity_at.desc().nulls_last(), ChatBot.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        bots = result.scalars().all()

        bot_responses = []
        for bot in bots:
            # Get snapshot name
            snapshot_result = await session.execute(
                select(SchemaSnapshot.name).where(SchemaSnapshot.id == bot.snapshot_id)
            )
            snapshot_name = snapshot_result.scalar_one_or_none()

            # Get model name
            model_result = await session.execute(
                select(LLMModel.name).where(LLMModel.id == bot.model_id)
            )
            model_name = model_result.scalar_one_or_none()

            bot_responses.append(ChatBotResponse(
                id=bot.id,
                name=bot.name,
                description=bot.description,
                snapshot_id=bot.snapshot_id,
                snapshot_name=snapshot_name,
                model_id=bot.model_id,
                model_name=model_name,
                language=bot.language,
                session_count=bot.session_count,
                total_message_count=bot.total_message_count,
                last_activity_at=bot.last_activity_at,
                created_at=bot.created_at
            ))

        return bot_responses
    except Exception as e:
        logger.error(f"Failed to list chat bots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots", response_model=ChatBotResponse)
async def create_chat_bot(
    request: CreateChatBotRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new chat bot with configuration"""
    try:
        chat_bot = ChatBot(
            name=request.name,
            description=request.description,
            snapshot_id=request.snapshot_id,
            model_id=request.model_id,
            language=request.language,
            session_count=0,
            total_message_count=0
        )

        session.add(chat_bot)
        await session.commit()
        await session.refresh(chat_bot)

        # Get snapshot and model names
        snapshot_result = await session.execute(
            select(SchemaSnapshot.name).where(SchemaSnapshot.id == chat_bot.snapshot_id)
        )
        snapshot_name = snapshot_result.scalar_one_or_none()

        model_result = await session.execute(
            select(LLMModel.name).where(LLMModel.id == chat_bot.model_id)
        )
        model_name = model_result.scalar_one_or_none()

        return ChatBotResponse(
            id=chat_bot.id,
            name=chat_bot.name,
            description=chat_bot.description,
            snapshot_id=chat_bot.snapshot_id,
            snapshot_name=snapshot_name,
            model_id=chat_bot.model_id,
            model_name=model_name,
            language=chat_bot.language,
            session_count=chat_bot.session_count,
            total_message_count=chat_bot.total_message_count,
            last_activity_at=chat_bot.last_activity_at,
            created_at=chat_bot.created_at
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create chat bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}", response_model=ChatBotDetailResponse)
async def get_chat_bot(
    bot_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Get a chat bot with all its sessions"""
    try:
        # Get bot
        stmt = select(ChatBot).where(ChatBot.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Chat bot not found")

        # Get sessions
        sessions_stmt = (
            select(ChatSession)
            .where(ChatSession.bot_id == bot_id)
            .order_by(ChatSession.last_activity_at.desc())
        )
        sessions_result = await session.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()

        # Get snapshot and model names
        snapshot_result = await session.execute(
            select(SchemaSnapshot.name).where(SchemaSnapshot.id == bot.snapshot_id)
        )
        snapshot_name = snapshot_result.scalar_one_or_none()

        model_result = await session.execute(
            select(LLMModel.name).where(LLMModel.id == bot.model_id)
        )
        model_name = model_result.scalar_one_or_none()

        bot_response = ChatBotResponse(
            id=bot.id,
            name=bot.name,
            description=bot.description,
            snapshot_id=bot.snapshot_id,
            snapshot_name=snapshot_name,
            model_id=bot.model_id,
            model_name=model_name,
            language=bot.language,
            session_count=bot.session_count,
            total_message_count=bot.total_message_count,
            last_activity_at=bot.last_activity_at,
            created_at=bot.created_at
        )

        session_responses = [
            ChatSessionResponse(
                id=s.id,
                bot_id=s.bot_id,
                conversation_id=s.conversation_id,
                title=s.title,
                message_count=s.message_count,
                last_activity_at=s.last_activity_at,
                created_at=s.created_at
            )
            for s in sessions
        ]

        return ChatBotDetailResponse(
            bot=bot_response,
            sessions=session_responses
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bots/{bot_id}")
async def delete_chat_bot(
    bot_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Delete a chat bot and all its sessions"""
    try:
        # Get bot
        stmt = select(ChatBot).where(ChatBot.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Chat bot not found")

        # Delete bot (cascade will delete sessions and messages)
        await session.delete(bot)
        await session.commit()

        return {"message": "Chat bot deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete chat bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ChatSession Endpoints (now under a bot) =====

@router.get("/bots/{bot_id}/sessions", response_model=List[ChatSessionResponse])
async def list_bot_sessions(
    bot_id: int,
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all sessions for a specific chat bot"""
    try:
        # Verify bot exists
        bot_stmt = select(ChatBot).where(ChatBot.id == bot_id)
        bot_result = await session.execute(bot_stmt)
        bot = bot_result.scalar_one_or_none()
        if not bot:
            raise HTTPException(status_code=404, detail="Chat bot not found")

        # Query sessions
        stmt = (
            select(ChatSession)
            .where(ChatSession.bot_id == bot_id)
            .order_by(ChatSession.last_activity_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        sessions = result.scalars().all()

        session_responses = [
            ChatSessionResponse(
                id=s.id,
                bot_id=s.bot_id,
                conversation_id=s.conversation_id,
                title=s.title,
                message_count=s.message_count,
                last_activity_at=s.last_activity_at,
                created_at=s.created_at
            )
            for s in sessions
        ]

        return session_responses
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list bot sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/sessions", response_model=CreateChatSessionResponse)
async def create_bot_session(
    bot_id: int,
    request: CreateChatSessionRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new chat session for a bot"""
    try:
        # Get bot to use its settings
        bot_stmt = select(ChatBot).where(ChatBot.id == bot_id)
        bot_result = await session.execute(bot_stmt)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise HTTPException(status_code=404, detail="Chat bot not found")

        conversation_id = str(uuid.uuid4())
        title = request.title or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Create session using bot's settings
        chat_session = ChatSession(
            bot_id=bot_id,
            conversation_id=conversation_id,
            title=title,
            message_count=0
        )

        session.add(chat_session)
        
        # Update bot statistics
        bot.session_count += 1
        bot.last_activity_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(chat_session)

        session_response = ChatSessionResponse(
            id=chat_session.id,
            bot_id=chat_session.bot_id,
            conversation_id=chat_session.conversation_id,
            title=chat_session.title,
            message_count=chat_session.message_count,
            last_activity_at=chat_session.last_activity_at,
            created_at=chat_session.created_at
        )

        return CreateChatSessionResponse(
            conversation_id=conversation_id,
            session=session_response
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create bot session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all chat sessions ordered by last activity"""
    try:
        # Query sessions with related data
        stmt = (
            select(ChatSession)
            .order_by(ChatSession.last_activity_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        sessions = result.scalars().all()

        session_responses = [
            ChatSessionResponse(
                id=s.id,
                bot_id=s.bot_id,
                conversation_id=s.conversation_id,
                title=s.title,
                message_count=s.message_count,
                last_activity_at=s.last_activity_at,
                created_at=s.created_at
            )
            for s in sessions
        ]

        return session_responses
    except Exception as e:
        logger.error(f"Failed to list chat sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/sessions/{conversation_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Get a chat session with all its messages"""
    try:
        # Get session
        stmt = select(ChatSession).where(ChatSession.conversation_id == conversation_id)
        result = await session.execute(stmt)
        chat_session = result.scalar_one_or_none()

        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Get messages
        messages_stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages_result = await session.execute(messages_stmt)
        messages = messages_result.scalars().all()

        # Get bot for settings
        bot_stmt = select(ChatBot).where(ChatBot.id == chat_session.bot_id)
        bot_result = await session.execute(bot_stmt)
        bot = bot_result.scalar_one_or_none()

        session_response = ChatSessionResponse(
            id=chat_session.id,
            bot_id=chat_session.bot_id,
            conversation_id=chat_session.conversation_id,
            title=chat_session.title,
            message_count=chat_session.message_count,
            last_activity_at=chat_session.last_activity_at,
            created_at=chat_session.created_at
        )

        message_responses = []
        for msg in messages:
            metadata = None
            if msg.message_metadata:
                try:
                    metadata = json.loads(msg.message_metadata)
                except:
                    pass

            message_responses.append(ChatMessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                generated_sql=msg.generated_sql,
                execution_status=msg.execution_status,
                row_count=msg.row_count,
                execution_time_ms=msg.execution_time_ms,
                metadata=metadata,
                created_at=msg.created_at
            ))

        return ChatSessionDetailResponse(
            session=session_response,
            messages=message_responses
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{conversation_id}")
async def delete_chat_session(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Delete a chat session and all its messages"""
    try:
        # Get session
        stmt = select(ChatSession).where(ChatSession.conversation_id == conversation_id)
        result = await session.execute(stmt)
        chat_session = result.scalar_one_or_none()

        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Delete messages (cascade should handle this, but explicit delete is safer)
        await session.execute(
            select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
        )

        # Delete session
        await session.delete(chat_session)
        await session.commit()

        return {"message": "Chat session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ChatResponse)
async def execute_chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Execute chat using the new production-grade ChatEngine.
    Also saves messages to the database for persistence.

    This endpoint uses the isolated ChatEngine module that provides:
    - Full Text-to-SQL lifecycle orchestration
    - Context loading and aggregation
    - LLM gateway abstraction
    - SQL validation and execution
    - Complete traceability
    """
    try:
        logger.info(f"Chat execution requested: snapshot_id={request.snapshot_id}, model_id={request.selected_model_id}, question='{request.user_question[:50]}...'")

        # Get or create chat session
        conversation_id = request.conversation_id
        chat_session_db = None

        if conversation_id:
            # Get existing session
            stmt = select(ChatSession).where(ChatSession.conversation_id == conversation_id)
            result = await session.execute(stmt)
            chat_session_db = result.scalar_one_or_none()

        if not chat_session_db:
            # Need bot_id to create session - this should come from the request
            # For now, we'll require conversation_id or bot_id in request
            # This is a limitation - we need to modify ChatRequest to include bot_id
            raise HTTPException(
                status_code=400,
                detail="conversation_id or bot_id required to create session"
            )

        # Get bot settings from session
        bot_stmt = select(ChatBot).where(ChatBot.id == chat_session_db.bot_id)
        bot_result = await session.execute(bot_stmt)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise HTTPException(status_code=404, detail="Chat bot not found")

        # Use bot's settings for the request (store values before using them)
        effective_snapshot_id = bot.snapshot_id
        effective_model_id = bot.model_id
        bot_language_str = bot.language
        
        # Convert language string to ChatLanguage enum
        if bot_language_str in ["en", "english"]:
            effective_language = ChatLanguage.ENGLISH
        elif bot_language_str in ["fa", "persian", "farsi"]:
            effective_language = ChatLanguage.PERSIAN
        else:
            effective_language = ChatLanguage.ENGLISH

        # Save user message
        user_message = ChatMessage(
            session_id=chat_session_db.id,
            conversation_id=conversation_id,
            role="user",
            content=request.user_question
        )
        session.add(user_message)

        # Create database connector for the snapshot (use bot's snapshot)
        from db.dependencies import get_database_connector
        connector = await get_database_connector(effective_snapshot_id, session)

        # Initialize ChatEngine - always use real mode
        chat_engine = ChatEngine(session, connector)

        # Process the chat request with bot's settings
        chat_request = ChatRequest(
            snapshot_id=effective_snapshot_id,
            selected_model_id=effective_model_id,
            language=effective_language,
            user_question=request.user_question,
            conversation_id=conversation_id
        )
        response = await chat_engine.process_chat_request(chat_request)

        # Update response with conversation_id
        if not response.conversation_id:
            response.conversation_id = conversation_id

        logger.info(f"Chat execution completed: success={response.success}, sql_generated={len(response.generated_sql) > 0}, rows_returned={response.row_count}")

        # Save assistant message
        assistant_content = response.conversational_response or (
            f"Generated SQL:\n```sql\n{response.generated_sql}\n```" if response.generated_sql else "No SQL generated"
        )
        
        metadata_dict = {
            "success": response.success,
            "execution_status": response.execution_status,
            "sql_validation_status": response.sql_validation_status,
            "context_hash": response.context_hash,
            "conversational_response": response.conversational_response
        }

        assistant_message = ChatMessage(
            session_id=chat_session_db.id,
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            generated_sql=response.generated_sql,
            execution_status=response.execution_status,
            row_count=response.row_count,
            execution_time_ms=response.execution_time_ms,
            message_metadata=json.dumps(metadata_dict)
        )
        session.add(assistant_message)

        # Update session message count and last activity
        chat_session_db.message_count += 2  # user + assistant
        chat_session_db.last_activity_at = datetime.utcnow()
        
        # Update title from first user question if still default
        if not chat_session_db.title or chat_session_db.title.startswith("Session "):
            first_question = request.user_question[:50]
            if len(request.user_question) > 50:
                first_question += "..."
            chat_session_db.title = first_question

        # Update bot statistics
        bot.total_message_count += 2
        bot.last_activity_at = datetime.utcnow()

        await session.commit()

        return response

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Chat execution failed: {e}", exc_info=True)

        # Use stored values if available, otherwise fallback to request values
        error_snapshot_id = effective_snapshot_id if 'effective_snapshot_id' in locals() else request.snapshot_id
        error_model_id = effective_model_id if 'effective_model_id' in locals() else request.selected_model_id

        # Return error response matching the expected schema
        return ChatResponse(
            success=False,
            user_question=request.user_question,
            generated_sql="",
            rows=[],
            row_count=0,
            snapshot_id=error_snapshot_id,
            model_used=f"model_{error_model_id}",
            execution_status="error",
            error_message=str(e),
            context_hash="",
            sql_validation_status="failed",
            execution_time_ms=0,
            conversation_id=request.conversation_id
        )
