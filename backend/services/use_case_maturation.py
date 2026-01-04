"""
Use Case Maturation Service

This service provides intelligent optimization and maturation of use cases
based on latest data dictionary, relationships, and schema information.
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import json
from loguru import logger

from api.db_models import (
    UseCase, UseCaseVersion, SchemaSnapshot, SchemaMetadata,
    DataDictionary, Relationship, LLMModel
)
from api.smart_use_case_builder import (
    _minify_schema_metadata,
    _format_data_dictionary,
    _format_relationships
)
from services.db_connector_utils import create_db_connector_for_snapshot
from services.llm_helper import generate_with_llm_service
from llm.schemas import LLMRequest, Message, MessageRole


class MaturityAnalysis:
    """Analysis result for use case maturity"""
    def __init__(
        self,
        use_case_id: int,
        current_dict_version: Optional[int],
        current_rel_version: Optional[int],
        latest_dict_version: int,
        latest_rel_version: int,
        is_dict_outdated: bool,
        is_rel_outdated: bool,
        maturity_score: float,
        recommendations: List[str]
    ):
        self.use_case_id = use_case_id
        self.current_dict_version = current_dict_version
        self.current_rel_version = current_rel_version
        self.latest_dict_version = latest_dict_version
        self.latest_rel_version = latest_rel_version
        self.is_dict_outdated = is_dict_outdated
        self.is_rel_outdated = is_rel_outdated
        self.maturity_score = maturity_score
        self.recommendations = recommendations


class OptimizedUseCase:
    """Result of use case optimization"""
    def __init__(
        self,
        use_case_id: int,
        optimized_name: str,
        optimized_description: str,
        optimized_questions: List[str],
        optimized_queries: List[str],
        improvements: List[str],
        maturity_score_before: float,
        maturity_score_after: float
    ):
        self.use_case_id = use_case_id
        self.optimized_name = optimized_name
        self.optimized_description = optimized_description
        self.optimized_questions = optimized_questions
        self.optimized_queries = optimized_queries
        self.improvements = improvements
        self.maturity_score_before = maturity_score_before
        self.maturity_score_after = maturity_score_after


class UseCaseMaturationService:
    """
    Service for maturing and optimizing use cases based on:
    - Latest data dictionary
    - Updated relationships
    - Schema changes
    - Business context improvements
    """
    
    async def analyze_maturity(
        self,
        use_case_id: int,
        session: AsyncSession
    ) -> MaturityAnalysis:
        """
        Analyze use case maturity level and identify improvement areas
        """
        logger.info(f"[MATURATION] Analyzing maturity for use case {use_case_id}")
        
        # Get use case
        result = await session.execute(
            select(UseCase).where(UseCase.id == use_case_id)
        )
        use_case = result.scalar_one_or_none()
        if not use_case:
            raise ValueError(f"Use case {use_case_id} not found")
        
        # Get current versions
        current_dict_version = use_case.dictionary_version
        current_rel_version = use_case.relationships_version
        
        # Get latest versions
        latest_dict_version = await session.execute(
            select(func.count(DataDictionary.id)).where(
                DataDictionary.schema_snapshot_id == use_case.schema_snapshot_id
            )
        )
        latest_dict_version = latest_dict_version.scalar() or 0
        
        latest_rel_version = await session.execute(
            select(func.count(Relationship.id)).where(
                Relationship.schema_snapshot_id == use_case.schema_snapshot_id
            )
        )
        latest_rel_version = latest_rel_version.scalar() or 0
        
        # Check if outdated
        is_dict_outdated = (
            current_dict_version is None or
            current_dict_version < latest_dict_version
        )
        is_rel_outdated = (
            current_rel_version is None or
            current_rel_version < latest_rel_version
        )
        
        # Calculate maturity score (0-1)
        maturity_score = 1.0
        if is_dict_outdated:
            maturity_score -= 0.3
        if is_rel_outdated:
            maturity_score -= 0.3
        
        # Check if questions/queries are valid
        try:
            questions = json.loads(use_case.example_questions or "[]")
            queries = json.loads(use_case.example_queries or "[]")
            if len(questions) < 3:
                maturity_score -= 0.2
            if len(queries) < 3:
                maturity_score -= 0.2
        except:
            maturity_score -= 0.2
        
        maturity_score = max(0.0, min(1.0, maturity_score))
        
        # Generate recommendations
        recommendations = []
        if is_dict_outdated:
            recommendations.append(
                f"Data dictionary has been updated (version {current_dict_version} -> {latest_dict_version}). "
                "Use case should be optimized with latest descriptions."
            )
        if is_rel_outdated:
            recommendations.append(
                f"Relationships have been updated (version {current_rel_version} -> {latest_rel_version}). "
                "Use case should use new relationship patterns."
            )
        if maturity_score < 0.7:
            recommendations.append(
                "Use case quality can be improved. Consider optimizing questions and queries."
            )
        
        logger.info(
            f"[MATURATION] Analysis complete: score={maturity_score:.2f}, "
            f"dict_outdated={is_dict_outdated}, rel_outdated={is_rel_outdated}"
        )
        
        return MaturityAnalysis(
            use_case_id=use_case_id,
            current_dict_version=current_dict_version,
            current_rel_version=current_rel_version,
            latest_dict_version=latest_dict_version,
            latest_rel_version=latest_rel_version,
            is_dict_outdated=is_dict_outdated,
            is_rel_outdated=is_rel_outdated,
            maturity_score=maturity_score,
            recommendations=recommendations
        )
    
    async def optimize_use_case(
        self,
        use_case_id: int,
        language: str = "persian",
        session: AsyncSession = None
    ) -> OptimizedUseCase:
        """
        Optimize use case using latest context
        """
        logger.info(f"[MATURATION] Optimizing use case {use_case_id}")
        
        # Get use case
        result = await session.execute(
            select(UseCase).where(UseCase.id == use_case_id)
        )
        use_case = result.scalar_one_or_none()
        if not use_case:
            raise ValueError(f"Use case {use_case_id} not found")
        
        # Analyze current maturity
        analysis = await self.analyze_maturity(use_case_id, session)
        maturity_score_before = analysis.maturity_score
        
        # Load latest context
        # 1. Schema metadata
        schema_query = select(SchemaMetadata).where(
            SchemaMetadata.schema_snapshot_id == use_case.schema_snapshot_id
        )
        schema_result = await session.execute(schema_query)
        schema_metadata = schema_result.scalars().all()
        minified_schema = _minify_schema_metadata(schema_metadata)
        
        # 2. Data dictionary
        dict_query = select(DataDictionary).where(
            DataDictionary.schema_snapshot_id == use_case.schema_snapshot_id
        )
        dict_result = await session.execute(dict_query)
        data_dictionary_raw = dict_result.scalars().all()
        data_dictionary = _format_data_dictionary(data_dictionary_raw)
        
        # 3. Relationships
        rel_query = select(Relationship).where(
            Relationship.schema_snapshot_id == use_case.schema_snapshot_id
        )
        rel_result = await session.execute(rel_query)
        relationships_raw = rel_result.scalars().all()
        relationships = _format_relationships(relationships_raw)
        
        # 4. Sample data
        sample_data = {}
        db_connector = None
        try:
            db_connector = await create_db_connector_for_snapshot(
                use_case.schema_snapshot_id, session
            )
            if db_connector:
                await db_connector.connect()
                tables_to_sample = list(minified_schema.keys())[:20]  # Limit for performance
                for table_key in tables_to_sample:
                    try:
                        if '.' in table_key:
                            schema_name, table_name = table_key.split('.', 1)
                        else:
                            schema_name = None
                            table_name = table_key
                        
                        full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name
                        sample_rows = await db_connector.sample_rows(full_table_name, limit=3)
                        if sample_rows:
                            sample_data[table_key] = sample_rows
                    except Exception as e:
                        logger.warning(f"Failed to sample {table_key}: {e}")
        except Exception as e:
            logger.warning(f"Database sampling failed: {e}")
        finally:
            if db_connector:
                try:
                    await db_connector.disconnect()
                except:
                    pass
        
        # Build optimization prompt
        prompt = self._build_optimization_prompt(
            use_case=use_case,
            minified_schema=minified_schema,
            data_dictionary=data_dictionary,
            relationships=relationships,
            sample_data=sample_data,
            language=language
        )
        
        # Get active LLM model
        model_result = await session.execute(
            select(LLMModel).where(LLMModel.is_active == True)
        )
        active_model = model_result.scalar_one_or_none()
        if not active_model:
            raise ValueError("No active LLM model found")
        
        # Generate using LLMService (unified interface)
        llm_request = LLMRequest(
            model_id=str(active_model.id),
            messages=[Message(role=MessageRole.USER, content=prompt)],
            temperature=active_model.temperature,
            max_tokens=min(4096, active_model.max_tokens * 2)
        )
        
        try:
            response = await generate_with_llm_service(session, llm_request)
            generated_text = response.text
            
            if not generated_text:
                raise ValueError("AI service returned empty response")
            
            # Parse JSON response
            cleaned_text = generated_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            optimized_data = json.loads(cleaned_text)
            
            # Extract optimized fields
            optimized_name = optimized_data.get("name") or optimized_data.get("usecase_name") or use_case.name
            optimized_description = optimized_data.get("description") or optimized_data.get("business_goal") or use_case.business_goal
            optimized_questions = optimized_data.get("typical_questions") or optimized_data.get("example_questions") or []
            optimized_queries = optimized_data.get("example_queries") or []
            
            # Ensure questions and queries are lists
            if isinstance(optimized_questions, str):
                try:
                    optimized_questions = json.loads(optimized_questions)
                except:
                    optimized_questions = [optimized_questions]
            if isinstance(optimized_queries, str):
                try:
                    optimized_queries = json.loads(optimized_queries)
                except:
                    optimized_queries = [optimized_queries]
            
            # Generate improvements list
            improvements = optimized_data.get("improvements", [])
            if not improvements:
                improvements = []
                if analysis.is_dict_outdated:
                    improvements.append("Updated with latest data dictionary descriptions")
                if analysis.is_rel_outdated:
                    improvements.append("Enhanced with new relationship patterns")
                if len(optimized_questions) > len(json.loads(use_case.example_questions or "[]")):
                    improvements.append("Added more comprehensive questions")
                if len(optimized_queries) > len(json.loads(use_case.example_queries or "[]")):
                    improvements.append("Added more SQL query examples")
            
            # Calculate maturity score after
            maturity_score_after = 1.0
            if len(optimized_questions) >= 3:
                maturity_score_after -= 0.0
            else:
                maturity_score_after -= 0.2
            if len(optimized_queries) >= 3:
                maturity_score_after -= 0.0
            else:
                maturity_score_after -= 0.2
            
            maturity_score_after = max(0.0, min(1.0, maturity_score_after))
            
            logger.info(
                f"[MATURATION] Optimization complete: "
                f"score {maturity_score_before:.2f} -> {maturity_score_after:.2f}"
            )
            
            return OptimizedUseCase(
                use_case_id=use_case_id,
                optimized_name=optimized_name,
                optimized_description=optimized_description,
                optimized_questions=optimized_questions,
                optimized_queries=optimized_queries,
                improvements=improvements,
                maturity_score_before=maturity_score_before,
                maturity_score_after=maturity_score_after
            )
            
        except Exception as e:
            logger.error(f"[MATURATION] Failed to optimize use case: {e}", exc_info=True)
            raise
    
    def _build_optimization_prompt(
        self,
        use_case: UseCase,
        minified_schema: Dict[str, Dict[str, Any]],
        data_dictionary: Dict[str, Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        sample_data: Dict[str, List[Dict[str, Any]]],
        language: str = "persian"
    ) -> str:
        """Build optimization prompt for use case enhancement"""
        
        # Format schema
        schema_lines = []
        for table_key, table_info in minified_schema.items():
            schema_lines.append(f"Table: {table_key}")
            for col in table_info["columns"]:
                col_line = f"  - {col['name']} ({col['type']})"
                if col.get("is_primary_key"):
                    col_line += " [PK]"
                if col.get("is_foreign_key"):
                    col_line += f" [FK -> {col.get('foreign_key_table', '?')}.{col.get('foreign_key_column', '?')}]"
                schema_lines.append(col_line)
            schema_lines.append("")
        
        # Format data dictionary
        dict_lines = []
        for table_key, table_dict in data_dictionary.items():
            dict_lines.append(f"Table: {table_key}")
            for col_key, col_info in table_dict.items():
                if col_key == "__table__":
                    dict_lines.append(f"  Table Description: {col_info['description']}")
                else:
                    dict_lines.append(f"  Column: {col_key}")
                    if col_info["description"]:
                        dict_lines.append(f"    Description: {col_info['description']}")
                    if col_info["example_values"]:
                        dict_lines.append(f"    Examples: {', '.join(col_info['example_values'][:5])}")
                    if col_info["synonyms"]:
                        dict_lines.append(f"    Synonyms: {col_info['synonyms']}")
            dict_lines.append("")
        
        # Format relationships
        rel_lines = []
        explicit_rels = [r for r in relationships if r.get("is_explicit", False)]
        inferred_rels = [r for r in relationships if not r.get("is_explicit", False)]
        
        if explicit_rels:
            rel_lines.append("EXPLICIT RELATIONSHIPS (Foreign Keys):")
            for rel in explicit_rels:
                rel_lines.append(f"  {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}")
                if rel.get("description"):
                    rel_lines.append(f"    Note: {rel['description']}")
            rel_lines.append("")
        
        if inferred_rels:
            rel_lines.append("INFERRED SEMANTIC RELATIONSHIPS:")
            for rel in inferred_rels:
                rel_lines.append(f"  {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}")
                rel_lines.append(f"    Type: {rel['relationship_type']}, Join: {rel['join_type']}, Cardinality: {rel['cardinality']}")
                if rel.get("description"):
                    rel_lines.append(f"    Description: {rel['description']}")
            rel_lines.append("")
        
        # Format sample data
        sample_lines = []
        if sample_data:
            sample_lines.append("SAMPLE DATA (3 unique rows per relevant table):")
            for table_key, rows in sample_data.items():
                if rows and len(rows) > 0:
                    sample_lines.append(f"\nTable: {table_key}")
                    for i, row in enumerate(rows[:3], 1):
                        sample_lines.append(f"  Row {i}: {json.dumps(row, ensure_ascii=False)}")
            sample_lines.append("")
        
        # Language instructions
        language_instructions = {
            "english": "Generate ALL content EXCLUSIVELY in English language.",
            "persian": "Generate ALL content EXCLUSIVELY in Persian (Farsi) language. Use appropriate Persian business terminology.",
            "arabic": "Generate ALL content EXCLUSIVELY in Arabic language.",
            "turkish": "Generate ALL content EXCLUSIVELY in Turkish language.",
        }
        selected_language_instruction = language_instructions.get(language.lower(), language_instructions["persian"])
        
        # Parse current use case data
        current_questions = []
        current_queries = []
        try:
            current_questions = json.loads(use_case.example_questions or "[]")
        except:
            pass
        try:
            current_queries = json.loads(use_case.example_queries or "[]")
        except:
            pass
        
        prompt = f"""You are an expert database analyst and product strategist optimizing a Text-to-SQL use case.

