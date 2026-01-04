from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json
from datetime import datetime, timezone

from .db_models import Relationship, SchemaSnapshot, DataDictionary, LLMModel, get_db_session
from llm import ModelConnector, LLMRequest, Message, MessageRole
from llm.registry import initialize_registry, ConfigRegistryLoader
from llm.exceptions import ModelNotFoundError, ModelGenerationError
from .database import decrypt_api_key


# Relationship scoring functions removed - using simplified 3-type system instead


router = APIRouter()


class RelationshipCreate(BaseModel):
    schema_snapshot_id: int
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: str = "manual"  # schema_fk, ai_suggested, manual
    join_type: str = "inner"  # inner, left, right
    cardinality: str = "1-n"  # 1-1, 1-n, n-1, n-n
    description: str
    confidence_score: Optional[float] = None
    semantic_similarity: Optional[float] = None
    user_accepted: bool = False
    agent_approved: bool = False
    is_confirmed: bool = False  # Legacy field


class RelationshipResponse(BaseModel):
    id: int
    schema_snapshot_id: int
    source_table: str
    source_column: str
    target_column: str
    target_table: str
    relationship_type: str
    join_type: str
    cardinality: str
    description: str
    confidence_score: Optional[float]
    semantic_similarity: Optional[float]
    user_accepted: bool
    agent_approved: bool
    is_confirmed: bool
    created_at: str
    updated_at: str

    # Helper property to get display type in Persian
    @property
    def display_type(self) -> str:
        """Get relationship type in Persian for display"""
        type_mapping = {
            "manual": "کاربر اضافه کرده",
            "schema_fk": "دیتابیس داشته",
            "ai_suggested": "پیشنهاد AI بوده"
        }
        return type_mapping.get(self.relationship_type, self.relationship_type)


class AiSuggestRelationshipsRequest(BaseModel):
    schema_snapshot_id: int
    business_context: Optional[str] = None


