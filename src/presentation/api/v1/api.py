"""
Main API Router for v1 endpoints.
Clean REST API that delegates to application handlers.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from ....application.commands.generate_ai_dictionary_command import GenerateAIDictionaryCommand
from ....application.queries.execute_sql_query import ExecuteSQLQuery
from ....application.handlers.generate_ai_dictionary_handler import GenerateAIDictionaryHandler
from ....application.handlers.execute_sql_handler import ExecuteSQLHandler
from ....infrastructure.config.dependencies import get_ai_handler, get_sql_handler

# Import response models
from .models import (
    GenerateAIDictionaryRequest,
    GenerateAIDictionaryResponse,
    ExecuteSQLRequest,
    ExecuteSQLResponse,
    APIResponse
)

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.post(
    "/ai-dictionary/generate",
    response_model=APIResponse[GenerateAIDictionaryResponse]
)
async def generate_ai_dictionary(
    request: GenerateAIDictionaryRequest,
    handler: GenerateAIDictionaryHandler = Depends(get_ai_handler)
) -> APIResponse[GenerateAIDictionaryResponse]:
    """
    Generate AI dictionary for a database snapshot.
    """
    try:
        command = GenerateAIDictionaryCommand.create(
            snapshot_id=request.snapshot_id,
            business_domain=request.business_domain,
            database_description=request.database_description,
            target_user=request.target_user,
            language=request.language,
            notes=request.notes
        )

        result = await handler.handle(command)

        return APIResponse(
            success=True,
            data=GenerateAIDictionaryResponse(**result),
            message="AI dictionary generation started successfully"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sql/execute",
    response_model=APIResponse[ExecuteSQLResponse]
)
async def execute_sql(
    request: ExecuteSQLRequest,
    handler: ExecuteSQLHandler = Depends(get_sql_handler)
) -> APIResponse[ExecuteSQLResponse]:
    """
    Execute SQL query against a database connection.
    """
    try:
        query = ExecuteSQLQuery.create(
            connection_id=request.connection_id,
            sql=request.sql,
            limit=request.limit
        )

        result = await handler.handle(query)

        return APIResponse(
            success=True,
            data=ExecuteSQLResponse(
                results=result["results"],
                execution_time=result["execution_time"],
                row_count=len(result["results"])
            ),
            message="SQL executed successfully"
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return APIResponse(
        success=True,
        data={"status": "healthy", "version": "1.0.0"},
        message="Service is healthy"
    )









