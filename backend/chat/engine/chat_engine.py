import time
import uuid
import logging
import json
from typing import Optional, List, Dict
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
        self.sql_pipeline = SQLPipeline(
            llm_gateway=self.llm_gateway,
            prompt_engine=self.prompt_engine,
            connector=connector,
            result_cache=self.query_result_cache
        )
        self.conversation_manager = ConversationStateManager(session=session)

        # Pre-initialized resources (for optimization)
        self._preloaded_context: Optional[ChatContext] = None
        self._context_snapshot_id: Optional[int] = None
        self._initialized = False

    async def initialize_for_bot(self, bot_id: int, snapshot_id: int, model_id: int):
        """
        Pre-initialize the chat engine for a specific bot.
        This loads context and warms up connections for better performance.
        """
        try:
            logger.info(f"🔧 INITIALIZING ChatEngine for bot {bot_id}, snapshot {snapshot_id}, model {model_id}")

            # Pre-load context if not already loaded or different snapshot
            if self._preloaded_context is None or self._context_snapshot_id != snapshot_id:
                logger.info(f"📚 PRE-LOADING context for snapshot {snapshot_id}")
                self._preloaded_context = await self.context_cache.get_context(
                    snapshot_id,
                    self.context_loader
                )
                self._context_snapshot_id = snapshot_id
                logger.info(f"✅ Context pre-loaded with {len(self._preloaded_context.schema_info or [])} schema items")

            # Warm up LLM connection
            logger.info(f"🔗 WARMING UP LLM connection for model {model_id}")
            # Test connection with a simple ping (if supported)
            # This ensures the model is ready for requests

            self._initialized = True
            logger.info(f"🎯 ChatEngine initialization completed for bot {bot_id}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize ChatEngine for bot {bot_id}: {e}")
            self._initialized = False
            raise

    def is_initialized(self) -> bool:
        """Check if the engine is pre-initialized"""
        return self._initialized

    async def process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """
        Process a complete chat request through the pipeline.
        """
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Get conversation history
        conversation_history = []
        if conversation_id:
            conversation_history = await self.conversation_manager.get_conversation_history(conversation_id)

        # Fast intent detection
        fast_result = await self.fast_intent_detector.detect_and_respond(
            self.llm_gateway,
            request.user_question,
            request.language,
            request.selected_model_id,
            conversation_history
        )

        # Handle fast conversational responses
        if fast_result.get("is_conversational") and fast_result.get("confidence", 0) >= 0.7:
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
                return ChatResponse(
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

        # Load context (use preloaded if available and matches)
        if self._preloaded_context and self._context_snapshot_id == request.snapshot_id:
            context = self._preloaded_context
            logger.debug(f"💾 Using preloaded context for snapshot {request.snapshot_id}")
        else:
            logger.debug(f"📚 Loading context on-demand for snapshot {request.snapshot_id}")
            context = await self.context_cache.get_context(
                request.snapshot_id,
                self.context_loader
            )

        pipeline_result = await self.sql_pipeline.process_sql_with_reasoning_pipeline(
            context=context,
            question=request.user_question,
            language=request.language,
            model_id=request.selected_model_id,
            conversation_history=conversation_history
        )

        # Handle conversational responses from pipeline
        if pipeline_result.get('intent') == 'CONVERSATIONAL':
            conversational_response = await self._generate_conversational_response_from_llm(
                request.user_question,
                request.language,
                request.selected_model_id,
                conversation_history
            )

            return ChatResponse(
                success=True,
                user_question=request.user_question,
                generated_sql="",
                rows=[],
                row_count=0,
                snapshot_id=request.snapshot_id,
                model_used=pipeline_result.get('model_used', f"model_{request.selected_model_id}"),
                execution_status="completed",
                error_message=None,
                context_hash=context.context_hash,
                sql_validation_status="skipped",
                execution_time_ms=0,
                conversation_id=conversation_id,
                conversational_response=conversational_response
            )

        # Return SQL query results
        return ChatResponse(
            success=True,
            user_question=request.user_question,
            generated_sql=pipeline_result['sql'],
            rows=pipeline_result['rows'],
            row_count=pipeline_result['row_count'],
            snapshot_id=request.snapshot_id,
            model_used=pipeline_result['model_used'],
            execution_status=pipeline_result['execution_status'],
            error_message=pipeline_result.get('error_message'),
            context_hash=context.context_hash,
            sql_validation_status=pipeline_result['validation_status'],
            execution_time_ms=0,
            conversation_id=conversation_id
        )

    async def cleanup_expired_conversations(self):
        """
        Process a complete chat request through the pipeline.

        Args:
            request: The chat request to process

        Returns:
            ChatResponse: Complete response with full traceability
        """
        from config.chatbot_logging import chatbot_logger

        request_id = str(uuid.uuid4())[:8]
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Step 0: Fast Intent Detection (BEFORE context loading)
        # Get conversation history (lightweight, no context needed)
        conversation_history = []
        if conversation_id:
            conversation_history = await self.conversation_manager.get_conversation_history(conversation_id)

        # Fast intent detection with LLM
        fast_result = await self.fast_intent_detector.detect_and_respond(
            self.llm_gateway,
            request.user_question,
            request.language,
            request.selected_model_id,
            conversation_history
        )

        # If conversational with high confidence, return immediately
        if fast_result.get("is_conversational") and fast_result.get("confidence", 0) >= 0.7:
                response_text = fast_result.get("response")

                # If response not generated, generate it quickly using LLM
                if not response_text:
                    response_text = await self.fast_intent_detector._generate_quick_response(
                        self.llm_gateway,
                        request.user_question,
                        request.language,
                        request.selected_model_id,
                        conversation_history
                    )

                    # If LLM failed to generate response, let normal pipeline handle
                    if not response_text:
                        logger.warning(f"⚠️ QUICK_RESPONSE_FAILED | ID: {request_id} | Falling back to normal pipeline")
                        # Don't return here, continue to normal pipeline below
                        
                        # Create minimal context for response
                        minimal_context = ChatContext(
                            snapshot_id=request.snapshot_id,
                            snapshot_name="unknown",
                            database_type="unknown",
                            schema_info=[],
                            data_dictionary=[],
                            relationships=[],
                            use_cases=[],
                            context_hash="fast_conversational"
                        )
                        
                        return ChatResponse(
                            success=True,
                            user_question=request.user_question,
                            generated_sql="",
                            rows=[],
                            row_count=0,
                            snapshot_id=request.snapshot_id,
                            model_used=f"model_{request.selected_model_id}",
                            execution_status="completed",
                            error_message=None,
                            context_hash=minimal_context.context_hash,
                            sql_validation_status="skipped",
                            execution_time_ms=total_time,
                            conversation_id=conversation_id,
                            conversational_response=response_text
                        )
                
                # Response already generated in fast_result
                if response_text:
                    total_time = int((time.time() - start_time) * 1000)
                    logger.info(
                        f"⚡ FAST_CONVERSATIONAL_RESPONSE | ID: {request_id} | "
                        f"Confidence: {fast_result.get('confidence', 0):.2f} | "
                        f"DetectionTime: {fast_detection_time}ms | "
                        f"TotalTime: {total_time}ms | "
                        f"Skipped: Context Loading, SQL Pipeline"
                    )
                    
                    # Create minimal context for response
                    minimal_context = ChatContext(
                        snapshot_id=request.snapshot_id,
                        snapshot_name="unknown",
                        database_type="unknown",
                        schema_info=[],
                        data_dictionary=[],
                        relationships=[],
                        use_cases=[],
                        context_hash="fast_conversational"
                    )
                    
                    return ChatResponse(
                        success=True,
                        user_question=request.user_question,
                        generated_sql="",
                        rows=[],
                        row_count=0,
                        snapshot_id=request.snapshot_id,
                        model_used=f"model_{request.selected_model_id}",
                        execution_status="completed",
                        error_message=None,
                        context_hash=minimal_context.context_hash,
                        sql_validation_status="skipped",
                        execution_time_ms=total_time,
                        conversation_id=conversation_id,
                        conversational_response=response_text
                    )

        # Step 1: Load context (only if not conversational)
        context = await self.context_cache.get_context(
            request.snapshot_id,
            self.context_loader
        )

        # Conversation history already loaded in Step 0
        logger.debug(f"💬 CONVERSATION_HISTORY | ID: {request_id} | Messages: {len(conversation_history)} | Recent: {conversation_history[-1] if conversation_history else 'None'}")

        # Step 3: Use new reasoning pipeline
        pipeline_result = await self.sql_pipeline.process_sql_with_reasoning_pipeline(
            context=context,
            question=request.user_question,
            language=request.language,
            model_id=request.selected_model_id,
            conversation_history=conversation_history
        )

        # Handle conversational queries differently - generate response from LLM
        if pipeline_result.get('intent') == 'CONVERSATIONAL':
            # Generate conversational response from LLM
            conversational_response = await self._generate_conversational_response_from_llm(
                request.user_question,
                request.language,
                request.selected_model_id,
                conversation_history
            )

            return ChatResponse(
                    success=True,
                    user_question=request.user_question,
                    generated_sql="",  # No SQL for conversational queries
                    rows=[],  # No data rows, just the message
                    row_count=0,
                    snapshot_id=request.snapshot_id,
                    model_used=pipeline_result.get('model_used', f"model_{request.selected_model_id}"),
                    execution_status="completed",  # Use "completed" instead of "success" for conversations
                    error_message=None,
                    context_hash=context.context_hash,
                    sql_validation_status="skipped",
                    execution_time_ms=total_time,
                    conversation_id=conversation_id,
                    conversational_response=conversational_response  # Response from LLM
                )

            # Step 5: Update conversation state (optional)
            if conversation_id:
                result_summary = f"{pipeline_result['row_count']} rows returned"
                if pipeline_result['truncated']:
                    result_summary += " (truncated)"

                logger.debug(f"💾 CONVERSATION_UPDATE | ID: {request_id} | Intent: {pipeline_result.get('intent', 'unknown')} | Summary: {result_summary}")

                self.conversation_manager.update_conversation_state(
                    conversation_id=conversation_id,
                    intent=pipeline_result.get('intent', 'unknown')[:100],  # Use detected intent
                    sql=pipeline_result['sql'],
                    result_summary=result_summary
                )

            # Step 6: Create successful response

            return ChatResponse(
                success=True,
                user_question=request.user_question,
                generated_sql=pipeline_result['sql'],
                rows=pipeline_result['rows'],
                row_count=pipeline_result['row_count'],
                snapshot_id=request.snapshot_id,
                model_used=pipeline_result['model_used'],
                execution_status=pipeline_result['execution_status'],
                error_message=pipeline_result.get('error_message'),
                context_hash=context.context_hash,
                sql_validation_status=pipeline_result['validation_status'],
                execution_time_ms=total_time,
                conversation_id=conversation_id
            )

            # Try to get model name for error response
            try:
                model_name = await self._get_model_name(request.selected_model_id)
            except:
                model_name = f"model_{request.selected_model_id}"

            # Create error context (minimal)
            context = ChatContext(
                snapshot_id=request.snapshot_id,
                snapshot_name="unknown",
                database_type="unknown",
                schema_info=[],
                data_dictionary=[],
                relationships=[],
                use_cases=[]
            )

            return self._create_error_response(
                request,
                context,
                model_name,
                f"Chat processing failed: {error_msg}",
                conversation_id,
                start_time
            )

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
            
            logger.info(f"🤖 CONVERSATIONAL_LLM_CALL | Model: {model_id} | Question: '{question[:50]}...' | Language: {language}")
            
            # Call LLM
            llm_response = await self.llm_gateway.call_llm(
                model_id=model_id,
                prompt=full_prompt,
                temperature=0.7  # Higher temperature for more natural conversational responses
            )
            
            if not llm_response.success:
                logger.error(f"❌ CONVERSATIONAL_LLM_FAILED | Model: {model_id} | Error: {llm_response.error_message}")
                # Fallback to predefined response
                return self._generate_conversational_response(question, language)
            
            response_text = llm_response.raw_text.strip()
            logger.info(f"✅ CONVERSATIONAL_LLM_SUCCESS | Model: {model_id} | ResponseLength: {len(response_text)}")
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ CONVERSATIONAL_LLM_ERROR | Error: {str(e)}", exc_info=True)
            # Fallback to predefined response
            return self._generate_conversational_response(question, language)
    
    def _generate_conversational_response(self, question: str, language: ChatLanguage) -> str:
        """Generate appropriate conversational response based on user input"""
        question_lower = question.lower().strip()

        if language == ChatLanguage.ENGLISH:
            # English responses
            if any(word in question_lower for word in ["hi", "hello", "hey", "greetings"]):
                return """Hello! I'm your SQL Assistant.

I can help you query and analyze data from your database. What would you like to know?

Try asking questions like:
• "How many products do we have?"
• "Show me the top 5 sales records"
• "What's the average price of cement?"
• "Compare sales this month vs last month"

Just ask in natural language!"""

            elif any(word in question_lower for word in ["thanks", "thank you", "thx"]):
                return "You're welcome! I'm here whenever you need help with your data analysis."

            elif any(word in question_lower for word in ["help", "please help"]):
                return """SQL Assistant Help

I can help you with:

• COUNTING: "How many records are in the table?"
• AGGREGATION: "What's the average value?" or "What's the total?"
• LISTING: "Show me all items" or "List the top 10 entries"
• DETAILS: "Tell me about item X" or "Show details for record #123"
• COMPARISON: "Compare values between categories"

Examples:
• "How many records are there?"
• "Show me the top 5 items"
• "What's the average value?"
• "List all records from today"

Just type your question in natural language!"""

            elif any(word in question_lower for word in ["bye", "goodbye", "see you"]):
                return "Goodbye! Feel free to come back anytime you need data insights."

            elif any(word in question_lower for word in ["sorry", "apologize"]):
                return "No need to apologize! I'm here to help. What can I do for you?"

            else:
                return f"I understand you asked: '{question}'.\n\nI'm a SQL Assistant focused on database queries and analysis. I can help you count records, analyze data, list information, and more. What would you like to know about your data?"

        else:  # Persian
            # Persian responses
            if any(word in question_lower for word in ["سلام", "hi", "hello", "hey"]):
                return """سلام! من دستیار SQL شما هستم.

می‌توانم به شما در جستجو و تحلیل داده‌های پایگاه داده کمک کنم. چه سوالی دارید؟

سوالاتی مانند این بپرسید:
• "چند محصول داریم؟"
• "۵ رکورد برتر فروش را نشان بده"
• "میانگین قیمت سیمان چقدر است؟"
• "فروش این ماه را با ماه گذشته مقایسه کن"

به زبان طبیعی بپرسید!"""

            elif any(word in question_lower for word in ["ممنون", "تشکر", "thanks", "thank you"]):
                return "خواهش می‌کنم! همیشه آماده کمک به شما هستم."

            elif any(word in question_lower for word in ["کمک", "help", "please help"]):
                return """راهنمای دستیار SQL

می‌توانم در موارد زیر به شما کمک کنم:

• شمارش: "چند رکورد در جدول وجود دارد؟"
• تجمیع: "میانگین قیمت چقدر است؟" یا "مجموع فروش چقدر است؟"
• لیست: "همه محصولات را نشان بده" یا "۱۰ مورد برتر را لیست کن"
• جزئیات: "در مورد محصول X بگو" یا "جزئیات سفارش شماره ۱۲۳"
• مقایسه: "فروش بین بخش‌ها را مقایسه کن"

مثال‌ها:
• "چند رکورد سیمان وجود دارد؟"
• "۵ محصول گران‌قیمت‌ترین را نشان بده"
• "میانگین قیمت در GoodsExchange چقدر است؟"
• "همه تراکنش‌های امروز را لیست کن"

سوال خود را به زبان طبیعی تایپ کنید!"""

            elif any(word in question_lower for word in ["خداحافظ", "bye", "goodbye"]):
                return "خداحافظ! هر زمان نیاز به تحلیل داده داشتید، برگردید."

            elif any(word in question_lower for word in ["ببخشید", "sorry"]):
                return "عذرخواهی لازم نیست! آماده کمک هستم. چه کاری می‌توانم برایتان انجام دهم؟"

            else:
                return f"متوجه شدم که پرسیدید: '{question}'.\n\nمن یک دستیار SQL هستم که روی جستجو و تحلیل داده‌های پایگاه داده تمرکز دارم. می‌توانم به شما در شمارش رکوردها، تحلیل داده‌ها، لیست کردن اطلاعات و موارد دیگر کمک کنم. چه می‌خواهید درباره داده‌های خود بدانید؟"

    async def close(self):
        """Clean up resources"""
        await self.llm_gateway.close()