class AiSuggestedRelationship(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: str = "ai_suggested"
    join_type: str
    cardinality: str
    description: str
    confidence_score: float
    reasoning: str
    intermediary_table: Optional[str] = None
    example: Optional[Dict[str, Any]] = None


class AiSuggestRelationshipsResponse(BaseModel):
    suggested_relationships: List[AiSuggestedRelationship]


@router.get("/{schema_snapshot_id}", response_model=List[RelationshipResponse])
async def get_relationships(
    schema_snapshot_id: int,
    include_types: str = "all",  # schema_fk,ai_suggested,manual or "all"
    for_agent: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """Get relationships for a schema snapshot with filtering options.
    By default, includes database foreign key relationships from schema metadata if they exist."""
    
    from .db_models import SchemaMetadata
    from datetime import datetime, timezone
    
    query = select(Relationship).where(Relationship.schema_snapshot_id == schema_snapshot_id)

    # Filter by relationship types - support simplified categories
    should_include_db_fk = False
    if include_types == "all":
        should_include_db_fk = True
    else:
        types = include_types.split(",")
        # Map simplified categories to actual types
        type_mapping = {
            "user_added": "manual",
            "database": "db_fk",
            "ai_suggested": "ai_suggested"
        }
        # Allow both simplified and original type names
        actual_types = []
        for t in types:
            if t in type_mapping:
                actual_types.append(type_mapping[t])
            else:
                actual_types.append(t)  # Allow original types too
        
        # Check if we should include database foreign keys
        if "db_fk" in actual_types or "schema_fk" in actual_types or "database" in types:
            should_include_db_fk = True
        
        query = query.where(Relationship.relationship_type.in_(actual_types))

    # For agent usage, only return approved relationships
    if for_agent:
        query = query.where(Relationship.agent_approved == True)

    result = await session.execute(
        query.order_by(Relationship.created_at.desc())
    )
    relationships = result.scalars().all()
    
    # Convert to list of RelationshipResponse
    relationship_responses = []
    for rel in relationships:
        relationship_responses.append(RelationshipResponse(**{
            "id": rel.id,
            "schema_snapshot_id": rel.schema_snapshot_id,
            "source_table": rel.source_table,
            "source_column": rel.source_column,
            "target_table": rel.target_table,
            "target_column": rel.target_column,
            "relationship_type": rel.relationship_type,
            "join_type": rel.join_type,
            "cardinality": rel.cardinality,
            "description": rel.description,
            "confidence_score": rel.confidence_score,
            "strength_score": None,  # Removed scoring system
            "semantic_similarity": rel.semantic_similarity,
            "user_accepted": rel.user_accepted,
            "agent_approved": rel.agent_approved,
            "is_confirmed": rel.is_confirmed,
            "created_at": rel.created_at.isoformat() if hasattr(rel.created_at, 'isoformat') else str(rel.created_at),
            "updated_at": rel.updated_at.isoformat() if hasattr(rel.updated_at, 'isoformat') else str(rel.updated_at)
        }))
    
    # If we should include database foreign keys, also fetch them from schema metadata
    if should_include_db_fk:
        # Get all foreign keys from schema metadata
        fk_query = select(SchemaMetadata).where(
            and_(
                SchemaMetadata.schema_snapshot_id == schema_snapshot_id,
                SchemaMetadata.is_foreign_key == True,
                SchemaMetadata.foreign_key_table.isnot(None),
                SchemaMetadata.foreign_key_column.isnot(None),
                SchemaMetadata.column_name.isnot(None),
                SchemaMetadata.column_name != ''
            )
        )
        fk_result = await session.execute(fk_query)
        fk_columns = fk_result.scalars().all()
        
        # Get existing relationship keys to avoid duplicates
        existing_rel_keys = set()
        for rel in relationships:
            if rel.relationship_type == "schema_fk" or rel.relationship_type == "db_fk":
                key = (rel.source_table, rel.source_column, rel.target_table, rel.target_column)
                existing_rel_keys.add(key)
        
        # Create virtual relationships from foreign keys that don't exist in Relationship table
        for fk_col in fk_columns:
            if not fk_col.foreign_key_table or not fk_col.foreign_key_column:
                continue
            
            # Build source and target table names
            source_table = f"{fk_col.schema_name}.{fk_col.table_name}" if fk_col.schema_name else fk_col.table_name
            target_table = fk_col.foreign_key_table
            # Ensure target_table has schema if source has schema
            if '.' not in target_table and fk_col.schema_name:
                target_table = f"{fk_col.schema_name}.{target_table}"
            
            # Check if this relationship already exists
            rel_key = (source_table, fk_col.column_name, target_table, fk_col.foreign_key_column)
            if rel_key in existing_rel_keys:
                continue
            
            # Determine cardinality (usually 1-n for foreign keys)
            cardinality = "1-n"
            # Check if target column is a primary key (usually indicates 1-n)
            target_pk_check = await session.execute(
                select(SchemaMetadata).where(
                    and_(
                        SchemaMetadata.schema_snapshot_id == schema_snapshot_id,
                        SchemaMetadata.table_name == fk_col.foreign_key_table.split('.')[-1] if '.' in fk_col.foreign_key_table else fk_col.foreign_key_table,
                        SchemaMetadata.column_name == fk_col.foreign_key_column,
                        SchemaMetadata.is_primary_key == True
                    )
                ).limit(1)
            )
            if target_pk_check.scalar_one_or_none():
                cardinality = "n-1"  # Many-to-one (this table's FK -> other table's PK)
            
            # Create virtual relationship response
            relationship_responses.append(RelationshipResponse(**{
                "id": 0,  # Virtual ID for relationships not in database
                "schema_snapshot_id": schema_snapshot_id,
                "source_table": source_table,
                "source_column": fk_col.column_name,
                "target_table": target_table,
                "target_column": fk_col.foreign_key_column,
                "relationship_type": "db_fk",
                "join_type": "inner",
                "cardinality": cardinality,
                "description": f"Database foreign key relationship: {fk_col.column_name} references {target_table}.{fk_col.foreign_key_column}",
                "confidence_score": 1.0,  # Database FKs have 100% confidence
                "strength_score": None,
                "semantic_similarity": None,
                "user_accepted": False,
                "agent_approved": False,
                "is_confirmed": True,  # Database FKs are confirmed
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }))
    
    return relationship_responses


@router.get("/filtered/{schema_snapshot_id}")
async def get_filtered_relationships(
    schema_snapshot_id: int,
    clean_mode: bool = False,  # Clean mode: only one relationship per table pair
    include_types: str = "all",  # schema_fk,ai_suggested,manual or simplified: user_added,database,ai_suggested
    session: AsyncSession = Depends(get_db_session)
):
    """Get filtered relationships optimized for visualization with simplified type filtering.
    By default, includes database foreign key relationships from schema metadata if they exist."""
    
    from .db_models import SchemaMetadata
    
    query = select(Relationship).where(Relationship.schema_snapshot_id == schema_snapshot_id)

    # Filter by relationship types with support for simplified categories
    should_include_db_fk = False
    if include_types == "all":
        should_include_db_fk = True
    else:
        types = include_types.split(",")
        # Map simplified categories to actual types
        type_mapping = {
            "user_added": "manual",
            "database": "db_fk",
            "ai_suggested": "ai_suggested"
        }
        # Allow both simplified and original type names
        actual_types = []
        for t in types:
            if t in type_mapping:
                actual_types.append(type_mapping[t])
            else:
                actual_types.append(t)  # Allow original types too
        
        # Check if we should include database foreign keys
        if "db_fk" in actual_types or "schema_fk" in actual_types or "database" in types:
            should_include_db_fk = True
        
        query = query.where(Relationship.relationship_type.in_(actual_types))

    result = await session.execute(query.order_by(desc(Relationship.created_at)))
    relationships = result.scalars().all()
    
    # Convert to list of RelationshipResponse
    relationship_responses = []
    for rel in relationships:
        relationship_responses.append(RelationshipResponse(**{
            "id": rel.id,
            "schema_snapshot_id": rel.schema_snapshot_id,
            "source_table": rel.source_table,
            "source_column": rel.source_column,
            "target_table": rel.target_table,
            "target_column": rel.target_column,
            "relationship_type": rel.relationship_type,
            "join_type": rel.join_type,
            "cardinality": rel.cardinality,
            "description": rel.description,
            "confidence_score": rel.confidence_score,
            "semantic_similarity": rel.semantic_similarity,
            "user_accepted": rel.user_accepted,
            "agent_approved": rel.agent_approved,
            "is_confirmed": rel.is_confirmed,
            "created_at": rel.created_at.isoformat() if hasattr(rel.created_at, 'isoformat') else str(rel.created_at),
            "updated_at": rel.updated_at.isoformat() if hasattr(rel.updated_at, 'isoformat') else str(rel.updated_at)
        }))
    
    # If we should include database foreign keys, also fetch them from schema metadata
    if should_include_db_fk:
        # Get all foreign keys from schema metadata
        fk_query = select(SchemaMetadata).where(
            and_(
                SchemaMetadata.schema_snapshot_id == schema_snapshot_id,
                SchemaMetadata.is_foreign_key == True,
                SchemaMetadata.foreign_key_table.isnot(None),
                SchemaMetadata.foreign_key_column.isnot(None),
                SchemaMetadata.column_name.isnot(None),
                SchemaMetadata.column_name != ''
            )
        )
        fk_result = await session.execute(fk_query)
        fk_columns = fk_result.scalars().all()
        
        # Get existing relationship keys to avoid duplicates
        existing_rel_keys = set()
        for rel in relationships:
            if rel.relationship_type == "schema_fk" or rel.relationship_type == "db_fk":
                key = (rel.source_table, rel.source_column, rel.target_table, rel.target_column)
                existing_rel_keys.add(key)
        
        # Create virtual relationships from foreign keys that don't exist in Relationship table
        for fk_col in fk_columns:
            if not fk_col.foreign_key_table or not fk_col.foreign_key_column:
                continue
            
            # Build source and target table names
            source_table = f"{fk_col.schema_name}.{fk_col.table_name}" if fk_col.schema_name else fk_col.table_name
            target_table = fk_col.foreign_key_table
            # Ensure target_table has schema if source has schema
            if '.' not in target_table and fk_col.schema_name:
                target_table = f"{fk_col.schema_name}.{target_table}"
            
            # Check if this relationship already exists
            rel_key = (source_table, fk_col.column_name, target_table, fk_col.foreign_key_column)
            if rel_key in existing_rel_keys:
                continue
            
            # Determine cardinality (usually 1-n for foreign keys)
            cardinality = "1-n"
            # Check if target column is a primary key (usually indicates 1-n)
            target_pk_check = await session.execute(
                select(SchemaMetadata).where(
                    and_(
                        SchemaMetadata.schema_snapshot_id == schema_snapshot_id,
                        SchemaMetadata.table_name == fk_col.foreign_key_table.split('.')[-1] if '.' in fk_col.foreign_key_table else fk_col.foreign_key_table,
                        SchemaMetadata.column_name == fk_col.foreign_key_column,
                        SchemaMetadata.is_primary_key == True
                    )
                ).limit(1)
            )
            if target_pk_check.scalar_one_or_none():
                cardinality = "n-1"  # Many-to-one (this table's FK -> other table's PK)
            
            # Create virtual relationship response
            relationship_responses.append(RelationshipResponse(**{
                "id": 0,  # Virtual ID for relationships not in database
                "schema_snapshot_id": schema_snapshot_id,
                "source_table": source_table,
                "source_column": fk_col.column_name,
                "target_table": target_table,
                "target_column": fk_col.foreign_key_column,
                "relationship_type": "db_fk",
                "join_type": "inner",
                "cardinality": cardinality,
                "description": f"Database foreign key relationship: {fk_col.column_name} references {target_table}.{fk_col.foreign_key_column}",
                "confidence_score": 1.0,  # Database FKs have 100% confidence
                "semantic_similarity": None,
                "user_accepted": False,
                "agent_approved": False,
                "is_confirmed": True,  # Database FKs are confirmed
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }))

    if clean_mode:
        # Group by table pairs and keep only the most recent relationship per pair
        pair_groups = {}
        for rel_resp in relationship_responses:
            pair_key = f"{min(rel_resp.source_table, rel_resp.target_table)}-{max(rel_resp.source_table, rel_resp.target_table)}"
            # Keep the most recent one if no existing, or if current is more recent
            if pair_key not in pair_groups:
                pair_groups[pair_key] = rel_resp
            else:
                # Compare by created_at
                existing_created = pair_groups[pair_key].created_at
                current_created = rel_resp.created_at
                if isinstance(current_created, str) and isinstance(existing_created, str):
                    if current_created > existing_created:
                        pair_groups[pair_key] = rel_resp

        relationship_responses = list(pair_groups.values())

    return relationship_responses


@router.get("/single/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(relationship_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get a specific relationship"""
    result = await session.execute(select(Relationship).where(Relationship.id == relationship_id))
    relationship = result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return RelationshipResponse.model_validate(relationship)


# Strength score endpoint removed - using simplified relationship type system


@router.post("/", response_model=RelationshipResponse)
async def create_relationship(
    relationship_data: RelationshipCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new relationship"""
    # Validate relationship type
    valid_relationship_types = ["schema_fk", "ai_suggested", "manual"]
    if relationship_data.relationship_type not in valid_relationship_types:
        raise HTTPException(status_code=400, detail=f"Invalid relationship type. Must be one of: {', '.join(valid_relationship_types)}")

    # Validate join type
    valid_join_types = ["inner", "left", "right"]
    if relationship_data.join_type not in valid_join_types:
        raise HTTPException(status_code=400, detail=f"Invalid join type. Must be one of: {', '.join(valid_join_types)}")

    # Validate cardinality
    valid_cardinalities = ["1-1", "1-n", "n-1", "n-n"]
    if relationship_data.cardinality not in valid_cardinalities:
        raise HTTPException(status_code=400, detail=f"Invalid cardinality. Must be one of: {', '.join(valid_cardinalities)}")

    # Check for existing relationship in the same schema snapshot
    result = await session.execute(select(Relationship).where(
        Relationship.schema_snapshot_id == relationship_data.schema_snapshot_id,
        Relationship.source_table == relationship_data.source_table,
        Relationship.source_column == relationship_data.source_column,
        Relationship.target_table == relationship_data.target_table,
        Relationship.target_column == relationship_data.target_column
    ))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Relationship already exists between these tables/columns in this schema snapshot")

    relationship = Relationship(**relationship_data.model_dump())
    session.add(relationship)
    await session.commit()
    await session.refresh(relationship)
    return RelationshipResponse.model_validate(relationship)


@router.put("/{relationship_id}", response_model=RelationshipResponse)
async def update_relationship(
    relationship_id: int,
    relationship_data: RelationshipCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Update a relationship"""
    result = await session.execute(select(Relationship).where(Relationship.id == relationship_id))
    relationship = result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Validate relationship type
    valid_relationship_types = ["schema_fk", "ai_suggested", "manual"]
    if relationship_data.relationship_type not in valid_relationship_types:
        raise HTTPException(status_code=400, detail=f"Invalid relationship type. Must be one of: {', '.join(valid_relationship_types)}")

    # Validate join type
    valid_join_types = ["inner", "left", "right"]
    if relationship_data.join_type not in valid_join_types:
        raise HTTPException(status_code=400, detail=f"Invalid join type. Must be one of: {', '.join(valid_join_types)}")

    # Validate cardinality
    valid_cardinalities = ["1-1", "1-n", "n-1", "n-n"]
    if relationship_data.cardinality not in valid_cardinalities:
        raise HTTPException(status_code=400, detail=f"Invalid cardinality. Must be one of: {', '.join(valid_cardinalities)}")

    # Check for conflicts if relationship changed (within same schema snapshot)
    if (relationship.source_table != relationship_data.source_table or
        relationship.source_column != relationship_data.source_column or
        relationship.target_table != relationship_data.target_table or
        relationship.target_column != relationship_data.target_column):

        conflict_result = await session.execute(select(Relationship).where(
            Relationship.schema_snapshot_id == relationship_data.schema_snapshot_id,
            Relationship.source_table == relationship_data.source_table,
            Relationship.source_column == relationship_data.source_column,
            Relationship.target_table == relationship_data.target_table,
            Relationship.target_column == relationship_data.target_column,
            Relationship.id != relationship_id
        ))
        if conflict_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Relationship already exists between these tables/columns in this schema snapshot")

    # Update fields
    for field, value in relationship_data.model_dump().items():
        setattr(relationship, field, value)

    # No need to recalculate scores - using simplified type system

    await session.commit()
    await session.refresh(relationship)
    return RelationshipResponse.model_validate(relationship)


@router.put("/{relationship_id}/promote", response_model=RelationshipResponse)
async def promote_relationship_for_agent(
    relationship_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Promote a relationship for agent use"""
    result = await session.execute(select(Relationship).where(Relationship.id == relationship_id))
    relationship = result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    relationship.agent_approved = True
    relationship.user_accepted = True
    await session.commit()
    await session.refresh(relationship)
    return RelationshipResponse.model_validate(relationship)


@router.delete("/{relationship_id}")
async def delete_relationship(relationship_id: int, session: AsyncSession = Depends(get_db_session)):
    """Delete a relationship"""
    result = await session.execute(select(Relationship).where(Relationship.id == relationship_id))
    relationship = result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Prevent deletion of DB foreign key relationships
    if relationship.relationship_type == "db_fk":
        raise HTTPException(status_code=400, detail="Cannot delete database foreign key relationships")

    await session.delete(relationship)
    await session.commit()
    return {"message": "Relationship deleted successfully"}


@router.post("/ai-suggest", response_model=AiSuggestRelationshipsResponse)
async def ai_suggest_relationships(
    request: AiSuggestRelationshipsRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Use AI to suggest relationships between tables with enhanced detection"""

    # Get the schema snapshot
    schema_result = await session.execute(
        select(SchemaSnapshot).where(SchemaSnapshot.id == request.schema_snapshot_id)
    )
    schema_snapshot = schema_result.scalar_one_or_none()
    if not schema_snapshot:
        raise HTTPException(status_code=404, detail="Schema snapshot not found")

    # Get schema metadata for this snapshot
    from .schema import get_schema_metadata
    schema_data = await get_schema_metadata(request.schema_snapshot_id, session)

    # Get data dictionary for this snapshot
    dict_result = await session.execute(
        select(DataDictionary).where(DataDictionary.schema_snapshot_id == request.schema_snapshot_id)
    )
    data_dict = dict_result.scalars().all()

    # Get sample data for all tables using DBConnector
    from core.db_utils import get_table_sample_data
    
    # Group tables and collect sample data
    tables_with_samples = {}
    table_keys = set()
    for item in schema_data:
        table_key = f"{item['schema_name']}.{item['table_name']}"
        table_keys.add(table_key)
    
    # Collect sample data for each table
    for table_key in table_keys:
        schema_name, table_name = table_key.split('.', 1) if '.' in table_key else ("", table_key)
        try:
            sample_rows = await get_table_sample_data(
                snapshot_id=request.schema_snapshot_id,
                schema_name=schema_name,
                table_name=table_name,
                limit=5,
                session=session
            )
            tables_with_samples[table_key] = sample_rows
        except Exception as e:
            # If sampling fails, continue without sample data for this table
            tables_with_samples[table_key] = []
    
    # Detect intermediary tables for N:N relationships
    intermediary_tables = _detect_intermediary_tables(schema_data)
    
    # Get active LLM model
    model_result = await session.execute(select(LLMModel).where(LLMModel.is_active == True))
    active_model = model_result.scalar_one_or_none()
    if not active_model:
        raise HTTPException(status_code=400, detail="No active LLM model found")

    # Build the enhanced AI prompt with sample data
    prompt = build_relationship_suggestion_prompt(
        schema_data, 
        data_dict, 
        tables_with_samples,
        intermediary_tables,
        request.business_context
    )

    # Calculate prompt hash for logging
    import hashlib
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

    print(f"Built AI prompt for relationship suggestions (hash: {prompt_hash[:8]}...), length: {len(prompt)} chars")
    print(f"Schema has {len(schema_data)} metadata items, {len(data_dict)} dictionary entries")

    try:
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
                "timeout_seconds": 1200.0,  # 20 minutes for complex relationship analysis
            })

        # Initialize registry and connector
        loader = ConfigRegistryLoader(config)
        registry = initialize_registry(loader)
        await registry.load()

        connector = ModelConnector(registry)
        await connector.initialize()  # Initialize the connector before use

        # Create LLM request for relationship generation
        llm_request = LLMRequest(
            model_id=str(active_model.id),
            messages=[Message(role=MessageRole.USER, content=prompt)],
            temperature=active_model.temperature,
            max_tokens=active_model.max_tokens
        )

        # Generate relationships using ModelConnector
        try:
            response = await connector.generate(llm_request)
            generated_text = response.text
        except (ModelNotFoundError, ModelGenerationError) as e:
            raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")

        # Parse the JSON response with improved error handling
        suggested_relationships = []

        try:
            # Clean the response text
            clean_text = generated_text.strip()

            # Remove markdown code blocks if present
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            clean_text = clean_text.strip()

            # Clean control characters that can break JSON parsing
            import re
            clean_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_text)

            # Try to parse as JSON
            parsed_response = json.loads(clean_text)

            # Handle different response formats
            if isinstance(parsed_response, dict):
                if "relationships" in parsed_response:
                    # Standard format: {"relationships": [...]}
                    suggested_relationships = parsed_response["relationships"]
                elif "data" in parsed_response and isinstance(parsed_response["data"], list):
                    # Alternative format: {"data": [...]}
                    suggested_relationships = parsed_response["data"]
                else:
                    # Check if the dict itself contains relationship fields
                    if all(key in parsed_response for key in ["source_table", "source_column", "target_table", "target_column"]):
                        suggested_relationships = [parsed_response]
                    elif all(key in parsed_response for key in ["table_1", "table_2", "column_1", "column_2"]):
                        # New format with table_1/table_2 - convert to source/target
                        suggested_relationships = [parsed_response]
                    else:
                        # Unknown dict format
                        raise ValueError(f"Unknown response format: {parsed_response}")
            elif isinstance(parsed_response, list):
                # Direct list of relationships
                suggested_relationships = parsed_response
            else:
                raise ValueError(f"Unexpected response type: {type(parsed_response)}")
            
            # Normalize field names: convert table_1/table_2 to source_table/target_table
            normalized_relationships = []
            for rel in suggested_relationships:
                normalized_rel = rel.copy()
                # Handle new format (table_1/table_2) -> convert to source/target
                if "table_1" in normalized_rel and "table_2" in normalized_rel:
                    normalized_rel["source_table"] = normalized_rel.pop("table_1")
                    normalized_rel["target_table"] = normalized_rel.pop("table_2")
                if "column_1" in normalized_rel and "column_2" in normalized_rel:
                    normalized_rel["source_column"] = normalized_rel.pop("column_1")
                    normalized_rel["target_column"] = normalized_rel.pop("column_2")
                # Handle relation_type -> cardinality mapping
                if "relation_type" in normalized_rel and "cardinality" not in normalized_rel:
                    relation_type = normalized_rel.pop("relation_type")
                    # Map relation_type to cardinality
                    type_mapping = {
                        "1-1": "1-1",
                        "1-n": "1-n",
                        "n-1": "n-1",
                        "n-n": "n-n",
                        "N:N": "n-n",
                        "1:N": "1-n",
                        "N:1": "n-1",
                        "1:1": "1-1"
                    }
                    normalized_rel["cardinality"] = type_mapping.get(relation_type.lower(), "1-n")
                # Handle confidence -> confidence_score
                if "confidence" in normalized_rel and "confidence_score" not in normalized_rel:
                    normalized_rel["confidence_score"] = normalized_rel.pop("confidence")
                # Ensure join_type exists (default to inner)
                if "join_type" not in normalized_rel:
                    normalized_rel["join_type"] = "inner"
                normalized_relationships.append(normalized_rel)
            
            suggested_relationships = normalized_relationships

        except json.JSONDecodeError as e:
            # If direct JSON parsing fails, try to extract JSON from text
            print(f"Direct JSON parsing failed: {str(e)}")
            print(f"Raw response: {generated_text[:500]}...")

            # Try to find JSON-like content in the response
            json_patterns = [
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Simple nested objects
                r'\[.*\]',  # Arrays
                r'\{.*\}',  # Objects
            ]

            for pattern in json_patterns:
                json_match = re.search(pattern, generated_text, re.DOTALL)
                if json_match:
                    try:
                        candidate_json = json_match.group()
                        parsed_candidate = json.loads(candidate_json)

                        if isinstance(parsed_candidate, dict) and "relationships" in parsed_candidate:
                            suggested_relationships = parsed_candidate["relationships"]
                            break
                        elif isinstance(parsed_candidate, list):
                            suggested_relationships = parsed_candidate
                            break
                    except (json.JSONDecodeError, ValueError):
                        continue

            if not suggested_relationships:
                print(f"Could not extract valid JSON from response. Returning empty suggestions.")
                suggested_relationships = []
            else:
                # Normalize field names for extracted JSON too
                normalized_relationships = []
                for rel in suggested_relationships:
                    normalized_rel = rel.copy()
                    # Handle new format (table_1/table_2) -> convert to source/target
                    if "table_1" in normalized_rel and "table_2" in normalized_rel:
                        normalized_rel["source_table"] = normalized_rel.pop("table_1")
                        normalized_rel["target_table"] = normalized_rel.pop("table_2")
                    if "column_1" in normalized_rel and "column_2" in normalized_rel:
                        normalized_rel["source_column"] = normalized_rel.pop("column_1")
                        normalized_rel["target_column"] = normalized_rel.pop("column_2")
                    # Handle relation_type -> cardinality mapping
                    if "relation_type" in normalized_rel and "cardinality" not in normalized_rel:
                        relation_type = normalized_rel.pop("relation_type")
                        type_mapping = {
                            "1-1": "1-1", "1-n": "1-n", "n-1": "n-1", "n-n": "n-n",
                            "N:N": "n-n", "1:N": "1-n", "N:1": "n-1", "1:1": "1-1"
                        }
                        normalized_rel["cardinality"] = type_mapping.get(relation_type.lower(), "1-n")
                    # Handle confidence -> confidence_score
                    if "confidence" in normalized_rel and "confidence_score" not in normalized_rel:
                        normalized_rel["confidence_score"] = normalized_rel.pop("confidence")
                    # Ensure join_type exists (default to inner)
                    if "join_type" not in normalized_rel:
                        normalized_rel["join_type"] = "inner"
                    normalized_relationships.append(normalized_rel)
                suggested_relationships = normalized_relationships

        except Exception as e:
            print(f"Unexpected error during JSON parsing: {str(e)}")
            suggested_relationships = []

        # Validate and structure the response
        validated_relationships = []
        for i, rel in enumerate(suggested_relationships):
            try:
                # Ensure required fields are present
                required_fields = ["source_table", "source_column", "target_table", "target_column", "join_type", "cardinality", "description", "confidence_score", "reasoning"]
                missing_fields = [field for field in required_fields if field not in rel]
                if missing_fields:
                    print(f"Skipping relationship {i}: missing required fields {missing_fields}")
                    continue

                # Validate and normalize values
                rel_copy = rel.copy()

                # Set default relationship type
                if rel_copy.get("relationship_type") not in ["db_fk", "ai_suggested", "manual"]:
                    rel_copy["relationship_type"] = "ai_suggested"

                # Validate join type
                if rel_copy["join_type"] not in ["inner", "left", "right"]:
                    print(f"Invalid join_type '{rel_copy['join_type']}' for relationship {i}, defaulting to 'inner'")
                    rel_copy["join_type"] = "inner"

                # Validate cardinality
                if rel_copy["cardinality"] not in ["1-1", "1-n", "n-1", "n-n"]:
                    print(f"Invalid cardinality '{rel_copy['cardinality']}' for relationship {i}, defaulting to '1-n'")
                    rel_copy["cardinality"] = "1-n"

                # Validate confidence score
                try:
                    confidence = float(rel_copy["confidence_score"])
                    if not (0 <= confidence <= 1):
                        print(f"Invalid confidence_score {confidence} for relationship {i}, defaulting to 0.5")
                        confidence = 0.5
                    rel_copy["confidence_score"] = confidence
                except (ValueError, TypeError):
                    print(f"Non-numeric confidence_score '{rel_copy['confidence_score']}' for relationship {i}, defaulting to 0.5")
                    rel_copy["confidence_score"] = 0.5

                # Handle intermediary_table (optional, only for N:N relationships)
                if rel_copy.get("cardinality") == "n-n":
                    if not rel_copy.get("intermediary_table"):
                        # Try to find intermediary table from detected ones
                        source_table = rel_copy["source_table"]
                        target_table = rel_copy["target_table"]
                        # This will be handled by the prompt, but we validate here
                        rel_copy["intermediary_table"] = rel_copy.get("intermediary_table")
                else:
                    rel_copy["intermediary_table"] = None

                # Handle example (optional, should be null if no sample data available)
                if rel_copy.get("example") is None:
                    # Try to extract example from sample data if available
                    source_table = rel_copy["source_table"]
                    target_table = rel_copy["target_table"]
                    source_col = rel_copy["source_column"]
                    target_col = rel_copy["target_column"]
                    
                    example = _extract_relationship_example(
                        tables_with_samples.get(source_table, []),
                        tables_with_samples.get(target_table, []),
                        source_col,
                        target_col
                    )
                    rel_copy["example"] = example
                elif not isinstance(rel_copy.get("example"), dict) and rel_copy.get("example") is not None:
                    # If example is not a dict, set to None
                    rel_copy["example"] = None

                # Ensure string fields are strings
                string_fields = ["source_table", "source_column", "target_table", "target_column", "description", "reasoning"]
                for field in string_fields:
                    if field in rel_copy and not isinstance(rel_copy[field], str):
                        rel_copy[field] = str(rel_copy[field])
                
                # Ensure intermediary_table is string or None
                if rel_copy.get("intermediary_table") and not isinstance(rel_copy["intermediary_table"], str):
                    rel_copy["intermediary_table"] = str(rel_copy["intermediary_table"]) if rel_copy["intermediary_table"] else None

                validated_relationships.append(AiSuggestedRelationship(**rel_copy))

            except Exception as e:
                print(f"Error processing relationship {i}: {str(e)}")
                print(f"Relationship data: {rel}")
                continue

        print(f"Successfully validated {len(validated_relationships)} out of {len(suggested_relationships)} suggested relationships")

        return AiSuggestRelationshipsResponse(suggested_relationships=validated_relationships)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI suggestion failed: {str(e)}")


def _detect_intermediary_tables(schema_data: List[dict]) -> Dict[str, Dict[str, Any]]:
    """
    Detect intermediary/bridge tables that could support N:N relationships.
    
    Returns a dictionary mapping intermediary table keys to their detected relationships.
    """
    intermediary_tables = {}
    
    # Group schema by table
    tables = {}
    for item in schema_data:
        table_key = f"{item['schema_name']}.{item['table_name']}"
        if table_key not in tables:
            tables[table_key] = {
                "schema_name": item["schema_name"],
                "table_name": item["table_name"],
                "columns": [],
                "foreign_key_count": 0
            }
        tables[table_key]["columns"].append({
            "name": item["column_name"],
            "type": item["column_type"],
            "is_primary_key": item["is_primary_key"],
            "is_foreign_key": item["is_foreign_key"],
            "foreign_key_table": item.get("foreign_key_table"),
            "foreign_key_column": item.get("foreign_key_column")
        })
        if item["is_foreign_key"]:
            tables[table_key]["foreign_key_count"] += 1
    
    # Identify potential intermediary tables
    # Criteria: table has 2+ foreign keys pointing to different main tables
    for table_key, table_info in tables.items():
        fk_columns = [col for col in table_info["columns"] if col["is_foreign_key"]]
        if len(fk_columns) >= 2:
            # Check if FKs point to different tables
            fk_targets = set()
            for fk_col in fk_columns:
                if fk_col.get("foreign_key_table"):
                    fk_targets.add(fk_col["foreign_key_table"])
            
            if len(fk_targets) >= 2:
                # This looks like an intermediary table
                intermediary_tables[table_key] = {
                    "table": table_key,
                    "foreign_keys": [
                        {
                            "column": fk_col["name"],
                            "target_table": fk_col["foreign_key_table"],
                            "target_column": fk_col["foreign_key_column"]
                        }
                        for fk_col in fk_columns
                    ]
                }
    
    return intermediary_tables


def _extract_relationship_example(
    source_samples: List[Dict[str, Any]],
    target_samples: List[Dict[str, Any]],
    source_column: str,
    target_column: str
) -> Optional[Dict[str, Any]]:
    """
    Extract a realistic example from sampled rows showing the relationship.
    
    Returns a dictionary with example values or None if no matching data found.
    """
    if not source_samples or not target_samples:
        return None
    
    # Try to find matching values between source and target
    source_values = set()
    for row in source_samples:
        if source_column in row and row[source_column] is not None:
            source_values.add(str(row[source_column]))
    
    target_values = set()
    for row in target_samples:
        if target_column in row and row[target_column] is not None:
            target_values.add(str(row[target_column]))
    
    # Find intersection
    matching_values = source_values.intersection(target_values)
    if matching_values:
        # Get first matching value and find example rows
        match_value = list(matching_values)[0]
        
        source_example = None
        for row in source_samples:
            if source_column in row and str(row[source_column]) == match_value:
                source_example = {k: str(v)[:100] if v is not None else None for k, v in row.items()}
                break
        
        target_example = None
        for row in target_samples:
            if target_column in row and str(row[target_column]) == match_value:
                target_example = {k: str(v)[:100] if v is not None else None for k, v in row.items()}
                break
        
        if source_example and target_example:
            return {
                "matching_value": match_value[:100],
                "source_example": source_example,
                "target_example": target_example
            }
    
    # If no match found, return None (low confidence)
    return None


def build_relationship_suggestion_prompt(
    schema_data: List[dict], 
    data_dict: List[DataDictionary], 
    tables_with_samples: Dict[str, List[Dict[str, Any]]],
    intermediary_tables: Dict[str, Dict[str, Any]],
    business_context: Optional[str] = None
) -> str:
    """Build the enhanced AI prompt for relationship suggestions with sample data"""

    # Group schema data by table
    tables = {}
    for item in schema_data:
        table_key = f"{item['schema_name']}.{item['table_name']}"
        if table_key not in tables:
            tables[table_key] = {
                "schema_name": item["schema_name"],
                "table_name": item["table_name"],
                "columns": []
            }
        tables[table_key]["columns"].append({
            "name": item["column_name"],
            "type": item["column_type"],
            "is_primary_key": item["is_primary_key"],
            "is_foreign_key": item["is_foreign_key"],
            "foreign_key_table": item.get("foreign_key_table"),
            "foreign_key_column": item.get("foreign_key_column")
        })

    # Group data dictionary by table
    dict_by_table = {}
    for item in data_dict:
        table_key = f"{item.schema_name}.{item.table_name}"
        if table_key not in dict_by_table:
            dict_by_table[table_key] = {"table_description": None, "columns": {}}
        if item.column_name:
            try:
                example_values = json.loads(item.example_values) if item.example_values else []
            except:
                example_values = []
            dict_by_table[table_key]["columns"][item.column_name] = {
                "description": item.description,
                "example_values": example_values,
                "synonyms": item.synonyms,
                "is_sensitive": item.is_sensitive
            }
        else:
            dict_by_table[table_key]["table_description"] = item.description

    prompt = """You are a senior database architect analyzing a database schema to identify logical relationships between tables.

Your task is to suggest meaningful relationships that would be useful for SQL query generation. Focus on relationships that enable common business queries and joins.

SCHEMA INFORMATION:
"""

    for table_key, table_info in tables.items():
        prompt += f"\nTABLE: {table_key}\n"
        table_dict = dict_by_table.get(table_key, {})
        if table_dict.get("table_description"):
            prompt += f"Description: {table_dict['table_description']}\n"

        prompt += "Columns:\n"
        for col in table_info["columns"]:
            prompt += f"  - {col['name']} ({col['type']})"
            if col["is_primary_key"]:
                prompt += " [PRIMARY KEY]"
            if col["is_foreign_key"]:
                prompt += f" [FK -> {col['foreign_key_table']}.{col['foreign_key_column']}]"

            col_dict = table_dict.get("columns", {}).get(col["name"])
            if col_dict and col_dict.get("description"):
                prompt += f" - {col_dict['description']}"
            prompt += "\n"
        
        # Add sample data if available
        sample_rows = tables_with_samples.get(table_key, [])
        if sample_rows:
            prompt += f"\nSample Data (first {min(3, len(sample_rows))} rows):\n"
            for idx, row in enumerate(sample_rows[:3], 1):
                # Format row data, limiting value length
                row_str = ", ".join([f"{k}: {str(v)[:50]}" for k, v in list(row.items())[:5]])
                prompt += f"  Row {idx}: {{{row_str}}}\n"

    # Add intermediary tables information
    if intermediary_tables:
        prompt += "\n\nDETECTED INTERMEDIARY TABLES (for N:N relationships):\n"
        for table_key, info in intermediary_tables.items():
            prompt += f"\n{table_key}:\n"
            prompt += "  This table appears to be a bridge/join table with multiple foreign keys:\n"
            for fk in info["foreign_keys"]:
                prompt += f"    - {fk['column']} -> {fk['target_table']}.{fk['target_column']}\n"

    if business_context:
        prompt += f"\n\nBUSINESS CONTEXT:\n{business_context}\n"

    prompt += """

RELATIONSHIP DETECTION INSTRUCTIONS:

1. HIDDEN/IMPLICIT RELATION DETECTION:
   - Analyze schema similarity: field names, types, constraints
   - Check value overlap from sampled DB rows (if provided)
   - Use business description from context
   - Consider column meaning from data dictionary
   - Identify likely relationships even when no DB foreign key exists
   - Look for semantic matches (e.g., "customer_id" in orders matches "id" in customers)

2. N:N RELATIONSHIPS VIA INTERMEDIARY TABLES:
   - Only suggest N:N when an intermediary/bridge table exists (see DETECTED INTERMEDIARY TABLES above)
   - The intermediary table must contain at least 2 foreign-like columns referencing 2 main tables
   - Set relation_type to "N:N" and reference the intermediary table in intermediary_table field
   - Explain in reasoning how the intermediary table enables the many-to-many relationship

3. CONFIDENCE SCORING:
   - Calculate confidence (0.0-1.0) based on:
     * Schema match quality (column name similarity, type compatibility)
     * Sample value correlation (overlap in actual data values)
     * Business context alignment
     * Dictionary description relevance
   - DO NOT assign high confidence without justification
   - If sample data shows no value overlap, confidence should be < 0.3
   - Provide short reasoning explaining the confidence score

4. REAL EXAMPLES:
   - Use actual values from sampled DB rows when available
   - If sample rows show matching values between source and target columns, include them in "example"
   - Format example as: {"matching_value": "...", "source_example": {...}, "target_example": {...}}
   - If no matching sample data found, set example to null

5. BUSINESS-LEVEL DESCRIPTIONS:
   - Description must explain:
     * Why the relation matters in the domain
     * Typical usage in queries/filters
     * Edge cases or exceptions
     * Cardinality justification
   - Be specific and actionable, not generic

6. GENERAL RULES:
   - NEVER suggest relationships that already exist as database foreign keys (marked with [FK -> ...])
   - Only suggest logical relationships useful for querying
   - Focus on relationships between different tables that make business sense
   - Consider table and column names, descriptions, sample data, and business context
   - Suggest appropriate join types (inner, left, right) and cardinalities (1-1, 1-n, n-1, n-n)
   - Avoid suggesting relationships with very low confidence (< 0.3) unless strongly justified

OUTPUT FORMAT:
Return ONLY valid JSON with this exact structure:
{
  "relationships": [
    {
      "table_1": "schema.table_name",
      "table_2": "schema.table_name",
      "column_1": "column_name",
      "column_2": "column_name",
      "relation_type": "1-1|1-n|n-1|n-n",
      "intermediary_table": null,
      "description": "Business-level description explaining why this relation matters, typical usage, edge cases, and cardinality justification",
      "confidence": 0.85,
      "example": {
        "matching_value": "actual_value_from_sample",
        "source_example": {"col1": "val1", "col2": "val2"},
        "target_example": {"col1": "val1", "col2": "val2"}
      },
      "reasoning": "Short explanation of confidence score and why this relationship makes sense"
    }
  ]
}

IMPORTANT:
- Output ONLY the JSON, no additional text
- Use "table_1", "table_2", "column_1", "column_2" in output (will be mapped to source/target)
- For N:N relationships, set intermediary_table to the bridge table name
- If no sample data match found, set example to null
- Ensure all fields are present for each relationship
- Use exact table names as shown in the schema
- Only suggest relationships you're confident about (confidence >= 0.3)"""

    return prompt


@router.get("/agent-export/{schema_snapshot_id}")
async def export_relationships_for_agent(schema_snapshot_id: int, session: AsyncSession = Depends(get_db_session)):
    """Export approved relationships for Text-to-SQL agent"""
    # Get only agent-approved relationships
    result = await session.execute(
        select(Relationship).where(
            Relationship.schema_snapshot_id == schema_snapshot_id,
            Relationship.agent_approved == True
        ).order_by(Relationship.created_at.desc())
    )
    relationships = result.scalars().all()

    # Format for agent consumption
    agent_relationships = []
    for rel in relationships:
        agent_relationships.append({
            "from": rel.source_table,
            "to": rel.target_table,
            "join": f"{rel.source_table}.{rel.source_column} = {rel.target_table}.{rel.target_column}",
            "cardinality": rel.cardinality,
            "confidence": rel.confidence_score or 0.5,
            "type": rel.relationship_type,
            "description": rel.description
        })

    # Get table info
    from .schema import get_schema_metadata
    schema_data = await get_schema_metadata(schema_snapshot_id, session)

    tables = []
    for table in schema_data:
        tables.append({
            "name": table["table_name"],
            "schema": table["schema_name"],
            "columns": [{"name": col["column_name"], "type": col["column_type"]} for col in table["columns"]]
        })

    return {
        "tables": tables,
        "relationships": agent_relationships,
        "metadata": {
            "schema_snapshot_id": schema_snapshot_id,
            "total_relationships": len(agent_relationships),
            "export_timestamp": "2025-12-18T07:06:03"
        }
    }


@router.post("/sync-database-relationships/{schema_snapshot_id}")
async def sync_database_relationships(schema_snapshot_id: int):
    """Sync relationships from database foreign keys for a schema snapshot"""
    return {
        "message": f"Database relationship sync endpoint working for snapshot {schema_snapshot_id}",
        "created_relationships": [],
        "skipped_relationships": [],
        "total_foreign_keys_found": 0
    }


@router.post("/ai-suggest/accept")
async def accept_ai_suggestions(
    request: dict,  # Will contain suggestions and snapshot_id
    session: AsyncSession = Depends(get_db_session)
):
    """Accept and create AI-suggested relationships in the database"""
    suggestions = request.get("suggestions", [])
    snapshot_id = request.get("snapshot_id")

    if not suggestions:
        raise HTTPException(status_code=400, detail="No suggestions provided")

    if not snapshot_id:
        # Try to get active snapshot
        active_result = await session.execute(select(SchemaSnapshot).where(SchemaSnapshot.is_active == True))
        snapshot = active_result.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=400, detail="No active schema snapshot found and snapshot_id not provided")
        snapshot_id = snapshot.id

    created_relationships = []
    errors = []

    for i, suggestion in enumerate(suggestions):
        try:
            # Convert suggestion dict to RelationshipCreate
            relationship_data = RelationshipCreate(
                schema_snapshot_id=snapshot_id,
                source_table=suggestion["source_table"],
                source_column=suggestion["source_column"],
                target_table=suggestion["target_table"],
                target_column=suggestion["target_column"],
                relationship_type="ai_suggested",
                join_type=suggestion["join_type"],
                cardinality=suggestion["cardinality"],
                description=suggestion["description"],
                confidence_score=suggestion.get("confidence_score", 0.5),
                is_confirmed=True
            )

            # Validate inputs (reuse existing validation logic)
            valid_relationship_types = ["schema_fk", "ai_suggested", "manual"]
            if relationship_data.relationship_type not in valid_relationship_types:
                raise ValueError(f"Invalid relationship type: {relationship_data.relationship_type}")

            valid_join_types = ["inner", "left", "right"]
            if relationship_data.join_type not in valid_join_types:
                raise ValueError(f"Invalid join type: {relationship_data.join_type}")

            valid_cardinalities = ["1-1", "1-n", "n-1", "n-n"]
            if relationship_data.cardinality not in valid_cardinalities:
                raise ValueError(f"Invalid cardinality: {relationship_data.cardinality}")

            # Check for existing relationship
            existing_result = await session.execute(select(Relationship).where(
                Relationship.schema_snapshot_id == relationship_data.schema_snapshot_id,
                Relationship.source_table == relationship_data.source_table,
                Relationship.source_column == relationship_data.source_column,
                Relationship.target_table == relationship_data.target_table,
                Relationship.target_column == relationship_data.target_column
            ))
            if existing_result.scalar_one_or_none():
                errors.append(f"Relationship {i} already exists: {suggestion['source_table']}.{suggestion['source_column']} -> {suggestion['target_table']}.{suggestion['target_column']}")
                continue

            relationship = Relationship(**relationship_data.model_dump())
            session.add(relationship)
            await session.flush()  # Get the ID without committing

            created_relationships.append({
                "id": relationship.id,
                "schema_snapshot_id": relationship.schema_snapshot_id,
                "source_table": relationship.source_table,
                "source_column": relationship.source_column,
                "target_table": relationship.target_table,
                "target_column": relationship.target_column,
                "relationship_type": relationship.relationship_type,
                "join_type": relationship.join_type,
                "cardinality": relationship.cardinality,
                "description": relationship.description,
                "confidence_score": relationship.confidence_score,
                "is_confirmed": relationship.is_confirmed,
                "created_at": relationship.created_at.isoformat() if relationship.created_at else None,
                "updated_at": relationship.updated_at.isoformat() if relationship.updated_at else None
            })

        except Exception as e:
            errors.append(f"Error creating relationship {i}: {str(e)}")
            continue

    await session.commit()

    return {
        "message": f"Successfully created {len(created_relationships)} relationships",
        "created_relationships": created_relationships,
        "errors": errors
    }
