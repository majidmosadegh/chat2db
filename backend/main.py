"""
SQL PT Backend - Main Entry Point
Uses centralized core application factory for clean architecture.
"""

# IMPORTANT: Configure loguru FIRST before any other imports
# This prevents loguru from writing to default Windows locations (C: drive)
import sys
from pathlib import Path

# Add backend to path if not already there
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Setup loguru BEFORE any other imports (especially modules that use loguru)
try:
    from core.loguru_config import setup_loguru
    setup_loguru()
except Exception as e:
    # If setup fails, at least try to prevent default loguru behavior
    import os
    os.environ.setdefault('LOGURU_AUTOINIT', 'false')
    print(f"Warning: Failed to setup loguru: {e}")

# Now safe to import other modules
import uvicorn
import logging
import os

# Configure logging (loguru is already configured above)
# This is for standard logging module
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Create console handler that handles Unicode encoding errors gracefully
class SafeConsoleHandler(logging.StreamHandler):
    """Console handler that safely handles Unicode encoding errors"""
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            # If encoding fails, replace problematic characters with '?' instead of crashing
            try:
                msg = record.getMessage()
                # Replace problematic Unicode characters with placeholder
                safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
                record.msg = safe_msg
                record.args = ()
                super().emit(record)
            except Exception:
                pass  # If still fails, silently ignore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'errors.log'), encoding='utf-8'),
        SafeConsoleHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import configuration
try:
    from config.config import HOST, PORT
except ImportError:
    # Fallback for when running from different directory
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from config.config import HOST, PORT

# Create application using centralized factory
from core import create_application
app = create_application()

# Add a simple test route
@app.get("/simple-test")
async def simple_test():
    return {"message": "Simple test works"}

@app.post("/start-workers")
async def start_workers():
    """Manually start AI dictionary workers for testing"""
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator
        if not ai_dictionary_generator._workers:
            logger.info("Manually starting worker tasks")
            import asyncio
            for i in range(ai_dictionary_generator._max_concurrent_jobs):
                if not ai_dictionary_generator._shutdown_event.is_set():
                    worker = asyncio.create_task(ai_dictionary_generator._process_queue_worker(i))
                    ai_dictionary_generator._workers.append(worker)
            return {"message": f"Started {len(ai_dictionary_generator._workers)} workers"}
        else:
            return {"message": f"Workers already running: {len(ai_dictionary_generator._workers)}"}
    except Exception as e:
        logger.error(f"Failed to start workers: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    logger.info(f"Starting SQL PT Backend v2.0.0 on {HOST}:{PORT}")
    logger.info(f"Logs are saved to: {logs_dir}")
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,  # Disable auto-reload to prevent constant restart due to .pyc files
        log_level="info",
        access_log=False  # Disable uvicorn access logs to reduce noise (we use loguru)
    )
