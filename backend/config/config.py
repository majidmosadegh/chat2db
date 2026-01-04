"""
Configuration management for the backend application.
Loads environment variables with sensible defaults.
"""
import os
from typing import List

# Server configuration
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "metadata.db"))
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# CORS configuration
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001")
CORS_ORIGINS: List[str] = [origin.strip() for origin in CORS_ORIGINS_STR.split(",")]

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Debug mode
DEBUG = ENVIRONMENT == "development"






