"""
Use Case Job API Router
Handles use case generation endpoints with WebSocket for realtime updates
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db_session
from services.use_case_generator import use_case_generator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["use-case-job"])


class UseCaseJobRequest(BaseModel):
    snapshot_id: int
    business_context: str
    primary_audience: List[str]
    typical_questions: List[str]
    output_preference: str
    number_of_use_cases: int
    language: str
    sample_questions: Optional[List[str]] = None
    scope: str = "snapshot"
    table: Optional[str] = None
    column: Optional[str] = None


class UseCaseJobResponse(BaseModel):
    success: bool
    message: str
    job_id: Optional[str] = None


class UseCaseJobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    error: Optional[str] = None
    use_cases: Optional[List[Dict[str, Any]]] = None
    generation_log_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        logger.info(f"WebSocket connection established for use case job {job_id}")

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        logger.info(f"WebSocket connection closed for use case job {job_id}")

    async def broadcast_to_job(self, job_id: str, message: Dict[str, Any]):
        """Broadcast message to all connections for a specific job"""
        if job_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[job_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to WebSocket: {e}")
                    disconnected.append(websocket)

            # Clean up disconnected websockets
            for websocket in disconnected:
                self.disconnect(job_id, websocket)


manager = ConnectionManager()


@router.post("/generate", response_model=UseCaseJobResponse)
async def generate_use_cases(
    request: UseCaseJobRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Create and start a use case generation job"""
    try:
        logger.info(f"Creating use case generation job for snapshot {request.snapshot_id}")
        
        # Create job
        job_id = await use_case_generator.create_job(
            session=session,
            snapshot_id=request.snapshot_id,
            business_context=request.business_context,
            primary_audience=request.primary_audience,
            typical_questions=request.typical_questions,
            output_preference=request.output_preference,
            number_of_use_cases=request.number_of_use_cases,
            language=request.language,
            sample_questions=request.sample_questions,
            scope=request.scope,
            table=request.table,
            column=request.column
        )

        # Start job in background
        background_tasks.add_task(use_case_generator.start_job, job_id)

        logger.info(f"Use case generation job {job_id} created and started")
        
        return UseCaseJobResponse(
            success=True,
            message="Use case generation job created and started successfully",
            job_id=job_id
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to create use case generation job: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {error_msg}")


@router.get("/jobs/{job_id}", response_model=UseCaseJobStatusResponse)
async def get_job_status(job_id: str):
    """Get use case generation job status"""
    try:
        job_data = await use_case_generator.get_job_status(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        return UseCaseJobStatusResponse(
            job_id=job_data["job_id"],
            status=job_data["status"],
            progress=job_data["progress"],
            error=job_data.get("error"),
            use_cases=job_data.get("use_cases"),
            generation_log_id=job_data.get("generation_log_id"),
            created_at=job_data.get("created_at"),
            updated_at=job_data.get("updated_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a use case generation job"""
    try:
        success = await use_case_generator.cancel_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found or cannot be canceled"
            )
        
        return {"success": True, "message": f"Job {job_id} canceled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.websocket("/ws/use-case-job-status/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for realtime use case generation job status updates

    Server will send updates in format:
    {
        "type": "job_status_update",
        "job_id": "job_id",
        "status": "waiting|processing|done|failed|canceled",
        "progress": 75.0,
        "use_cases": [...],  // when done
        "generation_log_id": 123,  // when done
        "error": "error message",  // if failed
        "timestamp": 1234567890.123
    }
    """
    await manager.connect(job_id, websocket)

    try:
        # Send initial status
        job_data = await use_case_generator.get_job_status(job_id)
        if job_data:
            await websocket.send_json({
                "type": "job_status_update",
                "job_id": job_id,
                "status": job_data["status"],
                "progress": job_data["progress"],
                "error": job_data.get("error"),
                "use_cases": job_data.get("use_cases"),
                "generation_log_id": job_data.get("generation_log_id"),
                "timestamp": asyncio.get_event_loop().time()
            })

        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages with timeout
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)

                # Handle client messages
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "status_request":
                    # Send current status
                    job_data = await use_case_generator.get_job_status(job_id)
                    if job_data:
                        await websocket.send_json({
                            "type": "job_status_update",
                            "job_id": job_id,
                            "status": job_data["status"],
                            "progress": job_data["progress"],
                            "error": job_data.get("error"),
                            "use_cases": job_data.get("use_cases"),
                            "generation_log_id": job_data.get("generation_log_id"),
                            "timestamp": asyncio.get_event_loop().time()
                        })

            except asyncio.TimeoutError:
                # Send periodic keepalive
                await websocket.send_json({"type": "keepalive"})
                continue

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for use case job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for use case job {job_id}: {e}")
    finally:
        manager.disconnect(job_id, websocket)

