from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
import json
import io
import csv
from datetime import datetime

from .db_models import UseCase, SchemaSnapshot, get_db_session
from loguru import logger
from core.config import LOG_ENCODING, LOG_ERROR_HANDLING

use_cases_router = APIRouter()


def safe_json_parse(value: Optional[str], field_name: str = "unknown") -> Optional[List]:
    """
    Safely parse JSON string to list, with fallback to single-item list.

    Args:
        value: JSON string to parse
        field_name: Name of the field for logging purposes

    Returns:
        List of items or None if parsing fails
    """
    if not value:
        return None

    if isinstance(value, list):
        return value

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        else:
            # If it's not a list, wrap it in a list
            return [parsed]
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON for {field_name}: {e}, value: {value[:100]}...")
        # Try to split by comma if it looks like a comma-separated string
        if isinstance(value, str) and ',' in value:
            try:
                return [item.strip() for item in value.split(',') if item.strip()]
            except Exception:
                pass
        # Fallback: return as single-item list
        return [value]

class UseCaseCreate(BaseModel):
    name: str
    business_goal: str
    example_questions: Optional[List[str]] = None
    output_style: str
    is_ai_generated: bool = False
    generation_log_id: Optional[int] = None
    generation_version: Optional[int] = None
    business_context: Optional[str] = None
    primary_audience: Optional[List[str]] = None
    typical_questions_wizard: Optional[List[str]] = None
    output_preference: Optional[str] = None
    dictionary_version: Optional[int] = None
    relationships_version: Optional[int] = None

class UseCaseResponse(BaseModel):
    id: int
    name: str
    business_goal: str
    example_questions: Optional[List[str]]
    example_queries: Optional[List[str]]
    output_style: str
    is_ai_generated: Optional[bool] = False
    generation_log_id: Optional[int] = None
    generation_version: Optional[int] = None
    business_context: Optional[str] = None
    primary_audience: Optional[List[str]] = None
    typical_questions_wizard: Optional[List[str]] = None
    output_preference: Optional[str] = None
    dictionary_version: Optional[int] = None
    relationships_version: Optional[int] = None

@use_cases_router.get("/", response_model=List[UseCaseResponse])
async def get_use_cases(
    snapshot_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session)
):
    """Get all use cases, optionally filtered by snapshot_id"""
    # TEMPORARY FIX: Return all use cases for now (they exist but don't have correct snapshot_id)
    print(f"DEBUG: snapshot_id = {snapshot_id}, type = {type(snapshot_id)}")
    query = select(UseCase).order_by(UseCase.created_at.desc())

    result = await session.execute(query)
    use_cases = result.scalars().all()

    # Log for debugging
    print(f"Found {len(use_cases)} use cases for snapshot_id: {snapshot_id}")

    response = []
    for uc in use_cases:
        example_questions = safe_json_parse(uc.example_questions, "example_questions")
        example_queries = safe_json_parse(uc.example_queries, "example_queries")
        primary_audience = safe_json_parse(uc.primary_audience, "primary_audience")
        typical_questions_wizard = safe_json_parse(uc.typical_questions, "typical_questions")

        response.append(UseCaseResponse(
            id=uc.id,
            name=uc.name,
            business_goal=uc.business_goal,
            example_questions=example_questions,
            example_queries=example_queries,
            output_style=uc.output_style,
            is_ai_generated=uc.is_ai_generated,
            generation_log_id=uc.generation_log_id,
            generation_version=uc.generation_version,
            business_context=uc.business_context,
            primary_audience=primary_audience,
            typical_questions_wizard=typical_questions_wizard,
            output_preference=uc.output_preference,
            dictionary_version=uc.dictionary_version,
            relationships_version=uc.relationships_version
        ))

    return response

