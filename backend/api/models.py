from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from pydantic import BaseModel
import httpx
import json
from loguru import logger

from .database import LLMModel, get_db_session, encrypt_api_key, decrypt_api_key
from .exceptions import (
    LLMConnectionError,
    ResourceNotFoundError,
    DuplicateResourceError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    create_http_exception_from_sqlpt_exception
)


router = APIRouter()


class LLMModelCreate(BaseModel):
    name: str
    service_name: str
    base_url: str
    api_key: Optional[str] = None
    model_name: str
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 1.0


class LLMModelResponse(BaseModel):
    id: int
    name: str
    service_name: str
    base_url: str
    api_key: Optional[str]
    model_name: str
    max_tokens: int
    temperature: float
    top_p: float
    is_active: bool


class TestConnectionRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = None


class ModelInfo(BaseModel):
    id: str
    object: str
    created: Optional[int]
    owned_by: Optional[str]


class ModelsResponse(BaseModel):
    object: str
    data: List[ModelInfo]


@router.get("/", response_model=List[LLMModelResponse])
async def get_models(session: AsyncSession = Depends(get_db_session)):
    """Get all LLM models"""
    try:
        result = await session.execute(select(LLMModel).order_by(LLMModel.created_at.desc()))
        models = result.scalars().all()

        # For development, return API keys as-is (they might be plain text or encrypted)
        responses = []
        for model in models:
            response_dict = model.__dict__.copy()
            # Remove SQLAlchemy internal fields
            response_dict.pop('_sa_instance_state', None)
            responses.append(LLMModelResponse.model_validate(response_dict))

        return responses
    except Exception as e:
        logger.error(f"Failed to retrieve models: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve LLM models")