CURRENT USE CASE TO OPTIMIZE:
Name: {use_case.name}
Description: {use_case.business_goal}
Current Questions: {json.dumps(current_questions, ensure_ascii=False)}
Current Queries: {json.dumps(current_queries, ensure_ascii=False)}
Output Style: {use_case.output_style}
Business Context: {use_case.business_context or 'Not specified'}

LATEST DATABASE CONTEXT:
{selected_language_instruction}

DATABASE SCHEMA:
{chr(10).join(schema_lines)}

DATA DICTIONARY (Latest Descriptions):
{chr(10).join(dict_lines)}

RELATIONSHIPS (Latest):
{chr(10).join(rel_lines) if rel_lines else "No relationships defined."}

{sample_lines[0] if sample_lines else ""}
{chr(10).join(sample_lines[1:]) if len(sample_lines) > 1 else ""}

OPTIMIZATION TASKS:
1. Enhance the use case description using latest dictionary descriptions
2. Improve questions to use actual column names and business terminology from dictionary
3. Update SQL queries to leverage new relationships and patterns
4. Ensure at least 3 high-quality questions and corresponding SQL queries
5. Use real table and column names from the schema (never placeholders)
6. Make questions more specific and business-focused
7. Optimize SQL queries for better performance and accuracy

REQUIRED OUTPUT FORMAT (JSON):
{{
  "name": "Optimized use case name",
  "description": "Enhanced business goal description",
  "typical_questions": ["Question 1", "Question 2", "Question 3+"],
  "example_queries": ["SELECT ...", "SELECT ... JOIN ...", "SELECT ... GROUP BY ..."],
  "improvements": ["Improvement 1", "Improvement 2", "..."],
  "reasoning": "Brief explanation of optimizations made"
}}

