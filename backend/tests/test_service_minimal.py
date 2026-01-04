"""
Minimal AI Dictionary Service Test
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_dictionary_types import (
    TableGenerationResult, JobState, TableState
)

logger = logging.getLogger(__name__)


class AIDictionaryGenerationService:
    """Minimal AI dictionary generation service"""

    def __init__(self):
        self._connector = None
        self._running_tasks: Dict[str, asyncio.Task] = {}

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status"""
        return {"job_id": job_id, "status": "test"}


# Global service instance
ai_dictionary_service = AIDictionaryGenerationService()

print("Minimal service created successfully")