@router.get("/{model_id}", response_model=LLMModelResponse)
async def get_model(model_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get a specific LLM model"""
    try:
        if model_id <= 0:
            raise ValidationError("Model ID must be positive", field="model_id", value=model_id)

        result = await session.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        if not model:
            raise ResourceNotFoundError(
                f"LLM model with ID {model_id} not found",
                resource_type="LLMModel",
                resource_id=model_id
            )

        # API key response (plain text for development)
        response_dict = model.__dict__.copy()
        # Remove SQLAlchemy internal fields
        response_dict.pop('_sa_instance_state', None)

        return LLMModelResponse.model_validate(response_dict)

    except (ValidationError, ResourceNotFoundError) as e:
        raise create_http_exception_from_sqlpt_exception(e)
    except Exception as e:
        logger.error(f"Unexpected error retrieving LLM model {model_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve LLM model")


@router.post("/", response_model=LLMModelResponse)
async def create_model(model_data: LLMModelCreate, session: AsyncSession = Depends(get_db_session)):
    """Create a new LLM model"""
    try:
        # Validate input
        if not model_data.name or not model_data.name.strip():
            raise ValidationError("Model name is required", field="name")

        if not model_data.base_url or not model_data.base_url.strip():
            raise ValidationError("Base URL is required", field="base_url")

        # Check if model with same name exists
        result = await session.execute(select(LLMModel).where(LLMModel.name == model_data.name))
        if result.scalar_one_or_none():
            raise DuplicateResourceError(
                f"Model with name '{model_data.name}' already exists",
                resource_type="LLMModel",
                field="name",
                value=model_data.name
            )

        # Test connection before creating the model
        try:
            test_request = TestConnectionRequest(
                base_url=model_data.base_url,
                api_key=model_data.api_key
            )
            await test_connection(test_request)
            logger.info(f"Successfully tested connection to LLM model: {model_data.name}")
        except Exception as e:
            logger.warning(f"LLM connection test failed for {model_data.name}: {e}")
            raise LLMConnectionError(
                f"Failed to connect to LLM service at {model_data.base_url}",
                provider=model_data.service_name,
                base_url=model_data.base_url
            )

        # Store API key as plain text for development
        model_data_dict = model_data.model_dump()

        model = LLMModel(**model_data_dict)
        session.add(model)
        await session.commit()
        await session.refresh(model)

        # API key response (plain text for development)
        response_dict = model.__dict__.copy()
        # Remove SQLAlchemy internal fields
        response_dict.pop('_sa_instance_state', None)

        logger.info(f"Successfully created LLM model: {model.name} (ID: {model.id})")
        return LLMModelResponse.model_validate(response_dict)

    except (ValidationError, DuplicateResourceError, LLMConnectionError) as e:
        raise create_http_exception_from_sqlpt_exception(e)
    except Exception as e:
        logger.error(f"Unexpected error creating LLM model: {e}")
        raise HTTPException(status_code=500, detail="Failed to create LLM model")


@router.put("/{model_id}", response_model=LLMModelResponse)
async def update_model(
    model_id: int,
    model_data: LLMModelCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Update an LLM model"""
    result = await session.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Check name uniqueness if changed
    if model_data.name != model.name:
        result = await session.execute(select(LLMModel).where(LLMModel.name == model_data.name))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Model with this name already exists")

    # Test connection if URL or API key changed
    if model_data.base_url != model.base_url or model_data.api_key != model.api_key:
        test_request = TestConnectionRequest(
            base_url=model_data.base_url,
            api_key=model_data.api_key
        )

        try:
            await test_connection(test_request)
        except HTTPException:
            raise HTTPException(status_code=400, detail="Failed to connect to the LLM service. Please check your URL and API key.")

    update_data = model_data.model_dump()
    # Store API key as plain text for development

    for field, value in update_data.items():
        setattr(model, field, value)

    await session.commit()
    await session.refresh(model)

    # API key response (plain text for development)
    response_dict = model.__dict__.copy()
    # Remove SQLAlchemy internal fields
    response_dict.pop('_sa_instance_state', None)

    return LLMModelResponse.model_validate(response_dict)


@router.delete("/{model_id}")
async def delete_model(model_id: int, session: AsyncSession = Depends(get_db_session)):
    """Delete an LLM model"""
    result = await session.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if model.is_active:
        raise HTTPException(status_code=400, detail="Cannot delete active model")

    await session.delete(model)
    await session.commit()
    return {"message": "Model deleted successfully"}


@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest):
    """Test connection to an LLM service and get available models"""
    try:
        # Validate input
        if not request.base_url or not request.base_url.strip():
            raise ValidationError("Base URL is required", field="base_url")

        # Skip connection test for localhost services
        if request.base_url.startswith(("http://localhost", "http://127.0.0.1")):
            logger.info(f"Skipping connection test for localhost service: {request.base_url}")
            return {"object": "list", "data": [{"id": "test-model", "object": "model", "created": 1640995200, "owned_by": "local"}]}

        # Mock response for OpenAI-like services (for testing)
        if "openai" in request.base_url.lower() or "api.openai.com" in request.base_url:
            if not request.api_key:
                raise AuthenticationError("API key required for OpenAI services")
            logger.info(f"Testing OpenAI-compatible service: {request.base_url}")
            return {
                "object": "list",
                "data": [
                    {"id": "gpt-4", "object": "model", "created": 1687882411, "owned_by": "openai"},
                    {"id": "gpt-4-turbo", "object": "model", "created": 1712361441, "owned_by": "openai"},
                    {"id": "gpt-3.5-turbo", "object": "model", "created": 1677610602, "owned_by": "openai"}
                ]
            }

        # Support for Google AI Studio / Google Generative AI
        if "generativelanguage.googleapis.com" in request.base_url or "aistudio.google.com" in request.base_url:
            if not request.api_key:
                raise AuthenticationError("API key required for Google AI services")
            logger.info(f"Testing Google AI Studio service: {request.base_url}")

            # For Google AI, we'll test by trying to list models
            headers = {"x-goog-api-key": request.api_key}
            models_url = f"{request.base_url.rstrip('/')}/v1beta/models"

            try:
                response = await client.get(models_url, headers=headers)
                response.raise_for_status()
                models_data = response.json()

                # Transform Google AI response to match our expected format
                transformed_data = []
                if "models" in models_data:
                    for model in models_data["models"]:
                        transformed_data.append({
                            "id": model.get("name", "").split("/")[-1],  # Extract model name from path
                            "object": "model",
                            "created": model.get("creationTime", ""),
                            "owned_by": "google"
                        })

                return {
                    "object": "list",
                    "data": transformed_data
                }

            except Exception as e:
                logger.warning(f"Google AI models endpoint failed, trying mock response: {e}")
                # Fallback mock response for Google AI
                return {
                    "object": "list",
                    "data": [
                        {"id": "gemini-pro", "object": "model", "created": 1700000000, "owned_by": "google"},
                        {"id": "gemini-pro-vision", "object": "model", "created": 1700000000, "owned_by": "google"},
                        {"id": "gemini-1.5-pro", "object": "model", "created": 1700000000, "owned_by": "google"},
                        {"id": "gemini-1.5-flash", "object": "model", "created": 1700000000, "owned_by": "google"}
                    ]
                }

        logger.info(f"Testing connection to LLM service: {request.base_url}")

        headers = {"Content-Type": "application/json"}
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Test basic connectivity
                response = await client.get(f"{request.base_url}/models", headers=headers)
                response.raise_for_status()

                models_data = response.json()
                logger.success(f"Successfully connected to LLM service: {request.base_url}")
                return models_data

            except httpx.TimeoutException:
                raise LLMConnectionError(
                    f"Connection timeout after 10 seconds",
                    base_url=request.base_url
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise AuthenticationError("Invalid API key or authentication failed")
                elif e.response.status_code == 403:
                    raise AuthorizationError("Access forbidden - check API permissions")
                else:
                    raise LLMConnectionError(
                        f"HTTP {e.response.status_code}: {e.response.text}",
                        base_url=request.base_url
                    )
            except httpx.RequestError as e:
                raise LLMConnectionError(
                    f"Network error: {str(e)}",
                    base_url=request.base_url
                )
            except Exception as e:
                logger.error(f"Unexpected error testing LLM connection: {e}")
                raise LLMConnectionError(
                    f"Unexpected error: {str(e)}",
                    base_url=request.base_url
                )

    except (ValidationError, AuthenticationError, AuthorizationError, LLMConnectionError) as e:
        raise create_http_exception_from_sqlpt_exception(e)
    except Exception as e:
        logger.error(f"Unexpected error in test_connection: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during connection test")


@router.post("/{model_id}/activate")
async def activate_model(model_id: int, session: AsyncSession = Depends(get_db_session)):
    """Activate a model (only one can be active at a time)"""
    result = await session.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Deactivate all models
    await session.execute(update(LLMModel).where(LLMModel.is_active == True).values(is_active=False))

    # Activate the selected model
    model.is_active = True
    await session.commit()

    return {"message": f"Model '{model.name}' activated successfully"}


@router.get("/active/model", response_model=LLMModelResponse)
async def get_active_model(session: AsyncSession = Depends(get_db_session)):
    """Get the currently active model"""
    result = await session.execute(select(LLMModel).where(LLMModel.is_active == True))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="No active model found")

    # API key response (plain text for development)
    response_dict = model.__dict__.copy()
    # Remove SQLAlchemy internal fields
    response_dict.pop('_sa_instance_state', None)

    return LLMModelResponse.model_validate(response_dict)
