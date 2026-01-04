"""
Enhanced Chatbot Logging Module

Provides comprehensive logging for chatbot operations with full process tracking,
performance metrics, and detailed error reporting.
"""

import time
import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ChatRequestContext:
    """Context information for a chat request"""
    request_id: str
    conversation_id: str
    user_question: str
    snapshot_id: int
    model_id: int
    language: str
    bot_id: Optional[int] = None
    bot_name: Optional[str] = None
    start_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessMetrics:
    """Performance metrics for different process steps"""
    step_name: str
    duration_ms: int
    start_time: float
    end_time: float
    success: bool
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ChatbotLogger:
    """
    Comprehensive chatbot logging with full process tracking
    """

    def __init__(self):
        self.chat_logger = get_logger('chatbot.process')
        self.performance_logger = get_logger('chatbot.performance')
        self.error_logger = get_logger('chatbot.errors')
        self.llm_logger = get_logger('chatbot.llm')

    @contextmanager
    def request_context(self, context: ChatRequestContext):
        """Context manager for chat request lifecycle logging"""
        context.start_time = time.time()

        self._log_request_start(context)

        try:
            yield context
            self._log_request_success(context)
        except Exception as e:
            self._log_request_error(context, e)
            raise
        finally:
            total_duration = int((time.time() - context.start_time) * 1000)
            self._log_request_complete(context, total_duration)

    def _log_request_start(self, context: ChatRequestContext):
        """Log the start of a chat request"""
        self.chat_logger.info(
            f"🚀 CHAT_REQUEST_START | ID: {context.request_id} | "
            f"Bot: {context.bot_name or 'Unknown'} | "
            f"Question: '{context.user_question[:100]}{'...' if len(context.user_question) > 100 else ''}' | "
            f"Language: {context.language} | Model: {context.model_id} | Snapshot: {context.snapshot_id}"
        )

    def _log_request_success(self, context: ChatRequestContext):
        """Log successful completion of chat request"""
        self.chat_logger.info(
            f"✅ CHAT_REQUEST_SUCCESS | ID: {context.request_id} | "
            f"Conversation: {context.conversation_id}"
        )

    def _log_request_error(self, context: ChatRequestContext, error: Exception):
        """Log error in chat request"""
        self.error_logger.error(
            f"❌ CHAT_REQUEST_ERROR | ID: {context.request_id} | "
            f"Error: {str(error)} | Type: {type(error).__name__}",
            exc_info=True
        )

    def _log_request_complete(self, context: ChatRequestContext, total_duration: int):
        """Log completion of chat request with total duration"""
        self.performance_logger.info(
            f"🏁 CHAT_REQUEST_COMPLETE | ID: {context.request_id} | "
            f"TotalDuration: {total_duration}ms"
        )

    @contextmanager
    def step_context(self, step_name: str, request_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for individual process steps"""
        start_time = time.time()

        self._log_step_start(step_name, request_id, metadata)

        try:
            yield
            duration = int((time.time() - start_time) * 1000)
            self._log_step_success(step_name, request_id, duration, metadata)
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            self._log_step_error(step_name, request_id, duration, e, metadata)
            raise

    def _log_step_start(self, step_name: str, request_id: str, metadata: Optional[Dict[str, Any]]):
        """Log the start of a processing step"""
        metadata_str = f" | {json.dumps(metadata)}" if metadata else ""
        self.chat_logger.debug(
            f"▶️  STEP_START | ID: {request_id} | Step: {step_name}{metadata_str}"
        )

    def _log_step_success(self, step_name: str, request_id: str, duration: int, metadata: Optional[Dict[str, Any]]):
        """Log successful completion of a processing step"""
        metadata_str = f" | {json.dumps(metadata)}" if metadata else ""
        self.performance_logger.info(
            f"✅ STEP_SUCCESS | ID: {request_id} | Step: {step_name} | Duration: {duration}ms{metadata_str}"
        )

    def _log_step_error(self, step_name: str, request_id: str, duration: int, error: Exception, metadata: Optional[Dict[str, Any]]):
        """Log error in a processing step"""
        metadata_str = f" | {json.dumps(metadata)}" if metadata else ""
        self.error_logger.error(
            f"❌ STEP_ERROR | ID: {request_id} | Step: {step_name} | Duration: {duration}ms | "
            f"Error: {str(error)}{metadata_str}",
            exc_info=True
        )

    def log_intent_detection(self, request_id: str, question: str, intent: str, confidence: float, duration: int):
        """Log intent detection results"""
        self.chat_logger.info(
            f"🎯 INTENT_DETECTED | ID: {request_id} | Intent: {intent} | "
            f"Confidence: {confidence:.2f} | Duration: {duration}ms | "
            f"Question: '{question[:50]}{'...' if len(question) > 50 else ''}'"
        )

    def log_context_loading(self, request_id: str, snapshot_id: int, table_count: int,
                           schema_items: int, relationships: int, duration: int, context_hash: str):
        """Log context loading results"""
        self.chat_logger.info(
            f"📚 CONTEXT_LOADED | ID: {request_id} | Snapshot: {snapshot_id} | "
            f"Tables: {table_count} | SchemaItems: {schema_items} | "
            f"Relationships: {relationships} | Duration: {duration}ms | "
            f"Hash: {context_hash[:16]}..."
        )

    def log_llm_call(self, request_id: str, model_id: int, model_name: str, prompt_tokens: int,
                    completion_tokens: int, total_tokens: int, duration: int, success: bool,
                    prompt: Optional[str] = None, response: Optional[str] = None):
        """Log LLM API call details"""
        status = "✅" if success else "❌"

        self.llm_logger.info(
            f"{status} LLM_CALL | ID: {request_id} | Model: {model_name} ({model_id}) | "
            f"Duration: {duration}ms | PromptTokens: {prompt_tokens} | "
            f"CompletionTokens: {completion_tokens} | TotalTokens: {total_tokens}"
        )

        if prompt:
            self.llm_logger.debug(f"📤 PROMPT | ID: {request_id} | {prompt[:200]}{'...' if len(prompt) > 200 else ''}")
        if response:
            self.llm_logger.debug(f"📥 RESPONSE | ID: {request_id} | {response[:200]}{'...' if len(response) > 200 else ''}")

    def log_sql_generation(self, request_id: str, sql: str, validation_status: str, duration: int):
        """Log SQL generation results"""
        sql_length = len(sql)
        sql_preview = sql[:100] + "..." if sql_length > 100 else sql

        status_emoji = "✅" if validation_status == "valid" else "⚠️" if validation_status == "warning" else "❌"

        self.chat_logger.info(
            f"{status_emoji} SQL_GENERATED | ID: {request_id} | Length: {sql_length} | "
            f"Validation: {validation_status} | Duration: {duration}ms | "
            f"SQL: {sql_preview}"
        )

        if validation_status != "valid":
            self.chat_logger.warning(
                f"⚠️ SQL_VALIDATION_ISSUE | ID: {request_id} | Status: {validation_status} | SQL: {sql}"
            )

    def log_sql_execution(self, request_id: str, sql: str, execution_status: str,
                         row_count: int, duration: int, error: Optional[str] = None):
        """Log SQL execution results"""
        status_emoji = "✅" if execution_status == "completed" else "❌"

        self.chat_logger.info(
            f"{status_emoji} SQL_EXECUTED | ID: {request_id} | Status: {execution_status} | "
            f"Rows: {row_count} | Duration: {duration}ms"
        )

        if error:
            self.error_logger.error(
                f"❌ SQL_EXECUTION_ERROR | ID: {request_id} | Error: {error} | SQL: {sql[:200]}{'...' if len(sql) > 200 else ''}"
            )

    def log_conversational_response(self, request_id: str, response_type: str,
                                  response_length: int, duration: int):
        """Log conversational response generation"""
        self.chat_logger.info(
            f"💬 CONVERSATIONAL_RESPONSE | ID: {request_id} | Type: {response_type} | "
            f"Length: {response_length} | Duration: {duration}ms"
        )

    def log_response_preparation(self, request_id: str, response_type: str,
                               has_sql: bool, has_data: bool, has_conversational: bool,
                               total_rows: int):
        """Log final response preparation"""
        features = []
        if has_sql: features.append("SQL")
        if has_data: features.append("Data")
        if has_conversational: features.append("Conversational")

        self.chat_logger.info(
            f"📦 RESPONSE_PREPARED | ID: {request_id} | Type: {response_type} | "
            f"Features: {', '.join(features)} | TotalRows: {total_rows}"
        )

    def log_cache_hit(self, request_id: str, cache_type: str, key: str):
        """Log cache hits"""
        self.performance_logger.info(
            f"💾 CACHE_HIT | ID: {request_id} | Type: {cache_type} | Key: {key[:32]}{'...' if len(key) > 32 else ''}"
        )

    def log_cache_miss(self, request_id: str, cache_type: str, key: str, reason: str = ""):
        """Log cache misses"""
        reason_str = f" | Reason: {reason}" if reason else ""
        self.performance_logger.info(
            f"💾 CACHE_MISS | ID: {request_id} | Type: {cache_type} | Key: {key[:32]}{'...' if len(key) > 32 else ''}{reason_str}"
        )

    def log_database_query(self, request_id: str, query_type: str, table_name: Optional[str],
                          duration: int, row_count: Optional[int] = None):
        """Log database operations"""
        row_info = f" | Rows: {row_count}" if row_count is not None else ""
        table_info = f" | Table: {table_name}" if table_name else ""

        self.performance_logger.debug(
            f"🗄️  DB_QUERY | ID: {request_id} | Type: {query_type}{table_info} | "
            f"Duration: {duration}ms{row_info}"
        )

    def log_memory_usage(self, request_id: str, step: str, memory_mb: float):
        """Log memory usage at different steps"""
        self.performance_logger.debug(
            f"🧠 MEMORY_USAGE | ID: {request_id} | Step: {step} | Memory: {memory_mb:.2f}MB"
        )

    def log_pipeline_metrics(self, request_id: str, pipeline_name: str,
                           stage_times: Dict[str, int], total_time: int,
                           error_count: int, success_rate: float):
        """Log comprehensive pipeline metrics"""
        stages_str = ", ".join(f"{k}:{v}ms" for k, v in stage_times.items())

        self.performance_logger.info(
            f"📊 PIPELINE_METRICS | ID: {request_id} | Pipeline: {pipeline_name} | "
            f"TotalTime: {total_time}ms | Stages: {stages_str} | "
            f"Errors: {error_count} | SuccessRate: {success_rate:.1%}"
        )


# Global chatbot logger instance
chatbot_logger = ChatbotLogger()


def create_request_context(request_id: str, conversation_id: str, user_question: str,
                          snapshot_id: int, model_id: int, language: str,
                          bot_id: Optional[int] = None, bot_name: Optional[str] = None) -> ChatRequestContext:
    """Create a chat request context for logging"""
    return ChatRequestContext(
        request_id=request_id,
        conversation_id=conversation_id,
        user_question=user_question,
        snapshot_id=snapshot_id,
        model_id=model_id,
        language=language,
        bot_id=bot_id,
        bot_name=bot_name
    )
