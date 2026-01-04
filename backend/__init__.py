"""
Backend package initialization
Ensures loguru is configured before any other modules import it
"""

# Configure loguru BEFORE any imports that might use it
# This must be the FIRST thing that runs when backend package is imported
import os
import sys
from pathlib import Path

# Disable loguru auto-initialization to prevent default handlers
os.environ.setdefault('LOGURU_AUTOINIT', 'false')

# Setup loguru configuration
try:
    # Add backend to path
    backend_dir = Path(__file__).parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    # Import and setup loguru
    from core.loguru_config import setup_loguru
    setup_loguru()
except Exception as e:
    # If setup fails, log to stderr (safe fallback)
    print(f"Warning: Failed to setup loguru: {e}", file=sys.stderr)
