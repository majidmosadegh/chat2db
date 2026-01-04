"""
AI Dictionary Generation API
Clean and unified endpoints for AI dictionary operations
MAINTAINS BACKWARD COMPATIBILITY while using new dictionary generator service
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from .database import get_db_session
# Import services locally to avoid circular imports
# from services.ai_dictionary_generator import ai_dictionary_generator, GenerationScope

# Router
router = APIRouter(tags=["ai-dictionary"])

# Pydantic Models (Legacy - maintained for backward compatibility)
class AIDictionaryGenerateRequest(BaseModel):
    snapshot_id: int
    business_domain: str
    database_description: str  # Maps to audience in new system
    target_user: str  # Maps to audience in new system
    language: Optional[str] = "persian"
    additional_notes: Optional[str] = None

class AIDictionaryGenerateResponse(BaseModel):
    success: bool
    message: str
    job_id: Optional[str] = None

class AIDictionaryJobStatusResponse(BaseModel):
    job_id: str
    status: str
    total_tables: int
    completed_tables: int
    failed_tables: int
    progress: Dict[str, Any]
    errors: list
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@router.post("/generate", response_model=AIDictionaryGenerateResponse)
async def generate_ai_dictionary(
    request: AIDictionaryGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Generate AI dictionary for a database snapshot (Legacy endpoint - uses new service)"""
    try:
        # Import locally to avoid circular imports
        from services.ai_dictionary_generator import ai_dictionary_generator, GenerationScope

        # Map legacy fields to new service format
        # Note: Legacy API doesn't support target_scope/target_names, so defaults to full_snapshot
        job_id = await ai_dictionary_generator.create_job(
            session=session,
            snapshot_id=request.snapshot_id,
            business_domain=request.business_domain,
            language=request.language or "persian",
            audience=request.target_user,  # target_user maps to audience
            tone="professional",  # Default tone for legacy compatibility
            scope=GenerationScope.FULL_SNAPSHOT,  # Default to full snapshot for legacy compatibility
            target_names=[],  # Empty for full snapshot
            row_sample_limit=5
        )

        # Start job in background
        background_tasks.add_task(ai_dictionary_generator.start_job, job_id)

        return AIDictionaryGenerateResponse(
            success=True,
            message="AI dictionary generation started successfully",
            job_id=job_id
        )

    except Exception as e:
        error_msg = str(e).encode('utf-8', errors='ignore').decode('utf-8')
        raise HTTPException(status_code=500, detail=f"Failed to start AI dictionary generation: {error_msg}")

@router.get("/jobs/{job_id}", response_model=AIDictionaryJobStatusResponse)
async def get_ai_dictionary_job_status(job_id: str):
    """Get AI dictionary job status (Legacy endpoint - uses new service)"""
    try:
        # Import locally to avoid circular imports
        from services.ai_dictionary_generator import ai_dictionary_generator

        job_data = await ai_dictionary_generator.get_job_status(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        # Map new service response to legacy format
        table_tasks = job_data.get("table_tasks", {})
        total_tables = len(table_tasks)
        completed_tables = sum(1 for t in table_tasks.values() if t["status"] == "done")
        failed_tables = sum(1 for t in table_tasks.values() if t["status"] == "failed")

        # Extract errors from table tasks
        errors = []
        for table_key, task in table_tasks.items():
            if task.get("error_message"):
                errors.append({
                    "table": table_key,
                    "error": task["error_message"]
                })

        legacy_response = {
            "job_id": job_data["job_id"],
            "status": job_data["status"],
            "total_tables": total_tables,
            "completed_tables": completed_tables,
            "failed_tables": failed_tables,
            "progress": table_tasks,  # Keep new format for progress
            "errors": errors,
            "created_at": job_data.get("created_at"),
            "updated_at": job_data.get("updated_at")
        }

        return AIDictionaryJobStatusResponse(**legacy_response)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e).encode('utf-8', errors='ignore').decode('utf-8')
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {error_msg}")

@router.post("/test")
async def test_endpoint():
    return {"message": "AI dictionary router works"}








