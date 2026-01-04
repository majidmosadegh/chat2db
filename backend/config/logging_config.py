"""
Logging Configuration for Chatbot Troubleshooting

This module provides comprehensive logging configuration for debugging
and troubleshooting the chatbot system, including LLM interactions,
database operations, and performance metrics.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any

# Create logs directory if it doesn't exist
# Use backend/logs instead of config/logs to centralize all logs
backend_dir = Path(__file__).parent.parent
logs_dir = backend_dir / "logs"
logs_dir.mkdir(exist_ok=True)

# Log file paths
CHAT_LOG_FILE = logs_dir / "chatbot.log"
LLM_LOG_FILE = logs_dir / "llm_calls.log"
ERROR_LOG_FILE = logs_dir / "errors.log"
PERFORMANCE_LOG_FILE = logs_dir / "performance.log"

# Logging formatters
class ChatFormatter(logging.Formatter):
    """Custom formatter for chat-related logs"""

    def format(self, record):
        # Add timestamp and session info
        if hasattr(record, 'session_id'):
            record.msg = f"[Session:{record.session_id}] {record.msg}"

        # Format the message
        formatted = super().format(record)

        # Add separators for major events
        if record.levelno >= logging.INFO:
            return f"\n{'='*80}\n{formatted}\n{'='*80}"
        elif record.levelno >= logging.WARNING:
            return f"\n{'-'*60}\n{formatted}\n{'-'*60}"

        return formatted

class LLMFormatter(logging.Formatter):
    """Custom formatter for LLM-related logs"""

    def format(self, record):
        # Add model and timing info
        if hasattr(record, 'model_id'):
            record.msg = f"[Model:{record.model_id}] {record.msg}"
        if hasattr(record, 'latency_ms'):
            record.msg = f"{record.msg} ({record.latency_ms}ms)"

        return super().format(record)

# Configure formatters
detailed_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

simple_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

chat_formatter = ChatFormatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

llm_formatter = LLMFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def setup_logging(log_level: str = "INFO", enable_file_logging: bool = True) -> None:
    """
    Setup comprehensive logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_file_logging: Whether to enable file logging
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler for all logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)

    if enable_file_logging:
        # Main application log file
        main_handler = logging.handlers.RotatingFileHandler(
            CHAT_LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(main_handler)

        # LLM-specific log file
        llm_handler = logging.handlers.RotatingFileHandler(
            LLM_LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        llm_handler.setLevel(logging.DEBUG)
        llm_handler.setFormatter(llm_formatter)
        llm_handler.addFilter(lambda record: 'llm' in record.name.lower() or 'model' in record.getMessage().lower())
        root_logger.addHandler(llm_handler)

        # Error-only log file
        error_handler = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)

        # Performance log file
        perf_handler = logging.handlers.RotatingFileHandler(
            PERFORMANCE_LOG_FILE,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(simple_formatter)
        perf_handler.addFilter(lambda record: any(keyword in record.getMessage().lower()
                                                  for keyword in ['performance', 'timing', 'latency', 'time']))
        root_logger.addHandler(perf_handler)

    # Configure specific loggers
    # Chat orchestrator - detailed logging
    chat_logger = logging.getLogger('backend.chat.orchestrator')
    chat_logger.setLevel(logging.DEBUG)

    # LLM components - detailed logging
    llm_logger = logging.getLogger('backend.llm')
    llm_logger.setLevel(logging.DEBUG)

    # LLM providers - detailed logging
    provider_logger = logging.getLogger('backend.llm.providers')
    provider_logger.setLevel(logging.DEBUG)

    # Database operations - info level
    db_logger = logging.getLogger('backend.db')
    db_logger.setLevel(logging.INFO)

    # API endpoints - info level
    api_logger = logging.getLogger('backend.api')
    api_logger.setLevel(logging.INFO)

    # Suppress noisy third-party logs
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"STARTUP: Logging configured: level={log_level}, files={enable_file_logging}")
    if enable_file_logging:
        logger.info(f"FILES: Log files created at: {CHAT_LOG_FILE}, {LLM_LOG_FILE}, {ERROR_LOG_FILE}, {PERFORMANCE_LOG_FILE}")

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance"""
    return logging.getLogger(name)

def log_chat_event(session_id: str, event: str, data: Dict[str, Any] = None) -> None:
    """Log a chat-related event with structured data"""
    logger = logging.getLogger('chat.events')

    # Add session context
    extra = {'session_id': session_id}

    if data:
        # Format data as JSON for structured logging
        data_str = ", ".join(f"{k}={v}" for k, v in data.items())
        logger.info(f"EVENT: {event}: {data_str}", extra=extra)
    else:
        logger.info(f"📝 {event}", extra=extra)

def log_llm_call(model_id: str, request_data: Dict[str, Any], response_data: Dict[str, Any] = None, latency_ms: int = None) -> None:
    """Log an LLM API call with details"""
    logger = logging.getLogger('llm.calls')

    extra = {'model_id': model_id}
    if latency_ms:
        extra['latency_ms'] = latency_ms

    logger.info(f"LLM_CALL: Model: {model_id}", extra=extra)

    if request_data:
        logger.debug(f"📤 Request: {request_data}", extra=extra)

    if response_data:
        logger.debug(f"📥 Response: {response_data}", extra=extra)

def log_performance(operation: str, duration: float, metadata: Dict[str, Any] = None) -> None:
    """Log performance metrics"""
    logger = logging.getLogger('performance')

    message = f"⚡ {operation}: {duration:.2f}s"
    if metadata:
        metadata_str = ", ".join(f"{k}={v}" for k, v in metadata.items())
        message += f" ({metadata_str})"

    logger.info(f"PERF: {message}")

# Initialize logging on import
setup_logging()
