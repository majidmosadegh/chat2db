"""
Loguru Configuration
Configure loguru to save logs in project directory instead of default locations
"""

import sys
import os
from pathlib import Path

# Disable loguru auto-initialization before importing
# This prevents loguru from setting up default handlers that write to system locations
os.environ.setdefault('LOGURU_AUTOINIT', 'false')

# Now safe to import loguru
from loguru import logger


def setup_loguru():
    """
    Configure loguru logger to save logs in project logs directory
    
    This ensures all loguru logs are saved in backend/logs instead of
    default system locations (like C: drive on Windows)
    """
    # Get project root directory (backend folder)
    backend_dir = Path(__file__).parent.parent
    
    # Create logs directory in project
    logs_dir = backend_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Remove default loguru handler (which might write to system default location)
    logger.remove()
    
    # Add console handler with color
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # Add main log file with rotation
    main_log_file = logs_dir / "app.log"
    logger.add(
        main_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )
    
    # Add error-only log file
    error_log_file = logs_dir / "errors.log"
    logger.add(
        error_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="5 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )
    
    # Add warning and above log file
    warning_log_file = logs_dir / "warnings.log"
    logger.add(
        warning_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="WARNING",
        rotation="5 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )
    
    logger.info(f"Loguru configured: Logs will be saved to {logs_dir}")
    logger.debug(f"Main log: {main_log_file}")
    logger.debug(f"Error log: {error_log_file}")
    logger.debug(f"Warning log: {warning_log_file}")