CRITICAL REQUIREMENTS:
- Questions MUST be in {language} language
- Each question must have a corresponding SQL query
- SQL queries must use REAL table and column names from the schema
- Questions should be specific and use business terminology from dictionary
- Queries should demonstrate different SQL patterns (filtering, joining, aggregation)
- Never use placeholder queries like "SELECT * FROM information_schema.tables"

Return ONLY valid JSON. No markdown, no explanations outside JSON.
"""
        
        return prompt
    
    async def auto_mature_stale_use_cases(
        self,
        snapshot_id: int,
        language: str = "persian",
        session: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Automatically mature use cases that are outdated
        """
        logger.info(f"[MATURATION] Auto-maturing stale use cases for snapshot {snapshot_id}")
        
        # Get all use cases for snapshot
        result = await session.execute(
            select(UseCase).where(UseCase.schema_snapshot_id == snapshot_id)
        )
        use_cases = result.scalars().all()
        
        results = []
        for use_case in use_cases:
            try:
                # Analyze maturity
                analysis = await self.analyze_maturity(use_case.id, session)
                
                # Only optimize if outdated
                if analysis.is_dict_outdated or analysis.is_rel_outdated or analysis.maturity_score < 0.7:
                    logger.info(f"[MATURATION] Auto-optimizing use case {use_case.id}")
                    optimized = await self.optimize_use_case(use_case.id, language, session)
                    
                    results.append({
                        "use_case_id": use_case.id,
                        "use_case_name": use_case.name,
                        "optimized": True,
                        "maturity_score_before": optimized.maturity_score_before,
                        "maturity_score_after": optimized.maturity_score_after,
                        "improvements": optimized.improvements
                    })
                else:
                    results.append({
                        "use_case_id": use_case.id,
                        "use_case_name": use_case.name,
                        "optimized": False,
                        "reason": "Already up to date"
                    })
            except Exception as e:
                logger.error(f"[MATURATION] Failed to auto-mature use case {use_case.id}: {e}")
                results.append({
                    "use_case_id": use_case.id,
                    "use_case_name": use_case.name,
                    "optimized": False,
                    "error": str(e)
                })
        
        return results


# Singleton instance
use_case_maturation_service = UseCaseMaturationService()

