"""
Use Case Maturation API

Endpoints for analyzing and optimizing use case maturity
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json
from loguru import logger

from .db_models import UseCase, UseCaseVersion, get_db_session
from services.use_case_maturation import (
    use_case_maturation_service,
    MaturityAnalysis,
    OptimizedUseCase
)
from core.config import LOG_ENCODING, LOG_ERROR_HANDLING

router = APIRouter()


# Request/Response Models
class MaturityAnalysisResponse(BaseModel):
    """Response model for maturity analysis"""
    use_case_id: int
    current_dict_version: Optional[int]
    current_rel_version: Optional[int]
    latest_dict_version: int
    latest_rel_version: int
    is_dict_outdated: bool
    is_rel_outdated: bool
    maturity_score: float
    recommendations: List[str]


class OptimizationOptions(BaseModel):
    """Options for use case optimization"""
    language: str = "persian"
    create_version: bool = True
    update_original: bool = False


class OptimizedUseCaseResponse(BaseModel):
    """Response model for optimized use case"""
    use_case_id: int
    optimized_name: str
    optimized_description: str
    optimized_questions: List[str]
    optimized_queries: List[str]
    improvements: List[str]
    maturity_score_before: float
    maturity_score_after: float
    new_version_id: Optional[int] = None


class BatchOptimizeRequest(BaseModel):
    """Request for batch optimization"""
    use_case_ids: List[int]
    language: str = "persian"
    create_versions: bool = True


class BatchOptimizeResponse(BaseModel):
    """Response for batch optimization"""
    results: List[Dict[str, Any]]
    total_optimized: int
    total_failed: int


class AutoMatureRequest(BaseModel):
    """Request for auto-maturation"""
    snapshot_id: int
    language: str = "persian"


# Endpoints

@router.get("/use-cases/{use_case_id}/analyze-maturity", response_model=MaturityAnalysisResponse)
async def analyze_use_case_maturity(
    use_case_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Analyze use case maturity and return improvement recommendations
    
    This endpoint analyzes:
    - Whether dictionary/relationships versions are outdated
    - Current maturity score (0-1)
    - Specific recommendations for improvement
    """
    try:
        # Validate use case exists
        result = await session.execute(
            select(UseCase).where(UseCase.id == use_case_id)
        )
        use_case = result.scalar_one_or_none()
        if not use_case:
            raise HTTPException(status_code=404, detail="Use case not found")
        
        # Analyze maturity
        analysis = await use_case_maturation_service.analyze_maturity(
            use_case_id, session
        )
        
        return MaturityAnalysisResponse(
            use_case_id=analysis.use_case_id,
            current_dict_version=analysis.current_dict_version,
            current_rel_version=analysis.current_rel_version,
            latest_dict_version=analysis.latest_dict_version,
            latest_rel_version=analysis.latest_rel_version,
            is_dict_outdated=analysis.is_dict_outdated,
            is_rel_outdated=analysis.is_rel_outdated,
            maturity_score=analysis.maturity_score,
            recommendations=analysis.recommendations
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze use case maturity: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to analyze maturity: {error_msg}")
        except:
            raise HTTPException(status_code=500, detail="Failed to analyze use case maturity")


@router.post("/use-cases/{use_case_id}/optimize", response_model=OptimizedUseCaseResponse)
async def optimize_use_case(
    use_case_id: int,
    options: OptimizationOptions = Body(default=OptimizationOptions()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Optimize a use case using latest context (dictionary, relationships, schema)
    
    This endpoint:
    1. Loads latest dictionary, relationships, and schema
    2. Uses AI to optimize the use case
    3. Optionally creates a new version or updates the original
    """
    try:
        # Validate use case exists
        result = await session.execute(
            select(UseCase).where(UseCase.id == use_case_id)
        )
        use_case = result.scalar_one_or_none()
        if not use_case:
            raise HTTPException(status_code=404, detail="Use case not found")
        
        # Optimize use case
        optimized = await use_case_maturation_service.optimize_use_case(
            use_case_id, options.language, session
        )
        
        new_version_id = None
        
        if options.create_version or options.update_original:
            # Get latest versions
            latest_dict_version = await session.execute(
                select(func.count(UseCase.id)).where(
                    UseCase.schema_snapshot_id == use_case.schema_snapshot_id
                )
            )
            # Actually get dictionary count
            from .db_models import DataDictionary, Relationship
            dict_count = await session.execute(
                select(func.count(DataDictionary.id)).where(
                    DataDictionary.schema_snapshot_id == use_case.schema_snapshot_id
                )
            )
            latest_dict_version = dict_count.scalar() or 0
            
            rel_count = await session.execute(
                select(func.count(Relationship.id)).where(
                    Relationship.schema_snapshot_id == use_case.schema_snapshot_id
                )
            )
            latest_rel_version = rel_count.scalar() or 0
            
            if options.create_version:
                # Create new version
                version_result = await session.execute(
                    select(func.max(UseCaseVersion.version_number)).where(
                        UseCaseVersion.original_use_case_id == use_case_id
                    )
                )
                max_version = version_result.scalar() or 0
                next_version = max_version + 1
                
                new_version = UseCaseVersion(
                    original_use_case_id=use_case_id,
                    schema_snapshot_id=use_case.schema_snapshot_id,
                    version_number=next_version,
                    version_description="Optimized using latest dictionary and relationships",
                    name=optimized.optimized_name,
                    business_goal=optimized.optimized_description,
                    example_questions=json.dumps(optimized.optimized_questions, ensure_ascii=False),
                    example_queries=json.dumps(optimized.optimized_queries, ensure_ascii=False),
                    output_style=use_case.output_style,
                    is_ai_generated=True,
                    business_context=use_case.business_context,
                    primary_audience=use_case.primary_audience,
                    typical_questions=use_case.typical_questions,
                    output_preference=use_case.output_preference,
                    dictionary_version=latest_dict_version,
                    relationships_version=latest_rel_version
                )
                session.add(new_version)
                await session.flush()
                await session.refresh(new_version)
                new_version_id = new_version.id
                
            if options.update_original:
                # Update original use case
                use_case.name = optimized.optimized_name
                use_case.business_goal = optimized.optimized_description
                use_case.example_questions = json.dumps(optimized.optimized_questions, ensure_ascii=False)
                use_case.example_queries = json.dumps(optimized.optimized_queries, ensure_ascii=False)
                use_case.dictionary_version = latest_dict_version
                use_case.relationships_version = latest_rel_version
            
            await session.commit()
        
        return OptimizedUseCaseResponse(
            use_case_id=optimized.use_case_id,
            optimized_name=optimized.optimized_name,
            optimized_description=optimized.optimized_description,
            optimized_questions=optimized.optimized_questions,
            optimized_queries=optimized.optimized_queries,
            improvements=optimized.improvements,
            maturity_score_before=optimized.maturity_score_before,
            maturity_score_after=optimized.maturity_score_after,
            new_version_id=new_version_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to optimize use case: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to optimize use case: {error_msg}")
        except:
            raise HTTPException(status_code=500, detail="Failed to optimize use case")


@router.post("/use-cases/batch-optimize", response_model=BatchOptimizeResponse)
async def batch_optimize_use_cases(
    request: BatchOptimizeRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Optimize multiple use cases in batch
    
    Useful for optimizing all use cases in a snapshot at once
    """
    try:
        results = []
        optimized_count = 0
        failed_count = 0
        
        for use_case_id in request.use_case_ids:
            try:
                # Validate use case exists
                result = await session.execute(
                    select(UseCase).where(UseCase.id == use_case_id)
                )
                use_case = result.scalar_one_or_none()
                if not use_case:
                    results.append({
                        "use_case_id": use_case_id,
                        "status": "error",
                        "message": "Use case not found"
                    })
                    failed_count += 1
                    continue
                
                # Optimize
                optimized = await use_case_maturation_service.optimize_use_case(
                    use_case_id, request.language, session
                )
                
                # Create version if requested
                if request.create_versions:
                    from .db_models import DataDictionary, Relationship, UseCaseVersion
                    from sqlalchemy import func
                    
                    dict_count = await session.execute(
                        select(func.count(DataDictionary.id)).where(
                            DataDictionary.schema_snapshot_id == use_case.schema_snapshot_id
                        )
                    )
                    latest_dict_version = dict_count.scalar() or 0
                    
                    rel_count = await session.execute(
                        select(func.count(Relationship.id)).where(
                            Relationship.schema_snapshot_id == use_case.schema_snapshot_id
                        )
                    )
                    latest_rel_version = rel_count.scalar() or 0
                    
                    version_result = await session.execute(
                        select(func.max(UseCaseVersion.version_number)).where(
                            UseCaseVersion.original_use_case_id == use_case_id
                        )
                    )
                    max_version = version_result.scalar() or 0
                    next_version = max_version + 1
                    
                    new_version = UseCaseVersion(
                        original_use_case_id=use_case_id,
                        schema_snapshot_id=use_case.schema_snapshot_id,
                        version_number=next_version,
                        version_description="Batch optimized using latest context",
                        name=optimized.optimized_name,
                        business_goal=optimized.optimized_description,
                        example_questions=json.dumps(optimized.optimized_questions, ensure_ascii=False),
                        example_queries=json.dumps(optimized.optimized_queries, ensure_ascii=False),
                        output_style=use_case.output_style,
                        is_ai_generated=True,
                        business_context=use_case.business_context,
                        primary_audience=use_case.primary_audience,
                        typical_questions=use_case.typical_questions,
                        output_preference=use_case.output_preference,
                        dictionary_version=latest_dict_version,
                        relationships_version=latest_rel_version
                    )
                    session.add(new_version)
                
                results.append({
                    "use_case_id": use_case_id,
                    "status": "success",
                    "maturity_score_before": optimized.maturity_score_before,
                    "maturity_score_after": optimized.maturity_score_after,
                    "improvements": optimized.improvements
                })
                optimized_count += 1
                
            except Exception as e:
                logger.error(f"Failed to optimize use case {use_case_id}: {e}")
                results.append({
                    "use_case_id": use_case_id,
                    "status": "error",
                    "message": str(e)
                })
                failed_count += 1
        
        await session.commit()
        
        return BatchOptimizeResponse(
            results=results,
            total_optimized=optimized_count,
            total_failed=failed_count
        )
    
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to batch optimize use cases: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to batch optimize: {error_msg}")
        except:
            raise HTTPException(status_code=500, detail="Failed to batch optimize use cases")


@router.post("/use-cases/auto-mature")
async def auto_mature_use_cases(
    request: AutoMatureRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Automatically mature all stale use cases in a snapshot
    
    This endpoint:
    1. Finds all use cases with outdated dictionary/relationships versions
    2. Optimizes them using latest context
    3. Creates new versions for each optimized use case
    """
    try:
        # Validate snapshot exists
        from .db_models import SchemaSnapshot
        snapshot_result = await session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.id == request.snapshot_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Schema snapshot not found")
        
        # Get latest versions
        from .db_models import DataDictionary, Relationship, UseCaseVersion
        from sqlalchemy import func
        
        dict_count = await session.execute(
            select(func.count(DataDictionary.id)).where(
                DataDictionary.schema_snapshot_id == request.snapshot_id
            )
        )
        latest_dict_version = dict_count.scalar() or 0
        
        rel_count = await session.execute(
            select(func.count(Relationship.id)).where(
                Relationship.schema_snapshot_id == request.snapshot_id
            )
        )
        latest_rel_version = rel_count.scalar() or 0
        
        # Get all use cases for snapshot
        use_cases_result = await session.execute(
            select(UseCase).where(UseCase.schema_snapshot_id == request.snapshot_id)
        )
        use_cases = use_cases_result.scalars().all()
        
        results = []
        for use_case in use_cases:
            try:
                # Analyze maturity
                analysis = await use_case_maturation_service.analyze_maturity(
                    use_case.id, session
                )
                
                # Only optimize if outdated
                if analysis.is_dict_outdated or analysis.is_rel_outdated or analysis.maturity_score < 0.7:
                    logger.info(f"[AUTO-MATURE] Optimizing use case {use_case.id}")
                    
                    # Optimize
                    optimized = await use_case_maturation_service.optimize_use_case(
                        use_case.id, request.language, session
                    )
                    
                    # Create version
                    version_result = await session.execute(
                        select(func.max(UseCaseVersion.version_number)).where(
                            UseCaseVersion.original_use_case_id == use_case.id
                        )
                    )
                    max_version = version_result.scalar() or 0
                    next_version = max_version + 1
                    
                    new_version = UseCaseVersion(
                        original_use_case_id=use_case.id,
                        schema_snapshot_id=use_case.schema_snapshot_id,
                        version_number=next_version,
                        version_description="Auto-matured using latest dictionary and relationships",
                        name=optimized.optimized_name,
                        business_goal=optimized.optimized_description,
                        example_questions=json.dumps(optimized.optimized_questions, ensure_ascii=False),
                        example_queries=json.dumps(optimized.optimized_queries, ensure_ascii=False),
                        output_style=use_case.output_style,
                        is_ai_generated=True,
                        business_context=use_case.business_context,
                        primary_audience=use_case.primary_audience,
                        typical_questions=use_case.typical_questions,
                        output_preference=use_case.output_preference,
                        dictionary_version=latest_dict_version,
                        relationships_version=latest_rel_version
                    )
                    session.add(new_version)
                    
                    results.append({
                        "use_case_id": use_case.id,
                        "use_case_name": use_case.name,
                        "optimized": True,
                        "maturity_score_before": optimized.maturity_score_before,
                        "maturity_score_after": optimized.maturity_score_after,
                        "improvements": optimized.improvements,
                        "new_version_id": new_version.id if new_version.id else None
                    })
                else:
                    results.append({
                        "use_case_id": use_case.id,
                        "use_case_name": use_case.name,
                        "optimized": False,
                        "reason": "Already up to date"
                    })
            except Exception as e:
                logger.error(f"[AUTO-MATURE] Failed to optimize use case {use_case.id}: {e}")
                results.append({
                    "use_case_id": use_case.id,
                    "use_case_name": use_case.name,
                    "optimized": False,
                    "error": str(e)
                })
        
        await session.commit()
        
        return {
            "snapshot_id": request.snapshot_id,
            "results": results,
            "total_processed": len(results),
            "total_optimized": sum(1 for r in results if r.get("optimized")),
            "total_skipped": sum(1 for r in results if not r.get("optimized"))
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to auto-mature use cases: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Failed to auto-mature: {error_msg}")
        except:
            raise HTTPException(status_code=500, detail="Failed to auto-mature use cases")

