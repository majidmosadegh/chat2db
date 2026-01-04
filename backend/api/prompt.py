from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List, Optional
import json

from .db_models import (
    SchemaMetadata, DataDictionary, Relationship, UseCase,
    GeneratedPrompt, LLMModel, SchemaSnapshot, get_db_session
)
from llm import ModelConnector, LLMRequest, Message, MessageRole
from llm.registry import initialize_registry, ConfigRegistryLoader
from llm.exceptions import ModelNotFoundError, ModelGenerationError
from .database import decrypt_api_key


router = APIRouter()


class PromptGenerationRequest(BaseModel):
    include_data_dictionary: bool = True
    include_relationships: bool = True
    include_use_cases: bool = True
    custom_instructions: Optional[str] = None


class GeneratedPromptResponse(BaseModel):
    id: int
    version: int
    prompt_text: str
    model_name: str
    schema_snapshot_name: str
    schema_snapshot_id: int
    tables_count: int
    columns_count: int
    relationships_count: int
    created_at: str


def build_meta_prompt(
    schema_data: List[dict],
    data_dictionary: List[dict],
    relationships: List[dict],
    use_cases: List[dict],
    custom_instructions: Optional[str] = None
) -> str:
    """Build the meta-prompt that will be sent to the LLM"""

    meta_prompt = """You are a Text-to-SQL prompt engineering expert. Your task is to create a high-quality system prompt for a Text-to-SQL agent.

Based on the following database information, generate a system prompt that will guide an LLM to convert natural language questions into accurate SQL queries.

CRITICAL REQUIREMENTS:
- The generated prompt must restrict SQL generation to SELECT statements only
- Avoid any SQL that modifies data (INSERT, UPDATE, DELETE, DROP, etc.)
- Prefer explicit JOINs over implicit joins
- Respect database schema and column descriptions
- Be aware of database-specific syntax
- Handle NULL values appropriately
- Use proper quoting for identifiers

DATABASE INFORMATION:
"""

    # Add schema information
    meta_prompt += "\nSCHEMA INFORMATION:\n"
    tables = {}
    for item in schema_data:
        key = f"{item['schema_name']}.{item['table_name']}"
        if key not in tables:
            tables[key] = {
                "schema": item['schema_name'],
                "table": item['table_name'],
                "columns": []
            }
        tables[key]["columns"].append({
            "name": item['column_name'],
            "type": item['column_type'],
            "is_primary_key": item['is_primary_key'],
            "is_foreign_key": item['is_foreign_key'],
            "foreign_key_table": item.get('foreign_key_table'),
            "foreign_key_column": item.get('foreign_key_column')
        })

    for table_key, table_info in tables.items():
        meta_prompt += f"\nTable: {table_key}\n"
        for col in table_info["columns"]:
            pk_marker = " (PRIMARY KEY)" if col['is_primary_key'] else ""
            fk_marker = f" (FOREIGN KEY -> {col['foreign_key_table']}.{col['foreign_key_column']})" if col['is_foreign_key'] else ""
            meta_prompt += f"  - {col['name']} ({col['type']}){pk_marker}{fk_marker}\n"

    # Add data dictionary
    if data_dictionary:
        meta_prompt += "\nDATA DICTIONARY:\n"
        for item in data_dictionary:
            table_key = f"{item['schema_name']}.{item['table_name']}"
            if item['column_name']:
                meta_prompt += f"\nColumn: {table_key}.{item['column_name']}\n"
            else:
                meta_prompt += f"\nTable: {table_key}\n"

            if item['description']:
                meta_prompt += f"Description: {item['description']}\n"
            if item['example_values']:
                try:
                    examples = json.loads(item['example_values'])
                    meta_prompt += f"Example values: {', '.join(examples)}\n"
                except (json.JSONDecodeError, TypeError):
                    meta_prompt += f"Example values: {item['example_values']}\n"
            if item['synonyms']:
                meta_prompt += f"Synonyms: {item['synonyms']}\n"
            if item['is_sensitive']:
                meta_prompt += "⚠️ SENSITIVE DATA - Handle with care\n"

    # Add relationships
    if relationships:
        meta_prompt += "\nLOGICAL RELATIONSHIPS:\n"
        for rel in relationships:
            meta_prompt += f"\n- {rel['source_table']}.{rel['source_column']} {rel['join_type']} {rel['target_table']}.{rel['target_column']}\n"
            meta_prompt += f"  Description: {rel['description']}\n"

    # Add use cases
    if use_cases:
        meta_prompt += "\nBUSINESS USE CASES:\n"
        for uc in use_cases:
            meta_prompt += f"\nUse Case: {uc['name']}\n"
            meta_prompt += f"Business Goal: {uc['business_goal']}\n"
            meta_prompt += f"Output Style: {uc['output_style']}\n"
            if uc['example_questions']:
                try:
                    questions = json.loads(uc['example_questions'])
                    meta_prompt += f"Example Questions: {', '.join(questions)}\n"
                except (json.JSONDecodeError, TypeError):
                    meta_prompt += f"Example Questions: {uc['example_questions']}\n"

    # Add custom instructions
    if custom_instructions:
        meta_prompt += f"\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}\n"

    meta_prompt += """

OUTPUT REQUIREMENTS:
- Your response must contain ONLY the final system prompt text
- Do not include any explanations, comments, or metadata
- The system prompt should be comprehensive and guide the Text-to-SQL agent effectively
- Include specific examples of how to handle common query patterns
- Emphasize data security and appropriate SQL generation

Generate the system prompt now:"""

    return meta_prompt


