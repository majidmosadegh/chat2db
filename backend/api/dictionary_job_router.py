"""
Dictionary Job API Router
Handles all dictionary generation endpoints including WebSocket for realtime updates
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db_session
from services.ai_dictionary_generator import ai_dictionary_generator, GenerationScope

logger = logging.getLogger(__name__)

# Router
router = APIRouter(tags=["dictionary-job"])

# Pydantic Models
class DictionaryJobRequest(BaseModel):
    snapshot_id: int
    business_domain: str
    language: str = "persian"
    audience: str
    tone: str
    target_scope: str  # "column" | "table" | "multi_table" | "full_snapshot"
    target_names: List[str]
    row_sample_limit: int = 5

class DictionaryJobResponse(BaseModel):
    success: bool
    message: str
    job_id: Optional[str] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total_tables: int
    completed_tables: int
    failed_tables: int
    progress: Dict[str, Any]
    errors: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class TableControlRequest(BaseModel):
    table_name: str  # schema.table format

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        logger.info(f"WebSocket connection established for job {job_id}")

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        logger.info(f"WebSocket connection closed for job {job_id}")

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

@router.post("/generate", response_model=DictionaryJobResponse)
async def generate_dictionary(
    request: DictionaryJobRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """Generate AI dictionary for specified scope"""
    try:
        # Validate scope
        try:
            scope = GenerationScope(request.target_scope)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target_scope: {request.target_scope}. Must be one of: column, table, multi_table, full_snapshot"
            )

        # Create job
        job_id = await ai_dictionary_generator.create_job(
            session=session,
            snapshot_id=request.snapshot_id,
            business_domain=request.business_domain,
            language=request.language,
            audience=request.audience,
            tone=request.tone,
            scope=scope,
            target_names=request.target_names,
            row_sample_limit=request.row_sample_limit
        )

        # Start job in background
        background_tasks.add_task(ai_dictionary_generator.start_job, job_id)

        return DictionaryJobResponse(
            success=True,
            message="Dictionary generation job created and started successfully",
            job_id=job_id
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to create dictionary generation job: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {error_msg}")

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get dictionary job status"""
    try:
        job_data = await ai_dictionary_generator.get_job_status(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        # Calculate statistics
        table_tasks = job_data.get("table_tasks", {})
        total_tables = len(table_tasks)
        completed_tables = sum(1 for t in table_tasks.values() if t["status"] == "done")
        failed_tables = sum(1 for t in table_tasks.values() if t["status"] == "failed")

        return JobStatusResponse(
            job_id=job_data["job_id"],
            status=job_data["status"],
            total_tables=total_tables,
            completed_tables=completed_tables,
            failed_tables=failed_tables,
            progress=job_data["table_tasks"],
            errors=[],  # TODO: Extract errors from table tasks
            created_at=job_data.get("created_at"),
            updated_at=job_data.get("updated_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to get job status for {job_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {error_msg}")

@router.post("/jobs/{job_id}/table/{table_name}/pause")
async def pause_table_task(job_id: str, table_name: str):
    """Pause a specific table task"""
    try:
        success = await ai_dictionary_generator.pause_table_task(job_id, table_name)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} or table {table_name} not found, or task cannot be paused"
            )

        # Broadcast status update
        await manager.broadcast_to_job(job_id, {
            "type": "table_status_update",
            "job_id": job_id,
            "table_name": table_name,
            "status": "paused",
            "timestamp": asyncio.get_event_loop().time()
        })

        return {"success": True, "message": f"Table task {table_name} paused"}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to pause table task {table_name} in job {job_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to pause task: {error_msg}")

@router.post("/jobs/{job_id}/table/{table_name}/resume")
async def resume_table_task(job_id: str, table_name: str):
    """Resume a specific table task"""
    try:
        success = await ai_dictionary_generator.resume_table_task(job_id, table_name)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} or table {table_name} not found, or task cannot be resumed"
            )

        # Broadcast status update
        await manager.broadcast_to_job(job_id, {
            "type": "table_status_update",
            "job_id": job_id,
            "table_name": table_name,
            "status": "resumed",
            "timestamp": asyncio.get_event_loop().time()
        })

        return {"success": True, "message": f"Table task {table_name} resumed"}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to resume table task {table_name} in job {job_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to resume task: {error_msg}")

@router.post("/jobs/{job_id}/table/{table_name}/stop")
async def stop_table_task(job_id: str, table_name: str):
    """Stop a specific table task"""
    try:
        success = await ai_dictionary_generator.stop_table_task(job_id, table_name)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} or table {table_name} not found, or task cannot be stopped"
            )

        # Broadcast status update
        await manager.broadcast_to_job(job_id, {
            "type": "table_status_update",
            "job_id": job_id,
            "table_name": table_name,
            "status": "stopped",
            "timestamp": asyncio.get_event_loop().time()
        })

        return {"success": True, "message": f"Table task {table_name} stopped"}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to stop table task {table_name} in job {job_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to stop task: {error_msg}")

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel an entire dictionary job"""
    try:
        success = await ai_dictionary_generator.cancel_job(job_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found or cannot be canceled"
            )

        # Broadcast job cancellation
        await manager.broadcast_to_job(job_id, {
            "type": "job_cancelled",
            "job_id": job_id,
            "timestamp": asyncio.get_event_loop().time()
        })

        return {"success": True, "message": f"Job {job_id} canceled"}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to cancel job {job_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {error_msg}")

@router.websocket("/ws/dictionary-job-status/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for realtime dictionary job status updates

    Expected message format from client:
    {
        "type": "subscribe",
        "job_id": "job_id"
    }

    Server will send updates in format:
    {
        "type": "job_status_update" | "table_status_update" | "job_cancelled",
        "job_id": "job_id",
        "table_name": "schema.table_name",  // only for table updates
        "status": "processing|done|failed|paused|canceled",
        "progress": 75.0,  // table progress percentage
        "sample_row_preview": [...],  // optional sample data
        "error_message": "error details",  // if failed
        "timestamp": 1234567890.123
    }
    """
    await manager.connect(job_id, websocket)

    try:
        # Send initial status
        job_data = await ai_dictionary_generator.get_job_status(job_id)
        if job_data:
            await websocket.send_json({
                "type": "job_status_update",
                "job_id": job_id,
                "status": job_data["status"],
                "progress": job_data["table_tasks"],
                "timestamp": asyncio.get_event_loop().time()
            })

        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages with timeout
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)

                # Handle client messages if needed
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "status_request":
                    # Send current status
                    job_data = await ai_dictionary_generator.get_job_status(job_id)
                    if job_data:
                        await websocket.send_json({
                            "type": "job_status_update",
                            "job_id": job_id,
                            "status": job_data["status"],
                            "progress": job_data["table_tasks"],
                            "timestamp": asyncio.get_event_loop().time()
                        })

            except asyncio.TimeoutError:
                # Send periodic keepalive
                await websocket.send_json({"type": "keepalive"})
                continue

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        manager.disconnect(job_id, websocket)

