import time
import uuid
import logging
import json
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from db import DatabaseConnector
from ..schemas import (
    ChatRequest, ChatResponse, ChatContext, ChatLanguage,
    ConversationState
)
from ..schemas import ChatLanguage
from .context_loader import ContextLoader
from .context_cache import ContextCache
from .query_result_cache import QueryResultCache
from .fast_intent_detector import FastIntentDetector
from .prompt_engine import PromptEngine
from .llm_gateway import LLMGateway
from .sql_pipeline import SQLPipeline
from .conversation_state import ConversationStateManager
from ..pipeline import PipelineFactory
from ..pipeline.pipeline_context import PipelineContext
from ..sql_guard import SQLGuard
from ..logging import get_chat_logger, request_context, create_request_id
logger = logging.getLogger(__name__)


class ChatEngine:
    """
    Production-grade Chat Engine orchestrator with optimized initialization.

    This module orchestrates the full Text-to-SQL lifecycle:
    - Loads context (with caching)
    - Builds prompts
    - Calls LLM for reasoning and SQL generation
    - Validates and executes SQL
    - Returns results with full traceability

    Supports pre-initialization for better performance.
    """

    def __init__(self, session: AsyncSession, connector: DatabaseConnector):
        # Initialize centralized logger
        self.logger = get_chat_logger("ChatEngine")
        """
        Initialize the Chat Engine.

        Args:
            session: Database session for metadata access
            connector: Database connector for snapshot queries
        """
        self.session = session
        self.connector = connector

        # Initialize components
        self.fast_intent_detector = FastIntentDetector()
        self.context_loader = ContextLoader(session)
        self.context_cache = ContextCache(ttl_seconds=3600)  # 1 hour TTL
        self.query_result_cache = QueryResultCache(ttl_seconds=300)  # 5 minutes TTL
        self.prompt_engine = PromptEngine()
        self.llm_gateway = LLMGateway(session)

        # Initialize legacy SQL pipeline (for backward compatibility)
        self.sql_pipeline = SQLPipeline(
            llm_gateway=self.llm_gateway,
            prompt_engine=self.prompt_engine,
            connector=connector,
            result_cache=self.query_result_cache
        )

        # Initialize new modular pipeline
        self._initialize_modular_pipeline(connector)

        self.conversation_manager = ConversationStateManager(session=session)

        # Pre-initialized resources (for optimization)
        self._preloaded_context: Optional[ChatContext] = None
        self._context_snapshot_id: Optional[int] = None
        self._initialized = False

    def _initialize_modular_pipeline(self, connector: DatabaseConnector):
        """Initialize the new modular pipeline architecture"""
        # Get components from legacy SQL pipeline
        semantic_guard = self.sql_pipeline.semantic_guard
        sql_critic = self.sql_pipeline.critic
        sql_validator = self.sql_pipeline.validator
        sql_executor = self.sql_pipeline.executor

        # Create new modular pipeline
        self.modular_pipeline = PipelineFactory.create_sql_pipeline_orchestrator(
            llm_gateway=self.llm_gateway,
            prompt_engine=self.prompt_engine,
            semantic_guard=semantic_guard,
            sql_critic=sql_critic,
            sql_validator=sql_validator,
            sql_executor=sql_executor
        )

        logger.info(f"🔧 MODULAR_PIPELINE_INITIALIZED | Stages: {len(self.modular_pipeline.stages)}")

    async def initialize_for_bot(self, bot_id: int, snapshot_id: int, model_id: int):
        """
        Pre-initialize the chat engine for a specific bot.
        This loads context and warms up connections for better performance.
        """
        try:
            logger.info(f"🔧 INITIALIZING ChatEngine for bot {bot_id}, snapshot {snapshot_id}, model {model_id}")

            # Pre-load context if not already loaded or different snapshot
            if self._preloaded_context is None or self._context_snapshot_id != snapshot_id:
                logger.info(f"Pre-loading context for snapshot {snapshot_id}")
                self._preloaded_context = await self.context_cache.get_context(
                    snapshot_id,
                    self.context_loader
                )
                self._context_snapshot_id = snapshot_id
                logger.info(f"Context pre-loaded with {len(self._preloaded_context.schema_info or [])} schema items")

            # Warm up LLM connection
            logger.info(f"🔗 WARMING UP LLM connection for model {model_id}")
            # Test connection with a simple ping (if supported)
            # This ensures the model is ready for requests

            self._initialized = True
            logger.info(f"🎯 ChatEngine initialization completed for bot {bot_id}")

        except Exception as e:
            logger.error(f"Failed to initialize ChatEngine for bot {bot_id}: {e}")
            self._initialized = False
            raise

    def is_initialized(self) -> bool:
        """Check if the engine is pre-initialized"""
        return self._initialized

    async def process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """
        Process a complete chat request through the pipeline.
        """
        try:
            # Generate request ID for tracing
            request_id = create_request_id("chat")
            conversation_id = request.conversation_id or str(uuid.uuid4())

            # Initialize variables
            fast_result = None
            conversation_history = []

            # Use request context for tracing
            with request_context(
                request_id=request_id,
                session_id=conversation_id,
                user_question=request.user_question,
                snapshot_id=request.snapshot_id,
                bot_id=getattr(request, 'bot_id', None)
            ) as ctx:
                # Get conversation history
                if conversation_id:
                    conversation_history = await self.conversation_manager.get_conversation_history(conversation_id)

                # Log request start
                self.logger.info(
                    "Processing chat request",
                    operation="process_request",
                    language=request.language.value,
                    model_id=request.selected_model_id,
                    conversation_length=len(conversation_history)
                )

                # Fast intent detection
                fast_result = await self.fast_intent_detector.detect_and_respond(
                    self.llm_gateway,
                    request.user_question,
                    request.language,
                    request.selected_model_id,
                    conversation_history
                )

            # Handle fast conversational responses
            if fast_result and fast_result.get("is_conversational") and fast_result.get("confidence", 0) >= 0.7:
                response_text = fast_result.get("response")

                if not response_text:
                    response_text = await self.fast_intent_detector._generate_quick_response(
                        self.llm_gateway,
                        request.user_question,
                        request.language,
                        request.selected_model_id,
                        conversation_history
                    )

                if response_text:
                    temp_response = ChatResponse(
                        success=True,
                        user_question=request.user_question,
                        generated_sql="",
                        rows=[],
                        row_count=0,
                        snapshot_id=request.snapshot_id,
                        model_used=f"model_{request.selected_model_id}",
                        execution_status="completed",
                        error_message=None,
                        context_hash="fast_conversational",
                        sql_validation_status="skipped",
                        execution_time_ms=0,
                        conversation_id=conversation_id,
                        conversational_response=response_text
                    )
                    temp_response.formatted_content = self._build_formatted_content(temp_response, request.language)
                    return temp_response

            # Load context (use preloaded if available and matches)
            if self._preloaded_context and self._context_snapshot_id == request.snapshot_id:
                context = self._preloaded_context
                logger.debug(f"Using preloaded context for snapshot {request.snapshot_id}")
            else:
                logger.debug(f"Loading context on-demand for snapshot {request.snapshot_id}")
                context = await self.context_cache.get_context(
                    request.snapshot_id,
                    self.context_loader
                )

            # Use new modular pipeline with centralized logging
            pipeline_context = PipelineContext(
                request_id=request_id,  # Use the same request ID for tracing
                question=request.user_question,
                language=request.language,
                model_id=request.selected_model_id,
                context=context,
                conversation_history=conversation_history,
                max_rows=50  # Default max rows
            )

            # Execute pipeline with timing
            pipeline_result = None
            pipeline_result_context = None

            try:
                with self.logger.start_operation("pipeline_execution") as timer:
                    pipeline_result_context = await self.modular_pipeline.execute_pipeline(pipeline_context)
                    pipeline_result = pipeline_result_context.final_result

                    # Set success status
                    timer.success = pipeline_result_context.success
            except Exception as e:
                # Pipeline execution failed
                self.logger.error(
                    "Pipeline execution failed",
                    operation="pipeline_execution",
                    error=str(e)
                )
                # Create error response
                pipeline_result = None

            # Handle conversational responses from pipeline
            if pipeline_result and pipeline_result.get('intent') == 'CONVERSATIONAL':
                conversational_response = await self._generate_conversational_response_from_llm(
                    request.user_question,
                    request.language,
                    request.selected_model_id,
                    conversation_history
                )

                temp_response = ChatResponse(
                    success=True,
                    user_question=request.user_question,
                    generated_sql="",
                    rows=[],
                    row_count=0,
                    snapshot_id=request.snapshot_id,
                    model_used=pipeline_result.get('model_used', f"model_{request.selected_model_id}"),
                    execution_status="completed",
                    error_message=None,
                    context_hash=getattr(context, 'context_hash', 'unknown'),
                    sql_validation_status="skipped",
                    execution_time_ms=0,
                    conversation_id=conversation_id,
                    conversational_response=conversational_response
                )
                temp_response.formatted_content = self._build_formatted_content(temp_response, request.language)
                return temp_response

            # Return SQL query results with conversational response
            if pipeline_result and pipeline_result_context.success:
                # Generate a conversational response explaining the SQL results
                sql_results_text = await self._generate_sql_results_conversational_response(
                    request.user_question,
                    request.language,
                    request.selected_model_id,
                    pipeline_result,
                    conversation_history
                )

                response = ChatResponse(
                    success=True,
                    user_question=request.user_question,
                    generated_sql=pipeline_result['sql'],
                    rows=pipeline_result['rows'],
                    row_count=pipeline_result['row_count'],
                    snapshot_id=request.snapshot_id,
                    model_used=pipeline_result['model_used'],
                    execution_status=pipeline_result['execution_status'],
                    error_message=pipeline_result.get('error_message'),
                    context_hash=getattr(context, 'context_hash', 'unknown'),
                    sql_validation_status=pipeline_result.get('validation_status', 'unknown'),
                    execution_time_ms=0,
                    conversation_id=conversation_id,
                    conversational_response=sql_results_text
                )
                response.formatted_content = self._build_formatted_content(response, request.language)
            else:
                # Pipeline failed, return error response with conversational explanation
                error_conversational = await self._generate_error_conversational_response(
                    request.user_question,
                    request.language,
                    request.selected_model_id,
                    "Pipeline execution failed",
                    conversation_history
                )

                response = ChatResponse(
                    success=False,
                    user_question=request.user_question,
                    generated_sql="",
                    rows=[],
                    row_count=0,
                    snapshot_id=request.snapshot_id,
                    model_used=f"model_{request.selected_model_id}",
                    execution_status="error",
                    error_message="Pipeline execution failed",
                    context_hash=getattr(context, 'context_hash', 'unknown'),
                    sql_validation_status="failed",
                    execution_time_ms=0,
                    conversation_id=conversation_id,
                    conversational_response=error_conversational
                )
                response.formatted_content = self._build_formatted_content(response, request.language)

            # Log final response
            if pipeline_result:
                self.logger.info(
                    "Chat request completed",
                    operation="request_complete",
                    success=True,
                    sql_length=len(pipeline_result['sql']),
                    rows_returned=pipeline_result['row_count'],
                    execution_status=pipeline_result['execution_status']
                )
            else:
                self.logger.error(
                    "Chat request failed - no pipeline result",
                    operation="request_complete",
                    success=False
                )

            return response
        except Exception as e:
            # Global exception handler for process_chat_request
            self.logger.error(
                "Unexpected error in process_chat_request",
                operation="process_request",
                error=str(e),
                error_type=type(e).__name__
            )

            # Return error response
            temp_response = ChatResponse(
                success=False,
                user_question=request.user_question,
                generated_sql="",
                rows=[],
                row_count=0,
                snapshot_id=getattr(request, 'snapshot_id', 0),
                model_used=f"model_{getattr(request, 'selected_model_id', 1)}",
                execution_status="error",
                error_message=f"Unexpected error: {str(e)}",
                context_hash="",
                sql_validation_status="failed",
                execution_time_ms=0,
                conversation_id=getattr(request, 'conversation_id', '')
            )
            temp_response.formatted_content = self._build_formatted_content(temp_response, getattr(request, 'language', ChatLanguage.ENGLISH))
            return temp_response


    def _create_error_response(
        self,
        request: ChatRequest,
        context: ChatContext,
        model_used: str,
        error_message: str,
        conversation_id: str,
        start_time: float
    ) -> ChatResponse:
        """Create error response with proper structure"""
        total_time = int((time.time() - start_time) * 1000)

        return ChatResponse(
            success=False,
            user_question=request.user_question,
            generated_sql="",
            rows=[],
            row_count=0,
            snapshot_id=request.snapshot_id,
            model_used=model_used,
            execution_status="error",
            error_message=error_message,
            context_hash=context.context_hash,
            sql_validation_status="skipped",
            execution_time_ms=total_time,
            conversation_id=conversation_id
        )

    def _get_smart_reasoning_for_persian(self, question: str, language) -> str:
        """Generate smart reasoning output for Persian queries"""
        # Generic reasoning for Persian queries - let the system discover tables dynamically
        base_reasoning = f"User question: {question}\n\nAnalysis: Persian language query."

        # Add specific focus based on keywords
        if any(keyword in question for keyword in ["قیمت", "price"]):
            base_reasoning += " Focus: Price-related query - look for tables with price columns."
        elif any(keyword in question for keyword in ["تعداد", "count", "شمارش"]):
            base_reasoning += " Focus: Counting query - look for aggregation opportunities."
        elif any(keyword in question for keyword in ["نمایش", "لیست", "show", "list"]):
            base_reasoning += " Focus: Listing/display query - find relevant data tables."
        elif any(keyword in question for keyword in ["میانگین", "average", "مجموع", "sum"]):
            base_reasoning += " Focus: Aggregation query - statistical analysis needed."
        else:
            base_reasoning += " Focus: General data inquiry."

        base_reasoning += f"\n\nIntent: DETAIL\n\nRequirements: Analyze the database schema dynamically and select appropriate tables and columns based on the query content and available schema information."

        return base_reasoning

    async def _get_model_name(self, model_id: int) -> str:
        """Get model name by ID for error responses"""
        from sqlalchemy import select
        from api.db_models import LLMModel

        result = await self.session.execute(
            select(LLMModel.name).where(LLMModel.id == model_id)
        )
        model = result.scalar_one_or_none()
        return model if model else f"model_{model_id}"

    def get_engine_metadata(self) -> dict:
        """Get metadata about the engine and its components"""
        return {
            "prompt_versions": self.prompt_engine.get_prompt_metadata(),
            "active_conversations": self.conversation_manager.get_active_conversations_count(),
            "components": [
                "ContextLoader",
                "PromptEngine",
                "LLMGateway",
                "SQLPipeline",
                "ConversationStateManager"
            ]
        }

    async def cleanup_expired_conversations(self):
        """Clean up expired conversation states"""
        self.conversation_manager.cleanup_expired_states()

    async def reset_initialization(self):
        """Reset pre-initialization state"""
        self._preloaded_context = None
        self._context_snapshot_id = None
        self._initialized = False
        logger.info("🔄 ChatEngine initialization reset")

    async def _generate_conversational_response_from_llm(
        self,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Generate conversational response from LLM model.
        
        Args:
            question: User's conversational question
            language: Language for the response
            model_id: LLM model ID to use
            conversation_history: Previous conversation messages
            
        Returns:
            Response text from LLM
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Build conversational prompt
            if language == ChatLanguage.PERSIAN:
                system_prompt = """شما یک دستیار هوشمند و دوستانه هستید که به کاربران در زمینه تحلیل داده کمک می‌کنید. 
به سوالات عمومی، احوال‌پرسی، تشکر و درخواست کمک پاسخ دهید. پاسخ‌های خود را به فارسی و به صورت دوستانه و مفید بنویسید.

اگر کاربر سوال داده‌ای پرسید، او را راهنمایی کنید که چگونه می‌تواند سوالات خود را در مورد داده‌ها بپرسد."""
                
                user_prompt = f"""کاربر: {question}

لطفاً یک پاسخ دوستانه و مفید به فارسی بنویسید."""
            else:
                system_prompt = """You are a friendly and intelligent assistant that helps users with data analysis.
Respond to general questions, greetings, thanks, and help requests. Write your responses in a friendly and helpful manner.

If the user asks a data-related question, guide them on how they can ask questions about their data."""
                
                user_prompt = f"""User: {question}

Please write a friendly and helpful response."""
            
            # Build full prompt with conversation history if available
            full_prompt = system_prompt + "\n\n"
            
            # Add conversation history (last 3 messages for context)
            if conversation_history:
                recent_history = conversation_history[-3:]  # Last 3 messages
                for msg in recent_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if role == 'user':
                        full_prompt += f"User: {content}\n"
                    elif role == 'assistant':
                        full_prompt += f"Assistant: {content}\n"
                full_prompt += "\n"
            
            full_prompt += user_prompt
            
            logger.info(f"Calling conversational LLM | Model: {model_id} | Language: {language}")
            
            # Call LLM
            llm_response = await self.llm_gateway.call_llm(
                model_id=model_id,
                prompt=full_prompt,
                temperature=0.7  # Higher temperature for more natural conversational responses
            )
            
            if not llm_response.success:
                logger.error(f"Conversational LLM call failed | Model: {model_id} | Error: {llm_response.error_message}")
                # Fallback to simple response - let model handle all responses
                return self._get_simple_fallback_response(language)
            
            response_text = llm_response.raw_text.strip()
            logger.info(f"Conversational LLM call succeeded | Model: {model_id} | Response length: {len(response_text)}")
            
            return response_text
            
        except Exception as e:
            logger.error(f"Conversational LLM error | Error: {str(e)}", exc_info=True)
            # Fallback to simple response - let model handle all responses
            return self._get_simple_fallback_response(language)

    async def _generate_sql_results_conversational_response(
        self,
        question: str,
        language: ChatLanguage,
        model_id: int,
        pipeline_result: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Generate conversational response for SQL query results.

        Args:
            question: User's original question
            language: Response language
            model_id: LLM model ID
            pipeline_result: Pipeline execution results
            conversation_history: Previous conversation

        Returns:
            Conversational explanation of SQL results
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            row_count = pipeline_result.get('row_count', 0)
            execution_status = pipeline_result.get('execution_status', 'unknown')
            sql = pipeline_result.get('generated_sql', '')

            # Build prompt for conversational response
            if language == ChatLanguage.PERSIAN:
                system_prompt = """شما یک دستیار مفید هستید که نتایج کوئری SQL را به زبان طبیعی توضیح می‌دهید.
پاسخ خود را به فارسی و به صورت دوستانه و مفید بنویسید. نتایج را خلاصه کنید و نکات کلیدی را برجسته کنید."""
                user_prompt = f"""سوال کاربر: {question}

کوئری SQL تولید شده: {sql}
وضعیت اجرا: {execution_status}
تعداد ردیف‌های بازگشتی: {row_count}

لطفاً یک پاسخ کوتاه و مفید به فارسی بنویسید که نتایج را توضیح دهد."""
            else:
                system_prompt = """You are a helpful assistant that explains SQL query results in natural language.
Write your response in a friendly and helpful manner. Summarize the results and highlight key points."""
                user_prompt = f"""User question: {question}

Generated SQL query: {sql}
Execution status: {execution_status}
Number of rows returned: {row_count}

Please write a brief and helpful response that explains the results."""

            # Add conversation history context
            full_prompt = system_prompt + "\n\n"
            if conversation_history:
                recent_history = conversation_history[-2:]  # Last 2 messages for context
                for msg in recent_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if role == 'user':
                        full_prompt += f"User: {content}\n"
                    elif role == 'assistant':
                        full_prompt += f"Assistant: {content}\n"
                full_prompt += "\n"

            full_prompt += user_prompt

            logger.info(f"Generating SQL results conversational response | Model: {model_id} | Rows: {row_count}")

            # Call LLM for conversational response
            llm_response = await self.llm_gateway.call_llm(
                model_id=model_id,
                prompt=full_prompt,
                temperature=0.3  # Lower temperature for more consistent explanations
            )

            if llm_response.success:
                response_text = llm_response.raw_text.strip()
                logger.info(f"SQL results response generated | Length: {len(response_text)}")
                return response_text
            else:
                logger.warning(f"LLM failed to generate SQL results response | Error: {llm_response.error_message}")
                return self._get_simple_sql_fallback_response(language, row_count, execution_status)

        except Exception as e:
            logger.error(f"Error generating SQL results conversational response | Error: {str(e)}", exc_info=True)
            return self._get_simple_sql_fallback_response(language, pipeline_result.get('row_count', 0), pipeline_result.get('execution_status', 'unknown'))

    def _get_simple_sql_fallback_response(self, language: ChatLanguage, row_count: int, execution_status: str) -> str:
        """Get simple fallback response for SQL results when LLM fails"""
        if language == ChatLanguage.PERSIAN:
            if execution_status == 'success':
                return f"کوئری با موفقیت اجرا شد و {row_count} ردیف نتیجه یافت شد."
            else:
                return f"متاسفانه اجرای کوئری با مشکل مواجه شد."
        else:
            if execution_status == 'success':
                return f"Query executed successfully, found {row_count} results."
            else:
                return f"Sorry, there was an issue executing the query."

    async def _generate_error_conversational_response(
        self,
        question: str,
        language: ChatLanguage,
        model_id: int,
        error_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Generate conversational response for errors.

        Args:
            question: User's original question
            language: Response language
            model_id: LLM model ID
            error_message: Error details
            conversation_history: Previous conversation

        Returns:
            Conversational explanation of the error
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            if language == ChatLanguage.PERSIAN:
                system_prompt = """شما یک دستیار مفید هستید که خطاها را به زبان طبیعی و دوستانه توضیح می‌دهید.
پاسخ خود را به فارسی بنویسید و راهنمایی کنید که کاربر چگونه می‌تواند سوال خود را دوباره بپرسد."""
                user_prompt = f"""سوال کاربر: {question}

خطا رخ داده: {error_message}

لطفاً یک پاسخ کوتاه و مفید به فارسی بنویسید که خطا را توضیح دهد و راهنمایی کند."""
            else:
                system_prompt = """You are a helpful assistant that explains errors in natural language.
Write your response in a friendly manner and guide the user on how to rephrase their question."""
                user_prompt = f"""User question: {question}

Error occurred: {error_message}

Please write a brief and helpful response that explains the error and provides guidance."""

            full_prompt = system_prompt + "\n\n" + user_prompt

            logger.info(f"Generating error conversational response | Model: {model_id}")

            # Call LLM for error explanation
            llm_response = await self.llm_gateway.call_llm(
                model_id=model_id,
                prompt=full_prompt,
                temperature=0.3
            )

            if llm_response.success:
                response_text = llm_response.raw_text.strip()
                logger.info(f"Error response generated | Length: {len(response_text)}")
                return response_text
            else:
                logger.warning(f"LLM failed to generate error response | Error: {llm_response.error_message}")
                return self._get_simple_error_fallback_response(language)

        except Exception as e:
            logger.error(f"Error generating error conversational response | Error: {str(e)}", exc_info=True)
            return self._get_simple_error_fallback_response(language)

    def _get_simple_error_fallback_response(self, language: ChatLanguage) -> str:
        """Get simple fallback response for errors when LLM fails"""
        if language == ChatLanguage.PERSIAN:
            return "متاسفانه در پردازش سوال شما مشکلی پیش آمد. لطفاً سوال خود را به صورت دیگری بیان کنید."
        else:
            return "Sorry, there was an issue processing your question. Please try rephrasing it."

    def _get_simple_fallback_response(self, language: ChatLanguage) -> str:
        """Get simple fallback response when LLM fails - all responses should be generated by model"""
        if language == ChatLanguage.PERSIAN:
            return "سلام! من دستیار SQL شما هستم و می‌توانم به سوالات شما در مورد داده‌ها پاسخ دهم. چه سوالی دارید؟"
        else:
            return "Hello! I'm your SQL Assistant and can help with data questions. What would you like to know?"

    def _build_formatted_content(self, response: ChatResponse, language: ChatLanguage) -> str:
        """
        Build formatted content for display with proper text direction.
        This ensures consistent formatting between API response and database storage.
        """
        content_parts = []

        # Add conversational response if available
        if response.conversational_response:
            if language.value == "fa":  # Persian
                content_parts.append(f"""<div dir="rtl" style="text-align: right;">
{response.conversational_response}
</div>""")
            else:  # English and other languages
                content_parts.append(response.conversational_response)

        # Add SQL query with proper direction
        if response.generated_sql:
            if language.value == "fa":  # Persian
                content_parts.append(f"""Generated SQL:
<div dir="ltr" style="text-align: left;">
<pre style="background-color: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 0.375rem; overflow-x: auto; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 0.875rem; line-height: 1.25rem;"><code style="color: #9cdcfe;">{response.generated_sql.replace('<', '&lt;').replace('>', '&gt;')}</code></pre>
</div>""")
            else:  # English and other languages
                content_parts.append(f"Generated SQL:\n```sql\n{response.generated_sql}\n```")

        # Add table data with proper direction if available
        if response.rows and len(response.rows) > 0:
            try:
                if language.value == "fa":  # Persian
                    # Create an HTML table with LTR direction
                    headers = list(response.rows[0].keys())
                    table_html = "<div dir='ltr' style='text-align: left;'>\n"
                    table_html += "<div style='margin: 1rem 0; font-weight: 600; color: #374151;'>Query Results:</div>\n"
                    table_html += "<div style='overflow-x: auto; overflow-y: auto; max-height: 500px; border: 1px solid #d1d5db; border-radius: 0.375rem; position: relative;'>\n"
                    table_html += "<table style='min-width: 100%; border-collapse: collapse; table-layout: auto;'>\n"
                    table_html += "<thead style='background-color: #f9fafb; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.1);'>\n"
                    table_html += "<tr>\n"
                    for header in headers:
                        table_html += f"<th style='padding: 0.5rem 0.75rem; text-align: left; font-weight: 600; color: #374151; border-bottom: 1px solid #d1d5db; white-space: nowrap;'>{header}</th>\n"
                    table_html += "</tr>\n"
                    table_html += "</thead>\n"
                    table_html += "<tbody>\n"
                    for row in response.rows[:50]:  # Limit to first 50 rows for display
                        table_html += "<tr style='border-bottom: 1px solid #e5e7eb;'>\n"
                        for header in headers:
                            value = str(row.get(header, ""))
                            table_html += f"<td style='padding: 0.5rem 0.75rem; color: #111827; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis;'>{value}</td>\n"
                        table_html += "</tr>\n"
                    table_html += "</tbody>\n"
                    table_html += "</table>\n"
                    if len(response.rows) > 50:
                        table_html += f"<div style='padding: 0.5rem; text-align: center; color: #6b7280; font-style: italic;'>... and {len(response.rows) - 50} more rows</div>\n"
                    table_html += "</div>\n"
                    table_html += "</div>"
                    content_parts.append(table_html)
                else:  # English and other languages
                    # Simple markdown table
                    headers = list(response.rows[0].keys())
                    table_md = "| " + " | ".join(headers) + " |\n"
                    table_md += "|" + "|".join(["---"] * len(headers)) + "|\n"
                    for row in response.rows[:10]:  # Limit to first 10 rows
                        values = [str(row.get(h, "")) for h in headers]  # Use headers to maintain column order
                        table_md += "| " + " | ".join(values) + " |\n"
                    if len(response.rows) > 10:
                        table_md += f"\n... and {len(response.rows) - 10} more rows\n"
                    content_parts.append(f"Query Results:\n{table_md}")
            except Exception as e:
                # Fallback if table formatting fails
                logger.warning(f"Failed to format table data: {e}")
                content_parts.append(f"Query Results: {len(response.rows)} rows returned")

        # Combine all parts or use fallback
        if content_parts:
            return "\n\n".join(content_parts)
        else:
            return "No response generated"

    async def close(self):
        """Clean up resources"""
        await self.llm_gateway.close()