@router.post("/generate", response_model=GeneratedPromptResponse)
async def generate_prompt(
    request: PromptGenerationRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Generate a new system prompt using the active LLM"""

    # Get active model
    result = await session.execute(select(LLMModel).where(LLMModel.is_active == True))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=400, detail="No active LLM model found")

    # Collect data
    schema_data = []
    data_dictionary = []
    relationships = []
    use_cases = []

    # Get schema metadata
    schema_result = await session.execute(select(SchemaMetadata))
    schema_items = schema_result.scalars().all()
    for item in schema_items:
        schema_data.append({
            "schema_name": item.schema_name,
            "table_name": item.table_name,
            "column_name": item.column_name,
            "column_type": item.column_type,
            "is_primary_key": item.is_primary_key,
            "is_foreign_key": item.is_foreign_key,
            "foreign_key_table": item.foreign_key_table,
            "foreign_key_column": item.foreign_key_column
        })

    if not schema_data:
        raise HTTPException(status_code=400, detail="No schema metadata found. Please run schema introspection first.")

    # Get data dictionary if requested
    if request.include_data_dictionary:
        dd_result = await session.execute(select(DataDictionary))
        dd_items = dd_result.scalars().all()
        for item in dd_items:
            data_dictionary.append({
                "schema_name": item.schema_name,
                "table_name": item.table_name,
                "column_name": item.column_name,
                "description": item.description,
                "example_values": item.example_values,
                "synonyms": item.synonyms,
                "is_sensitive": item.is_sensitive
            })

    # Get relationships if requested
    if request.include_relationships:
        rel_result = await session.execute(select(Relationship))
        rel_items = rel_result.scalars().all()
        for item in rel_items:
            relationships.append({
                "source_table": item.source_table,
                "source_column": item.source_column,
                "target_table": item.target_table,
                "target_column": item.target_column,
                "description": item.description,
                "join_type": item.join_type
            })

    # Get use cases if requested
    if request.include_use_cases:
        uc_result = await session.execute(select(UseCase))
        uc_items = uc_result.scalars().all()
        for item in uc_items:
            use_cases.append({
                "name": item.name,
                "business_goal": item.business_goal,
                "example_questions": item.example_questions,
                "output_style": item.output_style
            })

    # Build meta-prompt
    meta_prompt = build_meta_prompt(
        schema_data, data_dictionary, relationships, use_cases, request.custom_instructions
    )

    # Initialize ModelConnector for LLM generation
    # Load all active models from database for registry
    result = await session.execute(select(LLMModel).where(LLMModel.is_active == True))
    models = result.scalars().all()

    # Create registry configuration
    config = {"models": []}
    for db_model in models:
        # Map service_name to provider type
        provider_map = {
            "OpenAI": "openai",
            "Ollama": "ollama",
            "vLLM": "vllm",
        }
        provider = provider_map.get(db_model.service_name, "custom")

        config["models"].append({
            "id": str(db_model.id),
            "provider": provider,
            "base_url": db_model.base_url,
            "model_name": db_model.model_name,
            "api_key": decrypt_api_key(db_model.api_key) if db_model.api_key else None,
            "supports_chat": True,
            "supports_json": provider == "openai",
            "max_tokens": db_model.max_tokens,
            "is_active": True,
            "timeout_seconds": 1200.0,  # 20 minutes for complex prompt generation
        })

    # Initialize registry and connector
    loader = ConfigRegistryLoader(config)
    registry = initialize_registry(loader)
    await registry.load()

    connector = ModelConnector(registry)

    # Create LLM request for prompt generation
    llm_request = LLMRequest(
        model_id=str(model.id),
        messages=[Message(role=MessageRole.USER, content=meta_prompt)],
        temperature=0.2,  # Low temperature for consistent prompt generation
        max_tokens=4096
    )

    # Generate prompt using ModelConnector
    try:
        response = await connector.generate(llm_request)
        generated_prompt_text = response.text
    except (ModelNotFoundError, ModelGenerationError) as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")

    # Get next version number
    version_result = await session.execute(select(func.max(GeneratedPrompt.version)))
    max_version = version_result.scalar() or 0
    next_version = max_version + 1

    # Store the generated prompt
    generated_prompt = GeneratedPrompt(
        version=next_version,
        prompt_text=generated_prompt_text,
        model_id=model.id
    )

    session.add(generated_prompt)
    await session.commit()
    await session.refresh(generated_prompt)

    return GeneratedPromptResponse(
        id=generated_prompt.id,
        version=generated_prompt.version,
        prompt_text=generated_prompt.prompt_text,
        model_name=model.name,
        created_at=generated_prompt.created_at.isoformat()
    )


@router.get("/", response_model=List[GeneratedPromptResponse])
async def get_generated_prompts(session: AsyncSession = Depends(get_db_session)):
    """Get all generated prompts"""
    from sqlalchemy import func, distinct

    # Get prompts with additional metadata
    result = await session.execute(
        select(
            GeneratedPrompt,
            LLMModel.name.label('model_name'),
            SchemaSnapshot.name.label('schema_name'),
            SchemaSnapshot.id.label('schema_id'),
            # Count distinct tables
            func.count(distinct(SchemaMetadata.table_name)).label('tables_count'),
            # Count total columns
            func.count(SchemaMetadata.id).label('columns_count'),
            # Count relationships
            func.count(distinct(Relationship.id)).label('relationships_count')
        )
        .join(LLMModel)
        .join(SchemaSnapshot)
        .outerjoin(SchemaMetadata, SchemaMetadata.schema_snapshot_id == SchemaSnapshot.id)
        .outerjoin(Relationship, Relationship.schema_snapshot_id == SchemaSnapshot.id)
        .group_by(GeneratedPrompt.id, LLMModel.name, SchemaSnapshot.name, SchemaSnapshot.id)
        .order_by(GeneratedPrompt.version.desc())
    )

    prompts = []
    for row in result:
        prompts.append(GeneratedPromptResponse(
            id=row.GeneratedPrompt.id,
            version=row.GeneratedPrompt.version,
            prompt_text=row.GeneratedPrompt.prompt_text,
            model_name=row.model_name,
            schema_snapshot_name=row.schema_name,
            schema_snapshot_id=row.schema_id,
            tables_count=row.tables_count or 0,
            columns_count=row.columns_count or 0,
            relationships_count=row.relationships_count or 0,
            created_at=row.GeneratedPrompt.created_at.isoformat()
        ))

    return prompts


@router.get("/{version}", response_model=GeneratedPromptResponse)
async def get_prompt_by_version(version: int, session: AsyncSession = Depends(get_db_session)):
    """Get a specific prompt by version"""
    from sqlalchemy import func, distinct

    result = await session.execute(
        select(
            GeneratedPrompt,
            LLMModel.name.label('model_name'),
            SchemaSnapshot.name.label('schema_name'),
            SchemaSnapshot.id.label('schema_id'),
            # Count distinct tables
            func.count(distinct(SchemaMetadata.table_name)).label('tables_count'),
            # Count total columns
            func.count(SchemaMetadata.id).label('columns_count'),
            # Count relationships
            func.count(distinct(Relationship.id)).label('relationships_count')
        )
        .join(LLMModel)
        .join(SchemaSnapshot)
        .outerjoin(SchemaMetadata, SchemaMetadata.schema_snapshot_id == SchemaSnapshot.id)
        .outerjoin(Relationship, Relationship.schema_snapshot_id == SchemaSnapshot.id)
        .where(GeneratedPrompt.version == version)
        .group_by(GeneratedPrompt.id, LLMModel.name, SchemaSnapshot.name, SchemaSnapshot.id)
    )

    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")

    return GeneratedPromptResponse(
        id=row.GeneratedPrompt.id,
        version=row.GeneratedPrompt.version,
        prompt_text=row.GeneratedPrompt.prompt_text,
        model_name=row.model_name,
        schema_snapshot_name=row.schema_name,
        schema_snapshot_id=row.schema_id,
        tables_count=row.tables_count or 0,
        columns_count=row.columns_count or 0,
        relationships_count=row.relationships_count or 0,
        created_at=row.GeneratedPrompt.created_at.isoformat()
    )


@router.get("/latest/version", response_model=GeneratedPromptResponse)
async def get_latest_prompt(session: AsyncSession = Depends(get_db_session)):
    """Get the latest generated prompt"""
    result = await session.execute(
        select(GeneratedPrompt, LLMModel.name)
        .join(LLMModel)
        .order_by(GeneratedPrompt.version.desc())
        .limit(1)
    )

    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="No prompts found")

    prompt, model_name = row
    return GeneratedPromptResponse(
        id=prompt.id,
        version=prompt.version,
        prompt_text=prompt.prompt_text,
        model_name=model_name,
        created_at=prompt.created_at.isoformat()
    )
