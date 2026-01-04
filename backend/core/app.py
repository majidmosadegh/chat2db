"""
Centralized FastAPI Application Factory
Creates and configures the main application with all routes and middleware.
"""

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Loguru should already be configured by backend/__init__.py
# But setup again here as a safety measure
try:
    from .loguru_config import setup_loguru
    setup_loguru()
except Exception:
    # Already configured or failed, continue
    pass

from .container import container
from config.config import HOST, PORT, CORS_ORIGINS, DEBUG
from api import (
    database, schema, prompt_generator, database_connection,
    use_cases, llm, text_generation, fine_tuning, prompt,
    relationships, smart_use_case_builder, models, data_dictionary,
    ai_dictionary, dictionary_job_router, use_case_job_router,
    use_case_maturation, maturation
)
from chat import router as chat_router
from api.db_models import create_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting SQL PT Backend...")

    # Create database tables
    try:
        await create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        # Don't fail startup if DB creation fails
    
    # Run migrations for ai_generation_jobs
    try:
        from scripts.migrate_ai_generation_jobs import migrate_ai_generation_jobs
        await migrate_ai_generation_jobs()
        logger.info("[OK] AI generation jobs migration completed")
    except Exception as e:
        logger.warning(f"[WARNING] Migration warning (may be OK if columns already exist): {e}")
        # Don't fail startup if migration fails (columns may already exist)
    
    # Run migrations for maturation_sessions
    try:
        from scripts.migrate_maturation_sessions import migrate_maturation_sessions
        await migrate_maturation_sessions()
        logger.info("[OK] Maturation sessions migration completed")
    except Exception as e:
        logger.warning(f"[WARNING] Maturation sessions migration warning (may be OK if column already exists): {e}")
        # Don't fail startup if migration fails (column may already exist)

    # Initialize services
    try:
        # Initialize AI Dictionary Generator service
        try:
            from services.ai_dictionary_generator import ai_dictionary_generator
            logger.info("About to initialize AI Dictionary Generator")
            await ai_dictionary_generator.initialize()
            logger.info("AI Dictionary Generator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI Dictionary Generator in lifespan: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        logger.info("[OK] AI Dictionary Generator service initialized")
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize AI Dictionary Generator service: {e}")
        # Don't fail startup if service init fails

    yield

    logger.info("Shutting down SQL PT Backend...")
    await container.shutdown()

    # Shutdown AI Dictionary Generator service
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator
        await ai_dictionary_generator.shutdown()
        logger.info("[OK] AI Dictionary Generator service shutdown")
    except Exception as e:
        logger.error(f"❌ Failed to shutdown AI Dictionary Generator service: {e}")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    Centralizes all route registration and middleware setup.
    """

    app = FastAPI(
        title="SQL PT Backend",
        description="Professional SQL Prompt Tuning Backend with AI Dictionary Generation",
        version="2.0.0",
        lifespan=lifespan,
        debug=DEBUG
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    api_routes = [
        (database.router, "/api/database", "database"),
        (schema.router, "/api/schema", "schema"),
        (prompt_generator.router, "/api/prompt-generator", "prompt-generator"),
        (database_connection.router, "/api/database-connection", "database-connection"),
        (use_cases.use_cases_router, "/api/use-cases", "use-cases"),
        (llm.router, "/api/llm", "llm"),
        (text_generation.router, "/api/text-generation", "text-generation"),
        (fine_tuning.router, "/api/fine-tuning", "fine-tuning"),
        (prompt.router, "/api/prompt", "prompt"),
        (relationships.router, "/api/relationships", "relationships"),
        (smart_use_case_builder.router, "/api/smart-use-case-builder", "smart-use-case-builder"),
        (models.router, "/api/models", "models"),
        (data_dictionary.router, "/api/data-dictionary", "data-dictionary"),
        (ai_dictionary.router, "/api/ai/dictionary", "ai-dictionary"),
        (dictionary_job_router.router, "/api/dictionary-job", "dictionary-job"),
        (use_case_job_router.router, "/api/use-case-job", "use-case-job"),
        (use_case_maturation.router, "/api", "use-case-maturation"),
        (maturation.router, "/api/maturation", "maturation"),
        (chat_router.router, "/api/chat", "chat"),
    ]

    for router, prefix, tags in api_routes:
        if prefix:
            app.include_router(router, prefix=prefix, tags=[tags])
        else:
            app.include_router(router, tags=[tags])

    # Health check
    @app.get("/health")
    def health_check():
        return {
            "status": "healthy",
            "server": "sql-pt-backend",
            "version": "2.0.0"
        }

    @app.get("/test")
    def test():
        return {"message": "Server works!"}

    @app.get("/test-bg")
    async def test_background(background_tasks: BackgroundTasks):
        """Test background task"""
        async def bg_task():
            import asyncio
            await asyncio.sleep(2)
            print("Background task executed!")

        background_tasks.add_task(bg_task)
        return {"message": "Background task scheduled"}

    @app.get("/test-ai-bg")
    async def test_ai_background(background_tasks: BackgroundTasks):
        """Test AI background task"""
        async def ai_bg_task():
            from services.ai_dictionary_service import ai_dictionary_service
            try:
                await ai_dictionary_service._process_generation_job("dict_1_089e2472", 1, "Energy Trading", "Energy exchange database", "data analyst", "persian", None)
                print("AI Background task completed!")
            except Exception as e:
                print(f"AI Background task failed: {e}")

        background_tasks.add_task(ai_bg_task)
        return {"message": "AI background task scheduled"}

    return app