# Background task to periodically broadcast status updates
async def status_broadcast_worker():
    """Background worker to broadcast status updates to WebSocket connections"""
    while True:
        try:
            # Get all active jobs
            active_job_ids = list(manager.active_connections.keys())

            for job_id in active_job_ids:
                try:
                    job_data = await ai_dictionary_generator.get_job_status(job_id)
                    if job_data:
                        # Check if status changed since last broadcast
                        # For now, broadcast current status every 5 seconds
                        await manager.broadcast_to_job(job_id, {
                            "type": "job_status_update",
                            "job_id": job_id,
                            "status": job_data["status"],
                            "progress": job_data["table_tasks"],
                            "timestamp": asyncio.get_event_loop().time()
                        })
                except Exception as e:
                    logger.error(f"Failed to broadcast status for job {job_id}: {e}")

            await asyncio.sleep(5)  # Broadcast every 5 seconds

        except Exception as e:
            logger.error(f"Error in status broadcast worker: {e}")
            await asyncio.sleep(5)

# Global background task reference
_status_broadcast_task = None

@asynccontextmanager
async def lifespan_manager():
    """Lifespan manager for router-specific startup/shutdown"""
    global _status_broadcast_task

    # Startup
    _status_broadcast_task = asyncio.create_task(status_broadcast_worker())
    logger.info("Dictionary job router started with status broadcast worker")

    yield

    # Shutdown
    if _status_broadcast_task:
        _status_broadcast_task.cancel()
        try:
            await _status_broadcast_task
        except asyncio.CancelledError:
            pass
    logger.info("Dictionary job router shutdown")

# Test endpoint
@router.post("/test")
async def test_dictionary_job_router():
    """Test endpoint for dictionary job router"""
    return {
        "message": "Dictionary Job Router is working",
        "endpoints": [
            "POST /generate - Create and start dictionary generation job",
            "GET /jobs/{job_id} - Get job status",
            "POST /jobs/{job_id}/table/{table_name}/pause - Pause table task",
            "POST /jobs/{job_id}/table/{table_name}/resume - Resume table task",
            "POST /jobs/{job_id}/table/{table_name}/stop - Stop table task",
            "POST /jobs/{job_id}/cancel - Cancel entire job",
            "WS /ws/dictionary-job-status/{job_id} - Realtime status updates"
        ]
    }