# IMPORTANT: This route must be defined BEFORE /{use_case_id} route
# to avoid FastAPI matching "export" as a use_case_id
# Using /export/csv to ensure it doesn't conflict with /{use_case_id}
@use_cases_router.get("/export/csv")
async def export_use_cases_csv(
    snapshot_id: Optional[int] = Query(None, description="Schema snapshot ID (optional, exports all if not provided)"),
    session: AsyncSession = Depends(get_db_session)
):
    """Export use cases to CSV format"""
    try:
        # Get all use cases, optionally filtered by snapshot_id
        query = select(UseCase).order_by(UseCase.created_at.desc())
        if snapshot_id:
            query = query.where(UseCase.schema_snapshot_id == snapshot_id)
        
        result = await session.execute(query)
        use_cases = result.scalars().all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID",
            "Name",
            "Business Goal",
            "Example Questions",
            "Example Queries",
            "Output Style",
            "Is AI Generated",
            "Business Context",
            "Primary Audience",
            "Typical Questions (Wizard)",
            "Output Preference",
            "Schema Snapshot ID",
            "Generation Log ID",
            "Generation Version",
            "Dictionary Version",
            "Relationships Version",
            "Created At",
            "Updated At"
        ])
        
        # Write data rows
        for uc in use_cases:
            # Parse JSON fields
            example_questions = safe_json_parse(uc.example_questions, "example_questions")
            example_queries = safe_json_parse(uc.example_queries, "example_queries")
            primary_audience = safe_json_parse(uc.primary_audience, "primary_audience")
            typical_questions = safe_json_parse(uc.typical_questions, "typical_questions")
            
            # Format JSON arrays as semicolon-separated strings
            example_questions_str = "; ".join(str(q) for q in (example_questions or [])) if example_questions else ""
            example_queries_str = "; ".join(str(q) for q in (example_queries or [])) if example_queries else ""
            primary_audience_str = "; ".join(str(a) for a in (primary_audience or [])) if primary_audience else ""
            typical_questions_str = "; ".join(str(t) for t in (typical_questions or [])) if typical_questions else ""
            
            # Format dates
            created_at_str = uc.created_at.isoformat() if uc.created_at else ""
            updated_at_str = uc.updated_at.isoformat() if uc.updated_at else ""
            
            writer.writerow([
                uc.id,
                uc.name or "",
                uc.business_goal or "",
                example_questions_str,
                example_queries_str,
                uc.output_style or "",
                "Yes" if uc.is_ai_generated else "No",
                uc.business_context or "",
                primary_audience_str,
                typical_questions_str,
                uc.output_preference or "",
                uc.schema_snapshot_id,
                uc.generation_log_id or "",
                uc.generation_version or "",
                uc.dictionary_version or "",
                uc.relationships_version or "",
                created_at_str,
                updated_at_str
            ])
        
        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Get snapshot name for filename (if snapshot_id provided)
        filename_prefix = "use_cases"
        if snapshot_id:
            snapshot_result = await session.execute(
                select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
            )
            snapshot = snapshot_result.scalar_one_or_none()
            if snapshot and snapshot.name:
                snapshot_name = snapshot.name
                # Clean filename (remove invalid characters)
                safe_filename = "".join(c for c in snapshot_name if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_filename = safe_filename.replace(' ', '_')
                # Remove trailing underscores
                safe_filename = safe_filename.rstrip('_')
                if safe_filename:
                    filename_prefix = f"use_cases_{safe_filename}"
        
        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        # Ensure filename doesn't end with underscore
        filename = filename.rstrip('_')
        if not filename.endswith('.csv'):
            filename = filename.rstrip('_') + '.csv'
        
        # Return CSV file
        return Response(
            content=csv_content.encode('utf-8-sig'),  # UTF-8 with BOM for Excel compatibility
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            logger.error(f"Failed to export use cases: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Failed to export use cases: {error_msg}")
        except Exception as log_error:
            logger.error(f"Failed to export use cases: [Encoding error: {log_error}]")
            raise HTTPException(status_code=500, detail="Failed to export use cases")

@use_cases_router.get("/{use_case_id}", response_model=UseCaseResponse)
async def get_use_case(use_case_id: int, session: AsyncSession = Depends(get_db_session)):
    """Get a specific use case"""
    result = await session.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    example_questions = safe_json_parse(use_case.example_questions, "example_questions")
    example_queries = safe_json_parse(use_case.example_queries, "example_queries")
    primary_audience = safe_json_parse(use_case.primary_audience, "primary_audience")
    typical_questions_wizard = safe_json_parse(use_case.typical_questions, "typical_questions")

    return UseCaseResponse(
        id=use_case.id,
        name=use_case.name,
        business_goal=use_case.business_goal,
        example_questions=example_questions,
        example_queries=example_queries,
        output_style=use_case.output_style,
        is_ai_generated=use_case.is_ai_generated,
        generation_log_id=use_case.generation_log_id,
        generation_version=use_case.generation_version,
        business_context=use_case.business_context,
        primary_audience=primary_audience,
        typical_questions_wizard=typical_questions_wizard,
        output_preference=use_case.output_preference,
        dictionary_version=use_case.dictionary_version,
        relationships_version=use_case.relationships_version
    )

@use_cases_router.put("/{use_case_id}", response_model=UseCaseResponse)
async def update_use_case(
    use_case_id: int,
    use_case_data: dict,  # Using dict instead of Pydantic model
    session: AsyncSession = Depends(get_db_session)
):
    """Update a use case"""
    result = await session.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    # Extract data from dict
    name = use_case_data.get("name", use_case.name)
    business_goal = use_case_data.get("business_goal", use_case.business_goal)
    output_style = use_case_data.get("output_style", use_case.output_style)
    example_questions = use_case_data.get("example_questions")
    example_queries = use_case_data.get("example_queries")

    # Validate that questions and queries have matching counts if both are provided
    if example_questions is not None and example_queries is not None:
        if len(example_questions) != len(example_queries):
            raise HTTPException(
                status_code=400,
                detail=f"Number of example questions ({len(example_questions)}) must match number of example queries ({len(example_queries)})"
            )

    # Validate output style
    valid_styles = ["numeric", "summary", "analytical"]
    if output_style not in valid_styles:
        raise HTTPException(status_code=400, detail=f"Invalid output style. Must be one of: {', '.join(valid_styles)}")

    # Check name uniqueness if changed
    if name != use_case.name:
        name_result = await session.execute(select(UseCase).where(UseCase.name == name))
        if name_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Use case with this name already exists")

    # Convert JSON fields to strings
    example_questions_json = None
    if use_case_data.get("example_questions"):
        example_questions_json = json.dumps(use_case_data["example_questions"])

    example_queries_json = None
    if use_case_data.get("example_queries"):
        example_queries_json = json.dumps(use_case_data["example_queries"])

    primary_audience_json = None
    if use_case_data.get("primary_audience"):
        primary_audience_json = json.dumps(use_case_data["primary_audience"])

    typical_questions_json = None
    if use_case_data.get("typical_questions_wizard"):
        typical_questions_json = json.dumps(use_case_data["typical_questions_wizard"])

    use_case.name = name
    use_case.business_goal = business_goal
    use_case.example_questions = example_questions_json
    use_case.example_queries = example_queries_json
    use_case.output_style = output_style
    use_case.is_ai_generated = use_case_data.get("is_ai_generated", use_case.is_ai_generated)
    use_case.generation_log_id = use_case_data.get("generation_log_id", use_case.generation_log_id)
    use_case.generation_version = use_case_data.get("generation_version", use_case.generation_version)
    use_case.business_context = use_case_data.get("business_context", use_case.business_context)
    use_case.primary_audience = primary_audience_json
    use_case.typical_questions = typical_questions_json
    use_case.output_preference = use_case_data.get("output_preference", use_case.output_preference)
    use_case.dictionary_version = use_case_data.get("dictionary_version", use_case.dictionary_version)
    use_case.relationships_version = use_case_data.get("relationships_version", use_case.relationships_version)

    await session.commit()
    await session.refresh(use_case)

    return UseCaseResponse(
        id=use_case.id,
        name=use_case.name,
        business_goal=use_case.business_goal,
        example_questions=use_case_data.get("example_questions"),
        output_style=use_case.output_style,
        is_ai_generated=use_case.is_ai_generated,
        generation_log_id=use_case.generation_log_id,
        generation_version=use_case.generation_version,
        business_context=use_case.business_context,
        primary_audience=use_case_data.get("primary_audience"),
        typical_questions_wizard=use_case_data.get("typical_questions_wizard"),
        output_preference=use_case.output_preference,
        dictionary_version=use_case.dictionary_version,
        relationships_version=use_case.relationships_version
    )

@use_cases_router.delete("/{use_case_id}")
async def delete_use_case(use_case_id: int, session: AsyncSession = Depends(get_db_session)):
    """Delete a use case"""
    result = await session.execute(select(UseCase).where(UseCase.id == use_case_id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="Use case not found")

    await session.delete(use_case)
    await session.commit()
    return {"message": "Use case deleted successfully"}

@use_cases_router.post("/", response_model=UseCaseResponse)
async def create_use_case(
    use_case_data: dict  # Using dict instead of Pydantic model due to router parsing issue
):
    """Create a new use case"""
    # Manual validation since we're using dict
    name = use_case_data.get("name")
    business_goal = use_case_data.get("business_goal")
    output_style = use_case_data.get("output_style", "summary")
    example_questions = use_case_data.get("example_questions", [])
    example_queries = use_case_data.get("example_queries", [])

    if not name or not business_goal:
        raise HTTPException(status_code=400, detail="name and business_goal are required")

    # Validate that questions and queries have matching counts and are paired correctly
    if len(example_questions) != len(example_queries):
        raise HTTPException(
            status_code=400,
            detail=f"Number of example questions ({len(example_questions)}) must match number of example queries ({len(example_queries)}). Each question must have a corresponding query at the same index."
        )
    
    # Ensure all pairs are valid (both question and query exist)
    valid_pairs = []
    for i in range(len(example_questions)):
        q = example_questions[i] if i < len(example_questions) else None
        query = example_queries[i] if i < len(example_queries) else None
        
        # Only add if both exist
        if q and query:
            valid_pairs.append({
                "question": q,
                "query": query
            })
        else:
            # Log warning but continue
            logger.warning(f"[USECASE_CREATE] Skipping pair at index {i}: question={bool(q)}, query={bool(query)}")
    
    # Update lists with valid pairs only (maintaining order)
    if valid_pairs:
        example_questions = [pair["question"] for pair in valid_pairs]
        example_queries = [pair["query"] for pair in valid_pairs]
    else:
        raise HTTPException(
            status_code=400,
            detail="No valid question-query pairs found. Each question must have a corresponding query."
        )

    # Validate output style
    valid_styles = ["numeric", "summary", "analytical"]
    if output_style not in valid_styles:
        raise HTTPException(status_code=400, detail=f"Invalid output style. Must be one of: {', '.join(valid_styles)}")

    # Get session manually to avoid dependency injection issues
    from .db_models import async_session
    async with async_session() as session:
        # Check for existing use case name
        from sqlalchemy import select
        result = await session.execute(select(UseCase).where(UseCase.name == name))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Use case with this name already exists")

        # Convert JSON fields to strings (using validated pairs)
        # Note: example_questions and example_queries have been validated and paired above
        example_questions_json = json.dumps(example_questions, ensure_ascii=False)
        example_queries_json = json.dumps(example_queries, ensure_ascii=False)

        primary_audience_json = None
        if use_case_data.get("primary_audience"):
            primary_audience_json = json.dumps(use_case_data["primary_audience"])

        typical_questions_json = None
        if use_case_data.get("typical_questions_wizard"):
            typical_questions_json = json.dumps(use_case_data["typical_questions_wizard"])

        use_case = UseCase(
            schema_snapshot_id=1,  # Default snapshot for manual creation
            name=name,
            business_goal=business_goal,
            example_questions=example_questions_json,
            example_queries=example_queries_json,
            output_style=output_style,
            is_ai_generated=use_case_data.get("is_ai_generated", False),
            generation_log_id=use_case_data.get("generation_log_id"),
            generation_version=use_case_data.get("generation_version"),
            business_context=use_case_data.get("business_context"),
            primary_audience=primary_audience_json,
            typical_questions=typical_questions_json,
            output_preference=use_case_data.get("output_preference"),
            dictionary_version=use_case_data.get("dictionary_version"),
            relationships_version=use_case_data.get("relationships_version")
        )

        session.add(use_case)
        await session.commit()
        await session.refresh(use_case)

        return UseCaseResponse(
            id=use_case.id,
            name=use_case.name,
            business_goal=use_case.business_goal,
            example_questions=use_case_data.get("example_questions"),
            example_queries=use_case_data.get("example_queries"),
            output_style=use_case.output_style,
            is_ai_generated=use_case.is_ai_generated,
            generation_log_id=use_case.generation_log_id,
            generation_version=use_case.generation_version,
            business_context=use_case.business_context,
            primary_audience=use_case_data.get("primary_audience"),
            typical_questions_wizard=use_case_data.get("typical_questions_wizard"),
            output_preference=use_case.output_preference,
            dictionary_version=use_case.dictionary_version,
            relationships_version=use_case.relationships_version
        )


# Export the router for main.py
router = use_cases_router