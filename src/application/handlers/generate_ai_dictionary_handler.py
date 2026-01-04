"""
Generate AI Dictionary Handler.
Handles the GenerateAIDictionaryCommand by orchestrating the AI generation process.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime, timezone

from ..commands.generate_ai_dictionary_command import GenerateAIDictionaryCommand
from ...domain.services.ai_dictionary_service import AIDictionaryService
from ...application.interfaces.ai_dictionary_repository import IAIDictionaryRepository
from ...application.interfaces.llm_service import ILLMService
from ...application.interfaces.unit_of_work import IUnitOfWork

logger = logging.getLogger(__name__)


class GenerateAIDictionaryHandler:
    """Handler for generating AI dictionary."""

    def __init__(
        self,
        ai_service: AIDictionaryService,
        llm_service: ILLMService,
        repository: IAIDictionaryRepository,
        unit_of_work: IUnitOfWork
    ):
        self.ai_service = ai_service
        self.llm_service = llm_service
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def handle(self, command: GenerateAIDictionaryCommand) -> Dict[str, Any]:
        """
        Handle the generate AI dictionary command.

        Args:
            command: The command to handle

        Returns:
            Dictionary containing job information
        """
        logger.info(f"Starting AI dictionary generation for snapshot {command.snapshot_id}")

        try:
            # Start the generation job
            job_id = await self.ai_service.start_generation_job(
                snapshot_id=command.snapshot_id,
                business_domain=command.business_domain,
                database_description=command.database_description,
                target_user=command.target_user,
                language=command.language,
                notes=command.notes
            )

            # Start background processing (in a real implementation, this would use a queue)
            asyncio.create_task(self._process_job_async(job_id, command))

            logger.info(f"AI dictionary generation job {job_id} started successfully")

            return {
                "job_id": job_id,
                "status": "started",
                "message": "AI dictionary generation has been started",
                "command_id": command.command_id
            }

        except Exception as e:
            logger.error(f"Failed to start AI dictionary generation: {e}")
            raise

    async def _process_job_async(self, job_id: str, command: GenerateAIDictionaryCommand) -> None:
        """
        Process the AI generation job asynchronously.
        In a real implementation, this would be handled by a background worker/queue.
        """
        try:
            logger.info(f"Processing AI dictionary job {job_id} asynchronously")

            # Process the job using the AI service
            await self.ai_service.process_generation_job(
                job_id=job_id,
                snapshot_id=command.snapshot_id,
                business_domain=command.business_domain,
                database_description=command.database_description,
                target_user=command.target_user,
                language=command.language,
                llm_service=self.llm_service,
                repository=self.repository,
                unit_of_work=self.unit_of_work
            )

            logger.info(f"AI dictionary job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"AI dictionary job {job_id} failed: {e}")

            # Update job status to failed
            async with self.unit_of_work:
                await self.repository.update_job_status(
                    job_id=job_id,
                    status="failed",
                    error=str(e)
                )









