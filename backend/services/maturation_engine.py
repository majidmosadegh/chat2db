"""
Maturation Engine Service

A comprehensive engine for continuously maturing use cases by:
1. Generating questions based on use case knowledge
2. Generating SQL queries
3. Executing and validating queries
4. Storing successful question-query pairs
5. Retrying failed queries with alternative approaches
"""

from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import json
import asyncio
from datetime import datetime
from loguru import logger

from api.db_models import (
    UseCase, SchemaSnapshot, SchemaMetadata,
    DataDictionary, Relationship, LLMModel, DatabaseConnection
)
from api.smart_use_case_builder import (
    _minify_schema_metadata,
    _format_data_dictionary,
    _format_relationships
)
from services.db_connector_utils import create_db_connector_for_snapshot
from services.llm_helper import generate_with_llm_service
from llm.schemas import LLMRequest, Message, MessageRole
from api.database import decrypt_api_key


class MaturationContext:
    """Context information for maturation process"""
    def __init__(
        self,
        schema: Dict[str, Dict[str, Any]],
        data_dictionary: Dict[str, Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        sample_data: Dict[str, List[Dict[str, Any]]]
    ):
        self.schema = schema
        self.data_dictionary = data_dictionary
        self.relationships = relationships
        self.sample_data = sample_data


class GeneratedQuestion:
    """A generated question with its SQL query"""
    def __init__(
        self,
        question_text: str,
        generated_sql: Optional[str] = None,
        execution_status: str = "pending",  # pending, success, error, retrying
        execution_result: Optional[Any] = None,
        execution_error: Optional[str] = None,
        retry_count: int = 0,
        max_retries: int = 3
    ):
        self.question_text = question_text
        self.generated_sql = generated_sql
        self.execution_status = execution_status
        self.execution_result = execution_result
        self.execution_error = execution_error
        self.retry_count = retry_count
        self.max_retries = max_retries


class MaturationEngine:
    """
    Engine for continuous use case maturation
    
    Flow:
    1. Load context (schema, dictionary, relationships)
    2. Generate questions based on use case knowledge
    3. For each question:
       a. Generate SQL query
       b. Execute query
       c. If success: store question-query pair
       d. If error: retry with alternative approach (up to max_retries)
    """
    
    def __init__(self):
        self.active_sessions: Dict[int, Dict[str, Any]] = {}
        # Context cache: key = snapshot_id, value = (context, timestamp)
        # Cache expires after 1 hour to allow for schema updates
        self._context_cache: Dict[int, Tuple[MaturationContext, float]] = {}
        self._cache_ttl_seconds = 3600  # 1 hour
        # Error patterns cache for learning and better retry logic
        self._error_patterns: Dict[str, int] = {}  # error_pattern -> count
    
    def clear_context_cache(self, snapshot_id: Optional[int] = None) -> None:
        """Clear context cache for a specific snapshot or all snapshots
        
        Args:
            snapshot_id: If provided, clear cache for this snapshot only. If None, clear all cache.
        """
        if snapshot_id is not None:
            if snapshot_id in self._context_cache:
                del self._context_cache[snapshot_id]
                logger.info(f"[MATURATION_ENGINE] Cleared context cache for snapshot {snapshot_id}")
        else:
            self._context_cache.clear()
            logger.info("[MATURATION_ENGINE] Cleared all context cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the context cache
        
        Returns:
            Dictionary with cache statistics
        """
        import time
        current_time = time.time()
        active_caches = 0
        expired_caches = 0
        
        for snapshot_id, (context, timestamp) in self._context_cache.items():
            if (current_time - timestamp) < self._cache_ttl_seconds:
                active_caches += 1
            else:
                expired_caches += 1
        
        return {
            "total_cached_snapshots": len(self._context_cache),
            "active_caches": active_caches,
            "expired_caches": expired_caches,
            "cache_ttl_seconds": self._cache_ttl_seconds,
            "error_patterns_count": len(self._error_patterns),
            "error_patterns": dict(self._error_patterns)
        }
    
    async def get_database_type(
        self,
        snapshot_id: int,
        session: AsyncSession
    ) -> str:
        """Get database type from snapshot"""
        # Get snapshot
        snapshot_result = await session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        if not snapshot:
            return "unknown"
        
        # Get connection
        connection_result = await session.execute(
            select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
        )
        connection = connection_result.scalar_one_or_none()
        if not connection:
            return "unknown"
        
        db_type = connection.db_type.lower() if connection.db_type else "unknown"
        logger.info(f"[MATURATION_ENGINE] Database type: {db_type}")
        return db_type
    
    async def load_context(
        self,
        snapshot_id: int,
        session: AsyncSession,
        use_cache: bool = True
    ) -> MaturationContext:
        """Load all context needed for maturation
        
        Args:
            snapshot_id: Schema snapshot ID
            session: Database session
            use_cache: Whether to use cached context if available (default: True)
        """
        # Check cache first
        if use_cache and snapshot_id in self._context_cache:
            cached_context, cache_timestamp = self._context_cache[snapshot_id]
            import time
            current_time = time.time()
            if (current_time - cache_timestamp) < self._cache_ttl_seconds:
                logger.info(f"[MATURATION_ENGINE] Using cached context for snapshot {snapshot_id}")
                return cached_context
            else:
                # Cache expired, remove it
                logger.info(f"[MATURATION_ENGINE] Cache expired for snapshot {snapshot_id}, reloading")
                del self._context_cache[snapshot_id]
        
        logger.info(f"[MATURATION_ENGINE] Loading context for snapshot {snapshot_id}")
        
        # 1. Schema metadata
        schema_query = select(SchemaMetadata).where(
            SchemaMetadata.schema_snapshot_id == snapshot_id
        )
        schema_result = await session.execute(schema_query)
        schema_metadata = schema_result.scalars().all()
        minified_schema = _minify_schema_metadata(schema_metadata)
        
        # 2. Data dictionary
        dict_query = select(DataDictionary).where(
            DataDictionary.schema_snapshot_id == snapshot_id
        )
        dict_result = await session.execute(dict_query)
        data_dictionary_raw = dict_result.scalars().all()
        data_dictionary = _format_data_dictionary(data_dictionary_raw)
        
        # 3. Relationships
        rel_query = select(Relationship).where(
            Relationship.schema_snapshot_id == snapshot_id
        )
        rel_result = await session.execute(rel_query)
        relationships_raw = rel_result.scalars().all()
        relationships = _format_relationships(relationships_raw)
        
        # 4. Sample data
        sample_data = {}
        db_connector = None
        try:
            db_connector = await create_db_connector_for_snapshot(snapshot_id, session)
            if db_connector:
                await db_connector.connect()
                tables_to_sample = list(minified_schema.keys())[:20]  # Limit to 20 tables for performance
                max_sample_size_per_table = 5  # Max rows per table
                max_value_length = 100  # Max length for each value to prevent huge prompts
                
                for table_key in tables_to_sample:
                    try:
                        if '.' in table_key:
                            schema_name, table_name = table_key.split('.', 1)
                        else:
                            schema_name = None
                            table_name = table_key
                        
                        full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name
                        # Get 5 unique rows per table for better data pattern understanding
                        sample_rows = await db_connector.sample_rows(full_table_name, limit=max_sample_size_per_table)
                        if sample_rows:
                            # Limit value sizes to prevent huge prompts
                            limited_rows = []
                            for row in sample_rows:
                                limited_row = {}
                                # Limit to first 15 columns to prevent huge rows
                                for i, (col, val) in enumerate(list(row.items())[:15]):
                                    if val is not None:
                                        val_str = str(val)
                                        # Truncate long values
                                        if len(val_str) > max_value_length:
                                            val_str = val_str[:max_value_length] + "..."
                                        limited_row[col] = val_str
                                    else:
                                        limited_row[col] = None
                                limited_rows.append(limited_row)
                            sample_data[table_key] = limited_rows
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
        
        logger.info(
            f"[MATURATION_ENGINE] Context loaded: "
            f"{len(minified_schema)} tables, "
            f"{len(data_dictionary)} dict entries, "
            f"{len(relationships)} relationships, "
            f"{len(sample_data)} sampled tables"
        )
        
        context = MaturationContext(
            schema=minified_schema,
            data_dictionary=data_dictionary,
            relationships=relationships,
            sample_data=sample_data
        )
        
        # Cache the context (clean up expired entries first)
        import time
        current_time = time.time()
        # Remove expired cache entries to prevent memory leak
        expired_keys = [
            sid for sid, (_, timestamp) in self._context_cache.items()
            if (current_time - timestamp) >= self._cache_ttl_seconds
        ]
        for key in expired_keys:
            del self._context_cache[key]
            logger.debug(f"[MATURATION_ENGINE] Removed expired cache entry for snapshot {key}")
        
        self._context_cache[snapshot_id] = (context, current_time)
        logger.info(f"[MATURATION_ENGINE] Context cached for snapshot {snapshot_id} (cache size: {len(self._context_cache)})")
        
        return context
    
    def _format_context_for_prompt(self, context: MaturationContext) -> str:
        """Format context into prompt-friendly string"""
        lines = []
        
        # Schema
        lines.append("DATABASE SCHEMA:")
        for table_key, table_info in context.schema.items():
            lines.append(f"Table: {table_key}")
            for col in table_info["columns"]:
                col_line = f"  - {col['name']} ({col['type']})"
                if col.get("is_primary_key"):
                    col_line += " [PK]"
                if col.get("is_foreign_key"):
                    col_line += f" [FK -> {col.get('foreign_key_table', '?')}.{col.get('foreign_key_column', '?')}]"
                lines.append(col_line)
            lines.append("")
        
        # Data Dictionary
        lines.append("DATA DICTIONARY:")
        for table_key, table_dict in context.data_dictionary.items():
            lines.append(f"Table: {table_key}")
            for col_key, col_info in table_dict.items():
                if col_key == "__table__":
                    lines.append(f"  Table Description: {col_info['description']}")
                else:
                    lines.append(f"  Column: {col_key}")
                    if col_info["description"]:
                        lines.append(f"    Description: {col_info['description']}")
                    if col_info["example_values"]:
                        lines.append(f"    Examples: {', '.join(col_info['example_values'][:5])}")
                    if col_info["synonyms"]:
                        lines.append(f"    Synonyms: {col_info['synonyms']}")
            lines.append("")
        
        # Relationships
        explicit_rels = [r for r in context.relationships if r.get("is_explicit", False)]
        inferred_rels = [r for r in context.relationships if not r.get("is_explicit", False)]
        
        if explicit_rels:
            lines.append("EXPLICIT RELATIONSHIPS (Foreign Keys):")
            for rel in explicit_rels:
                lines.append(f"  {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}")
                if rel.get("description"):
                    lines.append(f"    Note: {rel['description']}")
            lines.append("")
        
        if inferred_rels:
            lines.append("INFERRED SEMANTIC RELATIONSHIPS:")
            for rel in inferred_rels:
                lines.append(f"  {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}")
                lines.append(f"    Type: {rel['relationship_type']}, Join: {rel['join_type']}, Cardinality: {rel['cardinality']}")
                if rel.get("description"):
                    lines.append(f"    Description: {rel['description']}")
            lines.append("")
        
        # Sample data - 5 unique rows per table
        if context.sample_data:
            lines.append("SAMPLE DATA (5 unique rows per table - USE THESE TO UNDERSTAND DATA PATTERNS):")
            for table_key, rows in context.sample_data.items():
                if rows and len(rows) > 0:
                    lines.append(f"\nTable: {table_key}")
                    for i, row in enumerate(rows[:5], 1):
                        lines.append(f"  Row {i}: {json.dumps(row, ensure_ascii=False)}")
            lines.append("")
            lines.append("IMPORTANT: Use the sample data above to understand:")
            lines.append("- Actual data types and formats in the database")
            lines.append("- Real values and patterns (dates, numbers, strings)")
            lines.append("- Data relationships and business context")
            lines.append("- Generate questions that match these actual data patterns")
            lines.append("")
        
        return "\n".join(lines)
    
    async def generate_questions(
        self,
        use_case: UseCase,
        context: MaturationContext,
        count: int = 5,
        language: str = "persian",
        session: AsyncSession = None,
        session_id: Optional[int] = None
    ) -> List[str]:
        """Generate questions based on use case knowledge
        
        Args:
            use_case: Use case to generate questions for
            context: Maturation context (schema, dictionary, etc.)
            count: Number of questions to generate
            language: Language for questions
            session: Database session
            session_id: Optional session ID to check for duplicates in current session
        """
        logger.info(f"[MATURATION_ENGINE] Generating {count} questions for use case {use_case.id}")
        
        # Get existing questions to avoid duplicates
        existing_questions = []
        try:
            existing_questions = json.loads(use_case.example_questions or "[]")
        except:
            pass
        
        # Get questions already generated in this session (if session_id provided)
        session_questions = []
        if session_id and session:
            try:
                from api.db_models import MaturationQuestion
                session_questions_result = await session.execute(
                    select(MaturationQuestion.question_text)
                    .where(MaturationQuestion.session_id == session_id)
                )
                session_questions = [q[0] for q in session_questions_result.fetchall()]
            except Exception as e:
                logger.warning(f"[MATURATION_ENGINE] Failed to get session questions: {e}")
        
        # Combine all existing questions (from use case and current session)
        all_existing_questions = existing_questions + session_questions
        
        # Get active LLM model
        model_result = await session.execute(
            select(LLMModel).where(LLMModel.is_active == True)
        )
        active_model = model_result.scalar_one_or_none()
        if not active_model:
            raise ValueError("No active LLM model found")
        
        # Format context
        context_text = self._format_context_for_prompt(context)
        
        # Language instructions
        language_instructions = {
            "persian": "Generate questions EXCLUSIVELY in Persian (Farsi) language. Use natural Persian business terminology.",
            "english": "Generate questions EXCLUSIVELY in English language.",
            "arabic": "Generate questions EXCLUSIVELY in Arabic language.",
        }
        lang_instruction = language_instructions.get(language.lower(), language_instructions["persian"])
        
        # Get existing queries for reference
        existing_queries = []
        try:
            existing_queries = json.loads(use_case.example_queries or "[]")
        except:
            pass
        
        # Build prompt with emphasis on sample data
        prompt = f"""You are an expert data analyst generating business questions for a Text-to-SQL system.

{lang_instruction}

USE CASE:
Name: {use_case.name}
Description: {use_case.business_goal}
Business Context: {use_case.business_context or 'Not specified'}
Output Style: {use_case.output_style}

EXISTING QUESTIONS (avoid duplicates - from use case and current session):
{chr(10).join(f"- {q}" for q in all_existing_questions[:15]) if all_existing_questions else "None"}

EXISTING QUERIES (for reference - understand the query patterns):
{chr(10).join(f"- {q[:100]}..." if len(q) > 100 else f"- {q}" for q in existing_queries[:5]) if existing_queries else "None"}

{context_text}

CRITICAL INSTRUCTIONS:
1. **USE SAMPLE DATA**: The SAMPLE DATA section above shows 5 unique rows from each table. 
   - Analyze the actual data values, formats, and patterns
   - Generate questions that match these REAL data patterns
   - Use actual values from sample data as examples in your questions
   - Extract real dates, numbers, categories, and text values from SAMPLE DATA section
   - Use the exact formats and values you see in sample data (don't make up values)
   - Base questions on actual business scenarios visible in the sample data

2. **DATA-DRIVEN QUESTIONS**: 
   - Look at the sample data to understand what types of queries make sense
   - If sample data shows transaction dates, generate questions about date ranges
   - If sample data shows categories, generate questions about filtering by category
   - If sample data shows amounts/prices, generate questions about aggregations

3. **QUESTION REQUIREMENTS**:
   - **MANDATORY: Generate EXACTLY {count} NEW, UNIQUE business questions**
   - **CRITICAL: You MUST return a JSON array with EXACTLY {count} questions, not just 1 or 2**
   - **If you generate fewer than {count} questions, the system will fail**
   - Questions must be directly related to the use case description
   - Questions must be answerable using the provided schema
   - Use business terminology from the data dictionary
   - Vary in complexity (simple filtering to complex aggregations)
   - Are NOT duplicates of existing questions
   - Are natural language questions (no SQL terms, no "Query:" prefix)
   - Questions should reflect the actual data patterns visible in SAMPLE DATA
   - Each question should be different and cover different aspects of the use case

4. **EXAMPLES BASED ON SAMPLE DATA**:
   - Look at the ACTUAL SAMPLE DATA section above
   - Extract real column names, values, and formats from sample data
   - Generate questions using ACTUAL table names, column names, and values from sample data
   - Example pattern: If sample shows {{"column1": "value1", "column2": "value2"}}, generate questions about "value1" and "value2"
   - NOT: Generic questions like "What is the average amount?" (too generic, doesn't match actual data)

Return ONLY a JSON array of questions, no explanations:
["Question 1", "Question 2", "Question 3", ...]

**CRITICAL: You MUST return EXACTLY {count} questions in the array.**
**DO NOT return just 1 question. You MUST generate {count} different questions.**
**Example for {count} questions: ["Question 1", "Question 2", "Question 3", "Question 4", "Question 5"]**
"""
        
        # Generate using LLMService (unified interface)
        llm_request = LLMRequest(
            model_id=str(active_model.id),
            messages=[Message(role=MessageRole.USER, content=prompt)],
            temperature=0.7,
            max_tokens=2048
        )
        
        try:
            response = await generate_with_llm_service(session, llm_request)
            generated_text = response.text.strip()
            
            # Parse JSON
            cleaned_text = generated_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            questions = json.loads(cleaned_text)
            if not isinstance(questions, list):
                questions = [questions] if questions else []
            
            # Filter out duplicates (check against both use case questions and session questions)
            unique_questions = []
            seen = set()
            existing_lower = {eq.lower().strip() for eq in all_existing_questions}
            
            for q in questions:
                q_lower = q.lower().strip()
                # Check for exact duplicates
                if q_lower not in seen and q_lower not in existing_lower:
                    # Check for similar questions (simple similarity check)
                    is_duplicate = False
                    for existing_q in all_existing_questions:
                        existing_q_lower = existing_q.lower().strip()
                        # Check if questions are very similar (more than 80% word overlap)
                        q_words = set(q_lower.split())
                        existing_words = set(existing_q_lower.split())
                        if len(q_words) > 0 and len(existing_words) > 0:
                            overlap = len(q_words & existing_words) / max(len(q_words), len(existing_words))
                            if overlap > 0.8:  # More than 80% word overlap
                                is_duplicate = True
                                logger.debug(f"[MATURATION_ENGINE] Skipping similar question: {q[:50]}... (similar to existing)")
                                break
                    
                    if not is_duplicate:
                        unique_questions.append(q)
                        seen.add(q_lower)
            
            logger.info(f"[MATURATION_ENGINE] Generated {len(unique_questions)} unique questions")
            return unique_questions[:count]
            
        except Exception as e:
            logger.error(f"[MATURATION_ENGINE] Failed to generate questions: {e}", exc_info=True)
            # Return fallback questions
            if language == "persian":
                return [
                    "چه نوع داده‌هایی در این سیستم وجود دارد؟",
                    "چند رکورد در جدول اصلی وجود دارد؟",
                    "کدام اطلاعات بیشترین تکرار را دارند؟"
                ][:count]
            else:
                return [
                    "What types of data exist in this system?",
                    "How many records are in the main table?",
                    "Which information has the most repetition?"
                ][:count]
    
    def _get_database_specific_instructions(self, db_type: str) -> str:
        """Get database-specific SQL syntax instructions"""
        db_type_lower = db_type.lower()
        
        if db_type_lower == "sqlserver":
            return """
SQL SERVER (T-SQL) SPECIFIC RULES - CRITICAL SYNTAX:

DATABASE TYPE: SQL Server (Microsoft SQL Server / T-SQL)

1. TOP SYNTAX - MUST be immediately after SELECT, before DISTINCT or column list:
   CORRECT: SELECT TOP 10 * FROM table
   CORRECT: SELECT TOP 10 column1, column2 FROM table
   CORRECT: SELECT TOP 10 DISTINCT column1 FROM table
   WRONG: SELECT DISTINCT TOP 10 * FROM table (TOP must come before DISTINCT)
   WRONG: SELECT column1, TOP 10 column2 FROM table (TOP must be right after SELECT)

2. TOP with ORDER BY:
   CORRECT: SELECT TOP 10 * FROM table ORDER BY column1 DESC
   CORRECT: SELECT TOP 10 column1, column2 FROM table WHERE condition ORDER BY column1

3. TABLE ALIASES (CRITICAL - MUST BE DEFINED BEFORE USE):
   - Table aliases are SHORT NAMES for tables to make queries shorter
   - **MANDATORY RULE**: You MUST define alias in FROM clause BEFORE using it
   - Syntax: FROM [schema].[TableName] AS alias_name  OR  FROM [schema].[TableName] alias_name
   - After defining alias in FROM, you can use it in SELECT, WHERE, JOIN, ORDER BY, etc.
   - **CRITICAL**: If you use alias like 't.' or 'e.' in SELECT or WHERE, you MUST define it in FROM first
   
   Examples (use ACTUAL table names from schema above):
   * WITHOUT alias (always works):
     SELECT [schema].[TableName].[ColumnName] 
     FROM [schema].[TableName] 
     WHERE [schema].[TableName].[FilterColumn] = 'value'
   
   * WITH alias (define in FROM first):
     SELECT t.[ColumnName] 
     FROM [schema].[TableName] AS t 
     WHERE t.[FilterColumn] = 'value'
     Note: 't' is defined in FROM clause, then used in SELECT and WHERE
   
   * WRONG - Using alias without defining it:
     SELECT t.[ColumnName] FROM [schema].[TableName] WHERE t.[FilterColumn] = 'value'
     ERROR: 't' is not defined! Must add "AS t" after TableName in FROM clause
   
   * CORRECT - Define alias in FROM:
     SELECT t.[ColumnName] FROM [schema].[TableName] AS t WHERE t.[FilterColumn] = 'value'
   
   - When using alias, you MUST use it consistently throughout the query
   - CORRECT: SELECT t.[column1], t.[column2] FROM [schema].[TableName] AS t WHERE t.[status] = 'Active'
   - WRONG: SELECT t.[column1], [TableName].[column2] FROM [schema].[TableName] AS t (mixed usage)
   - WRONG: SELECT t.[column1] FROM [schema].[TableName] WHERE t.[status] = 'Active' (alias not defined in FROM)

4. IDENTIFIERS: Use square brackets for identifiers with spaces or special characters:
   CORRECT: [schema].[table].[column]
   CORRECT: [schema].[TableName].[ColumnName]
   CORRECT: [schema].[TableName] AS alias_name
   If no spaces/special chars, brackets optional: schema.TableName AS alias_name

5. NEVER use LIMIT in SQL Server - always use TOP:
   WRONG: SELECT * FROM table LIMIT 10
   CORRECT: SELECT TOP 10 * FROM table

6. DATE FUNCTIONS: Use T-SQL date functions:
   GETDATE(), DATEADD(day, 1, date), DATEDIFF(day, date1, date2)
   FORMAT(date, 'yyyy-MM-dd') for formatting
   
   **CRITICAL: NEVER USE strftime() - This function does NOT exist in SQL Server**
   WRONG: strftime('%Y', [DateColumn]) - will cause error: "'strftime' is not a recognized built-in function name"
   CORRECT: YEAR([DateColumn]) for extracting year
   CORRECT: FORMAT([DateColumn], 'yyyy-MM-dd') for formatting dates
   CORRECT: CONVERT(VARCHAR, [DateColumn], 23) for date to string conversion

   **CRITICAL: DATE COLUMNS STORED AS STRINGS - PREVENT "CONVERSION FAILED" ERRORS:**
   - **STEP 1: CHECK SAMPLE DATA FIRST** - Look at actual date values in SAMPLE DATA section
   - **STEP 2: DETERMINE DATA TYPE**:
     * If sample data shows: 'YYYY/MM/DD', 'YYYY-MM-DD', 'DD/MM/YYYY' (with quotes, as text) → STRING column
     * If sample data shows: date/datetime type (no quotes, SQL Server date format) → DATE/DATETIME column
   - **STEP 3: USE CORRECT SYNTAX BASED ON TYPE**:
   
   **FOR STRING DATE COLUMNS (nvarchar/varchar):**
   - **NEVER USE**: YEAR(), MONTH(), DAY(), DATEPART(), DATEADD(), DATEDIFF(), CAST(), CONVERT() on string columns
   - **NEVER USE**: Direct comparison with date functions: WHERE [DateColumn] = GETDATE() (will cause "Conversion failed")
   - **NEVER USE**: WHERE [DateColumn] BETWEEN 'date1' AND 'date2' (may cause conversion errors)
   - **USE INSTEAD**: String functions: LIKE, SUBSTRING, LEFT, RIGHT
   - **CORRECT FOR YEAR**: WHERE [DateColumn] LIKE N'YYYY%' (extract year from string)
   - **CORRECT FOR YEAR**: WHERE SUBSTRING([DateColumn], 1, 4) = N'YYYY' (extract first 4 chars)
   - **CORRECT FOR MONTH**: WHERE [DateColumn] LIKE N'YYYY/MM%' (year and month)
   - **CORRECT FOR EXACT DATE**: WHERE [DateColumn] = N'YYYY/MM/DD' (exact match with N prefix)
   - **CORRECT FOR DATE RANGE**: WHERE [DateColumn] >= N'YYYY/MM/DD' AND [DateColumn] <= N'YYYY/MM/DD' (string comparison)
   
   **FOR DATE/DATETIME COLUMNS (actual date type):**
   - **CAN USE**: YEAR([DateColumn]), MONTH([DateColumn]), DAY([DateColumn])
   - **CAN USE**: DATEADD(), DATEDIFF(), DATEPART()
   - **CAN USE**: WHERE [DateColumn] = CAST('YYYY-MM-DD' AS DATE)
   - **CORRECT**: WHERE YEAR([DateColumn]) = YYYY
   - **CORRECT**: WHERE [DateColumn] BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
   
   **CRITICAL RULES TO PREVENT "CONVERSION FAILED" ERRORS:**
   - **RULE 1**: Always check SAMPLE DATA first to determine if date column is STRING or DATE type
   - **RULE 2**: If sample data shows dates as strings (with quotes), it's STRING - use LIKE/SUBSTRING, NOT date functions
   - **RULE 3**: If you're not sure, assume it's STRING and use LIKE/SUBSTRING (safer)
   - **RULE 4**: NEVER mix date functions with string columns - will cause "Conversion failed" error
   - **RULE 5**: If sample data format is 'YYYY/MM/DD' or 'YYYY-MM-DD' (with quotes), it's STRING - use string functions
   - **RULE 6**: Always use N'...' prefix for string dates if they contain non-ASCII characters

7. STRING CONCATENATION: Use + operator:
   'string1' + 'string2'

8. NULL HANDLING: Use ISNULL() or COALESCE():
   ISNULL(column, 'default') or COALESCE(column1, column2, 'default')

9. TYPE CONVERSION: Use CAST() or CONVERT():
   CAST(value AS INT) or CONVERT(INT, value)

10. SCHEMA PREFIX: May need [schema].[table] format:
   [dbo].[table_name] or dbo.table_name

11. AGGREGATION: Use proper GROUP BY syntax:
    SELECT TOP 10 column1, COUNT(*) FROM table GROUP BY column1 ORDER BY COUNT(*) DESC

12. STATISTICAL FUNCTIONS - CRITICAL:
    - **CORR() DOES NOT EXIST in SQL Server** - This function is NOT available
    - **NEVER USE**: CORR(column1, column2) - will cause error: "'CORR' is not a recognized built-in function name"
    - **FOR CORRELATION**: Use manual calculation with AVG, STDEV, or use formula:
      CORRECT: Use (SUM((x - AVG(x)) * (y - AVG(y))) / (COUNT(*) * STDEV(x) * STDEV(y))) for correlation
      CORRECT: Or use simpler approach: AVG(ABS(column1 - column2)) for deviation
      CORRECT: Or use: (AVG(column1 * column2) - AVG(column1) * AVG(column2)) / (STDEV(column1) * STDEV(column2))
    - **USE ACTUAL COLUMN NAMES**: Always use REAL column names from DATABASE SCHEMA section above
    - **CRITICAL**: Check SAMPLE DATA to see actual column names - don't assume names like "Price", "Amount", etc.
    - **CRITICAL**: If schema shows "basePrice" and "finalPrice", use those exact names, NOT "Price"
    - **CRITICAL**: If schema shows "totalTradedVolume", use that exact name, NOT "Volume" or "Quantity"
    - **RULE**: Only use column names that actually exist in the DATABASE SCHEMA section above
    - **RULE**: Check SAMPLE DATA to verify column names match what you're using

13. UNICODE STRING LITERALS (CRITICAL FOR NON-ASCII TEXT):
    - For ANY string containing non-ASCII characters (Persian, Arabic, Chinese, etc.), you MUST use N'...' prefix
    - **MANDATORY RULE**: If sample data shows ANY non-ASCII characters, use N'...' prefix
    - **APPLIES EVERYWHERE**: This rule applies to ALL string literals in the query:
      * Main query WHERE clauses: WHERE [ColumnName] = N'unicode_value'
      * Subqueries: WHERE [ColumnName] = N'unicode_value' (in subquery too!)
      * JOIN conditions: ON t1.[Column] = N'unicode_value'
      * CASE statements: CASE WHEN [Column] = N'unicode_value' THEN ...
      * IN clauses: WHERE [Column] IN (N'value1', N'value2')
    - **CHECK SAMPLE DATA**: Look at actual values in SAMPLE DATA section to determine if text contains non-ASCII
    - CORRECT: WHERE [ColumnName] = N'unicode_text_value' (Unicode string with N prefix)
    - CORRECT: (SELECT ... FROM table WHERE [Column] = N'unicode_value') (N prefix in subquery too!)
    - CORRECT: WHERE [DateColumn] = N'date_string_value' (Date strings with non-ASCII need N prefix)
    - CORRECT: WHERE [Column1] = N'value1' AND [Column2] = N'value2' (Both need N prefix if non-ASCII)
    - WRONG: WHERE [ColumnName] = 'unicode_text_value' (missing N prefix - will cause errors with Unicode)
    - WRONG: (SELECT ... FROM table WHERE [Column] = 'unicode_value') (missing N prefix in subquery - will cause errors!)
    - WRONG: WHERE [DateColumn] = 'date_string_value' (missing N prefix - will cause errors if non-ASCII)
    - For ASCII-only strings (English only, no special chars), '...' is fine: WHERE [ColumnName] = 'Active'
    - **RULE**: If sample data shows ANY non-ASCII characters, use N'...' in ALL string literals (main query, subqueries, JOINs, etc.)
    - **RULE**: Check SAMPLE DATA to see actual text values and determine if N prefix is needed
    - **SAFETY RULE**: When in doubt, use N'...' prefix - it works for both ASCII and Unicode

13. JOIN SYNTAX with ALIASES:
    CORRECT: SELECT t1.[Column1], t2.[Column2] 
             FROM [schema].[Table1] AS t1 
             INNER JOIN [schema].[Table2] AS t2 ON t1.[IDColumn] = t2.[ForeignKeyColumn]
    Note: After defining alias 't1' for Table1, use 't1' everywhere, not 'Table1'
    Use ACTUAL table names and column names from DATABASE SCHEMA section above
"""
        elif db_type_lower == "postgresql":
            return """
POSTGRESQL SPECIFIC RULES:
- Use LIMIT for row limiting: SELECT * FROM table LIMIT 10
- Use double quotes for identifiers if needed: "schema"."table"."column"
- Use standard SQL syntax
- Date functions: NOW(), CURRENT_DATE, DATE_TRUNC()
- String concatenation: Use || operator or CONCAT()
- Use COALESCE() for NULL handling
- Use CAST() or :: for type conversion
- Schema prefix: schema_name.table_name
"""
        elif db_type_lower == "mysql":
            return """
MYSQL SPECIFIC RULES:
- Use LIMIT for row limiting: SELECT * FROM table LIMIT 10
- Use backticks for identifiers if needed: `schema`.`table`.`column`
- Use MySQL-specific syntax
- Date functions: NOW(), CURDATE(), DATE_FORMAT()
- String concatenation: Use CONCAT() function
- Use IFNULL() or COALESCE() for NULL handling
- Use CAST() or CONVERT() for type conversion
- Schema prefix: schema_name.table_name
"""
        else:
            return """
STANDARD SQL RULES:
- Use LIMIT for row limiting (if supported)
- Use standard SQL syntax
- Use COALESCE() for NULL handling
- Use CAST() for type conversion
"""
    
    async def generate_sql(
        self,
        question: str,
        use_case: UseCase,
        context: MaturationContext,
        snapshot_id: int,
        language: str = "persian",
        previous_error: Optional[str] = None,
        session: AsyncSession = None
    ) -> str:
        """Generate SQL query for a question"""
        logger.info(f"[MATURATION_ENGINE] Generating SQL for question: {question[:50]}...")
        
        # Get database type
        db_type = await self.get_database_type(snapshot_id, session)
        db_instructions = self._get_database_specific_instructions(db_type)
        
        # Get active LLM model
        model_result = await session.execute(
            select(LLMModel).where(LLMModel.is_active == True)
        )
        active_model = model_result.scalar_one_or_none()
        if not active_model:
            raise ValueError("No active LLM model found")
        
        # Format context
        context_text = self._format_context_for_prompt(context)
        
        # Build prompt
        error_instruction = ""
        if previous_error:
            error_instruction = f"\nPREVIOUS ATTEMPT ERROR: {previous_error}\nPlease fix the SQL query to avoid this error."
        
        # Add SQL Server specific examples (generic, not case-specific)
        examples = ""
        if db_type.lower() == "sqlserver":
            examples = """
EXAMPLES OF CORRECT SQL SERVER QUERIES (GENERIC PATTERNS):

Example 1 - Simple query WITHOUT alias:
SELECT TOP 10 * FROM [schema].[TableName] WHERE [schema].[TableName].[ColumnName] = 'value'

Example 2 - Simple query WITH alias (define alias in FROM first):
SELECT TOP 10 * FROM [schema].[TableName] AS t WHERE t.[ColumnName] = 'value'
Note: 't' is defined in FROM clause with "AS t", then used in WHERE clause
CRITICAL: The alias 't' MUST be defined in FROM before you can use 't.' in SELECT or WHERE

Example 3 - Query with columns and alias:
SELECT TOP 5 t.[Column1], t.[Column2] 
FROM [schema].[TableName] AS t 
WHERE t.[Column2] > 100 
ORDER BY t.[Column2] DESC

Example 4 - Aggregation with alias:
SELECT TOP 10 t.[CategoryColumn], COUNT(*) as Total 
FROM [schema].[TableName] AS t 
GROUP BY t.[CategoryColumn] 
ORDER BY Total DESC

Example 5 - Date filtering with alias:
SELECT TOP 20 t.[IDColumn], t.[DateColumn] 
FROM [schema].[TableName] AS t 
WHERE t.[DateColumn] >= DATEADD(day, -30, GETDATE()) 
ORDER BY t.[DateColumn] DESC

Example 6 - Aggregation with WHERE clause using alias (with Unicode strings):
SELECT SUM(t.[NumericColumn]) AS TotalValue
FROM [schema].[TableName] AS t
WHERE t.[FilterColumn1] = N'actual_unicode_value_from_sample_data'
AND t.[FilterColumn2] = N'actual_unicode_value_from_sample_data'
AND t.[DateColumn] = N'actual_date_value_from_sample_data'
Note: Use ACTUAL values from SAMPLE DATA section
CRITICAL: If sample data shows Persian/Arabic/Unicode text OR Persian date format, use N'...' prefix (N before quotes)
Note: If sample data shows non-ASCII characters, use N'...' prefix (N before quotes)
WRONG: WHERE [DateColumn] = 'unicode_value' AND [TextColumn] = 'unicode_value' (missing N prefix - will fail if non-ASCII)
CORRECT: WHERE [DateColumn] = N'unicode_value' AND [TextColumn] = N'unicode_value' (with N prefix for non-ASCII)

Example 7 - Aggregation with string date year filtering (CRITICAL - PREVENT "CONVERSION FAILED" ERROR):
SELECT AVG([NumericColumn]) AS AverageValue
FROM [schema].[TableName]
WHERE [DateColumn] LIKE N'YYYY%'
Note: If sample data shows DateColumn as string (e.g., 'YYYY/MM/DD' with quotes), use LIKE/SUBSTRING, NOT date functions
WRONG: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE YEAR([DateColumn]) = YYYY (will cause "Conversion failed" error if DateColumn is string!)
WRONG: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE MONTH([DateColumn]) = MM (will cause "Conversion failed" error if DateColumn is string!)
WRONG: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE CAST([DateColumn] AS DATE) = 'YYYY-MM-DD' (may cause "Conversion failed" if format doesn't match!)
CORRECT: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE [DateColumn] LIKE N'YYYY%' (use LIKE for string dates - SAFE)
CORRECT: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE SUBSTRING([DateColumn], 1, 4) = N'YYYY' (extract year from string - SAFE)
CORRECT: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE [DateColumn] LIKE N'YYYY/MM%' (year and month from string - SAFE)

Example 7 - JOIN with aliases (with Unicode strings):
SELECT t1.[Column1], t2.[Column2]
FROM [schema].[Table1] AS t1
INNER JOIN [schema].[Table2] AS t2 ON t1.[IDColumn] = t2.[ForeignKeyColumn]
WHERE t1.[StatusColumn] = N'actual_unicode_value_from_sample_data'
Note: If sample data shows non-ASCII text, use N'...' prefix (N before quotes)

Example 8 - Query with subquery (CRITICAL - N prefix needed in subquery too):
SELECT AVG([NumericColumn]) AS AvgValue,
       (SELECT MAX([QuantityColumn]) FROM [schema].[TableName] WHERE [TextColumn] = N'unicode_value')
FROM [schema].[TableName]
WHERE [DateColumn] = N'date_string_value'
Note: N prefix is required in BOTH main query AND subquery if values contain non-ASCII
WRONG: (SELECT ... WHERE [Column] = 'unicode_value') - missing N prefix in subquery!
CORRECT: (SELECT ... WHERE [Column] = N'unicode_value') - N prefix in subquery!

UNDERSTANDING TABLE ALIASES (CRITICAL):
- An alias is a SHORT NAME you give to a table
- **MANDATORY**: You MUST define alias in FROM clause: FROM [schema].[TableName] AS alias_name
- **CRITICAL**: If you write "t.[ColumnName]" or "e.[ColumnName]", you MUST have "AS t" or "AS e" in FROM clause
- After defining alias in FROM, use it instead of full table name throughout the query
- Choose meaningful aliases: first letter(s) of actual table name from schema
- Aliases make queries shorter and easier to read
- You MUST use the alias consistently once defined (don't mix alias and full table name)

COMMON MISTAKES TO AVOID (CRITICAL - THESE WILL CAUSE ERRORS):

1. **NEVER USE CORR() FUNCTION**:
   - WRONG: SELECT CORR(column1, column2) - will cause error: "'CORR' is not a recognized built-in function name"
   - CORRECT: Use AVG(ABS(column1 - column2)) for deviation
   - CORRECT: Use manual correlation formula if needed
   - **CRITICAL**: CORR() does NOT exist in SQL Server - using it will ALWAYS fail

2. **USE ACTUAL COLUMN NAMES FROM SCHEMA**:
   - **CRITICAL**: Check DATABASE SCHEMA section above to see ACTUAL column names
   - **CRITICAL**: Check SAMPLE DATA section to see ACTUAL column names and values
   - **NEVER ASSUME** column names like "Price", "Amount", "Volume" exist
   - **WRONG**: SELECT Price FROM table (if "Price" doesn't exist in schema, will cause "Invalid column name" error)
   - **CORRECT**: Use ACTUAL column names from schema: SELECT [basePrice] FROM [schema].[TableName] (if basePrice exists)
   - **RULE**: Only use column names that appear in DATABASE SCHEMA section above
   - **RULE**: If schema shows "basePrice" and "finalPrice", use those exact names, NOT "Price"
   - **RULE**: If schema shows "totalTradedVolume", use that exact name, NOT "Volume" or "Quantity"
   - **RULE**: Check SAMPLE DATA to verify column names match what you're using

3. **OTHER COMMON MISTAKES**:
- WRONG: SELECT DISTINCT TOP 10 * FROM table (TOP must come before DISTINCT)
- WRONG: SELECT * FROM table LIMIT 10 (SQL Server doesn't support LIMIT)
- WRONG: SELECT column1, TOP 10 column2 FROM table (TOP must be right after SELECT)
- WRONG: SELECT t.[column1] FROM [schema].[TableName] WHERE t.[column2] = 'value' (alias 't' not defined in FROM)
- WRONG: SELECT t.[column1], TableName.[column2] FROM [schema].[TableName] AS t (mixed alias and full name)
- WRONG: WHERE [ColumnName] = 'unicode_value' (missing N prefix for Unicode - will cause errors if non-ASCII)
- WRONG: WHERE [DateColumn] = 'date_string' AND [TextColumn] = 'unicode_value' (missing N prefix - will cause errors if non-ASCII)
- WRONG: SELECT MAX([NumericColumn]) FROM [schema].[TableName] WHERE [DateColumn] = 'date_string' AND [TextColumn] = 'unicode_value' (missing N prefix)
- WRONG: (SELECT ... FROM table WHERE [Column] = 'unicode_value') (missing N prefix in SUBQUERY - will cause errors if non-ASCII!)
- WRONG: SELECT AVG([NumericColumn]), (SELECT MAX([Qty]) FROM table WHERE [Column] = 'unicode_value') FROM table (missing N prefix in subquery!)
- WRONG: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE YEAR([DateColumn]) = YYYY (if DateColumn is STRING - YEAR() doesn't work on strings, will cause "Conversion failed" error)
- CORRECT: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE [DateColumn] LIKE N'YYYY%' (use LIKE for string dates, with N prefix)
- CORRECT: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE SUBSTRING([DateColumn], 1, 4) = N'YYYY' (extract year from string)
- CORRECT: (SELECT ... FROM table WHERE [Column] = N'unicode_value') (N prefix in SUBQUERY too!)
- CORRECT: SELECT AVG([NumericColumn]), (SELECT MAX([Qty]) FROM table WHERE [Column] = N'unicode_value') FROM table (N prefix in subquery!)
- CORRECT: SELECT t.[column1], t.[column2] FROM [schema].[TableName] AS t WHERE t.[column2] = N'value' (alias defined, N prefix for Unicode if needed)
- CORRECT: WHERE [ColumnName] = N'unicode_value' (N prefix for Unicode/non-ASCII text)
- CORRECT: WHERE [DateColumn] = N'date_string' AND [TextColumn] = N'unicode_value' (both with N prefix if non-ASCII)
- CORRECT: SELECT MAX([NumericColumn]) FROM [schema].[TableName] WHERE [DateColumn] = N'date_string' AND [TextColumn] = N'unicode_value'
- CORRECT: SELECT [schema].[TableName].[column1] FROM [schema].[TableName] WHERE [schema].[TableName].[column2] = N'value' (no alias, N prefix for Unicode)
"""
        
        # Get existing queries for reference
        existing_queries = []
        try:
            existing_queries = json.loads(use_case.example_queries or "[]")
        except:
            pass
        
        existing_queries_text = ""
        if existing_queries:
            existing_queries_text = f"""
EXISTING EXAMPLE QUERIES FROM THIS USE CASE (use as reference for patterns):
{chr(10).join(f"Example {i+1}: {q}" for i, q in enumerate(existing_queries[:3]))}
"""
        
        # Extract actual data patterns from sample data for better query generation
        sample_data_examples = ""
        if context.sample_data:
            sample_data_examples = "\nACTUAL DATA PATTERNS FROM SAMPLE DATA:\n"
            for table_key, rows in list(context.sample_data.items())[:5]:  # Limit to 5 tables
                if rows and len(rows) > 0:
                    sample_data_examples += f"\nTable: {table_key}\n"
                    # Show column names and sample values
                    first_row = rows[0]
                    for col_name, col_value in list(first_row.items())[:10]:  # Limit to 10 columns
                        sample_data_examples += f"  - {col_name}: {col_value} (example value)\n"
                    # Show data type patterns
                    if len(rows) > 1:
                        sample_data_examples += f"  Sample values: {', '.join([str(list(r.values())[0])[:30] for r in rows[:3]])}\n"
        
        prompt = f"""You are a Text-to-SQL expert for {db_type.upper()} database.

DATABASE TYPE: {db_type.upper()}
{db_instructions}
{examples}

{context_text}

{sample_data_examples}

USE CASE:
{use_case.business_goal}
{existing_queries_text}

Question: {question}
{error_instruction}

CRITICAL: USE SAMPLE DATA TO GENERATE LOGICAL QUERIES
- The SAMPLE DATA section shows 5 REAL rows from each table with ACTUAL values
- **ANALYZE the sample data carefully**: Look at actual column values, formats, and patterns
- **USE REAL VALUES**: Extract actual dates, numbers, and text values from SAMPLE DATA section
- Use the EXACT format and values you see in sample data (don't change formats or make up values)
- **USE REAL RANGES**: If sample data shows numbers like 1000000, use similar ranges in filters
- **MATCH DATA TYPES**: If sample shows strings, use string comparisons; if numbers, use numeric comparisons

**CRITICAL: USE ACTUAL COLUMN NAMES FROM SCHEMA**
- **MANDATORY**: Check DATABASE SCHEMA section above to see ACTUAL column names
- **MANDATORY**: Check SAMPLE DATA section to see ACTUAL column names and values
- **NEVER ASSUME** column names like "Price", "Amount", "Volume", "Quantity" exist
- **ERROR EXAMPLE**: Using "Price" when schema only has "basePrice" and "finalPrice" will cause: "Invalid column name 'Price'"
- **RULE**: Only use column names that appear in DATABASE SCHEMA section above
- **RULE**: If schema shows "basePrice" and "finalPrice", use those exact names, NOT "Price"
- **RULE**: If schema shows "totalTradedVolume", use that exact name, NOT "Volume" or "Quantity"
- **RULE**: Check SAMPLE DATA to verify column names match what you're using

**CRITICAL: NEVER USE CORR() FUNCTION**
- **CORR() DOES NOT EXIST in SQL Server** - will cause error: "'CORR' is not a recognized built-in function name"
- **NEVER USE**: SELECT CORR(column1, column2) - will ALWAYS fail
- **USE INSTEAD**: AVG(ABS(column1 - column2)) for deviation
- **USE INSTEAD**: Manual correlation formula if correlation is needed
- **ERROR EXAMPLE**: Using CORR() will cause: "'CORR' is not a recognized built-in function name"
- **UNICODE STRINGS (CRITICAL)**: If sample data shows ANY non-ASCII characters (Persian, Arabic, Unicode, or Persian date format), use N'...' prefix in WHERE clauses
  * Example: If sample shows non-ASCII text, use WHERE [ColumnName] = N'unicode_value' (NOT 'unicode_value' without N)
  * Example: If sample shows date as string, use WHERE [DateColumn] = N'date_string' (NOT 'date_string' without N if non-ASCII)
  * Example: WHERE [DateColumn] = N'date_string' AND [TextColumn] = N'unicode_value' (both need N prefix if non-ASCII)
  * **RULE**: If you see ANY non-ASCII characters in sample data, use N'...' prefix
  * **SAFETY**: When in doubt, use N'...' - it works for both ASCII and Unicode strings
- **DATE COLUMNS STORED AS STRINGS (CRITICAL - PREVENT "CONVERSION FAILED" ERRORS)**:
  * **STEP 1: CHECK SAMPLE DATA FIRST** - Look at actual date values in SAMPLE DATA section
  * **STEP 2: IDENTIFY TYPE**:
    - If sample shows: 'YYYY/MM/DD', 'YYYY-MM-DD', 'DD/MM/YYYY' (with quotes, as text) → STRING column
    - If sample shows: date/datetime type (no quotes, SQL Server date format) → DATE/DATETIME column
  * **STEP 3: USE CORRECT SYNTAX - PREVENT ERRORS**:
    - **NEVER USE ON STRING COLUMNS (WILL CAUSE "CONVERSION FAILED" ERROR)**:
      * YEAR([DateColumn]), MONTH([DateColumn]), DAY([DateColumn])
      * DATEPART(), DATEADD(), DATEDIFF()
      * CAST([DateColumn] AS DATE), CONVERT(DATE, [DateColumn])
      * [DateColumn] = GETDATE(), [DateColumn] BETWEEN date1 AND date2
    - **USE INSTEAD FOR STRING COLUMNS (SAFE)**:
      * WHERE [DateColumn] LIKE N'YYYY%' (extract year - SAFE)
      * WHERE SUBSTRING([DateColumn], 1, 4) = N'YYYY' (extract year - SAFE)
      * WHERE [DateColumn] LIKE N'YYYY/MM%' (year and month - SAFE)
      * WHERE [DateColumn] = N'YYYY/MM/DD' (exact date - SAFE)
  * **RULE**: If sample data shows dates as strings (with quotes), use LIKE/SUBSTRING, NOT date functions
  * **RULE**: If unsure, assume STRING and use LIKE/SUBSTRING (safer, prevents "Conversion failed" errors)
- **AVOID GENERIC QUERIES**: Don't generate queries that return empty results - use filters based on actual data

EXAMPLE LOGIC (use ACTUAL data from SAMPLE DATA section):
- Look at the SAMPLE DATA section above to see actual table names, column names, and values
- Extract real values from sample data rows
- If sample data shows: {{"ColumnName1": "ActualValue1", "ColumnName2": "ActualValue2"}}
- Generate: SELECT * FROM [schema].[ActualTableName] WHERE [ColumnName1] = 'ActualValue1' AND [ColumnName2] = 'ActualValue2'
- **CRITICAL FOR UNICODE**: If sample data shows non-ASCII text (Persian, Arabic, Chinese, etc.):
  * **APPLIES EVERYWHERE**: Use N'...' prefix in ALL string literals - main query, subqueries, JOINs, CASE, IN clauses
  * Use N'...' prefix: WHERE [ColumnName] = N'unicode_value' (NOT 'unicode_value' without N)
  * Use N'...' prefix: (SELECT ... FROM table WHERE [Column] = N'unicode_value') (N prefix in subquery too!)
  * Use N'...' prefix: WHERE [TextColumn] = N'unicode_value' (NOT 'unicode_value' without N)
  * Example: WHERE t.[TextColumn1] = N'unicode_value' AND t.[TextColumn2] = N'unicode_value'
  * Example: SELECT ... FROM table1 WHERE [Column] = (SELECT ... FROM table2 WHERE [Column] = N'unicode_value') (N prefix in subquery!)
- **CRITICAL FOR STRING DATE COLUMNS - PREVENT "CONVERSION FAILED" ERRORS**: If sample data shows date format as string (e.g., 'YYYY/MM/DD', 'YYYY-MM-DD' with quotes):
  * **STEP 1**: Check SAMPLE DATA - if dates are shown as strings (with quotes), it's a STRING column
  * **STEP 2**: These are STRING columns, NOT date/datetime type - NEVER use date functions on them
  * **NEVER USE (WILL CAUSE "CONVERSION FAILED" ERROR)**:
    - WHERE YEAR([DateColumn]) = YYYY (YEAR() doesn't work on strings)
    - WHERE MONTH([DateColumn]) = MM (MONTH() doesn't work on strings)
    - WHERE DAY([DateColumn]) = DD (DAY() doesn't work on strings)
    - WHERE DATEPART(year, [DateColumn]) = YYYY (DATEPART() doesn't work on strings)
    - WHERE CAST([DateColumn] AS DATE) = 'YYYY-MM-DD' (CAST may fail if format doesn't match)
    - WHERE CONVERT(DATE, [DateColumn]) = 'YYYY-MM-DD' (CONVERT may fail if format doesn't match)
    - WHERE [DateColumn] = GETDATE() (comparison with date function causes conversion error)
  * **USE INSTEAD (SAFE FOR STRING DATES)**:
    - WHERE [DateColumn] LIKE N'YYYY%' (extract year - SAFE, prevents errors)
    - WHERE SUBSTRING([DateColumn], 1, 4) = N'YYYY' (extract first 4 chars for year - SAFE)
    - WHERE [DateColumn] LIKE N'YYYY/MM%' (for specific year and month - SAFE)
    - WHERE [DateColumn] = N'YYYY/MM/DD' (exact date match - SAFE)
  * Example CORRECT: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE [DateColumn] LIKE N'YYYY%' (NOT YEAR([DateColumn]) = YYYY)
  * Example WRONG: SELECT AVG([NumericColumn]) FROM [schema].[TableName] WHERE YEAR([DateColumn]) = YYYY (will cause "Conversion failed" error!)
- Use the EXACT table names, column names, and values from SAMPLE DATA
- NOT: Use made-up table names, column names, or values that don't exist in sample data
- NOT: Use '...' for Unicode strings - always use N'...' for non-ASCII text if sample data shows non-ASCII
- NOT: Use YEAR() function on string date columns - if sample data shows dates as strings, use LIKE or SUBSTRING instead

TASK:
Generate ONE valid SQL SELECT query that:
1. Answers the question accurately
2. Uses actual data patterns from SAMPLE DATA
3. Will return meaningful results (not empty)
4. Uses proper filters based on real data values

CRITICAL RULES:
1. DATABASE TYPE: This is {db_type.upper()} database - follow {db_type.upper()}-specific syntax rules above EXACTLY
2. Use ONLY tables and columns from the schema above
3. Use proper JOINs based on relationships
4. Use data dictionary descriptions to understand column meanings
5. **TABLE ALIASES - CRITICAL RULE**:
   - **MANDATORY**: If you use alias like 't.' or 'e.' in SELECT or WHERE, you MUST define it in FROM clause first
   - Syntax: FROM [schema].[TableName] AS alias_name
   - Example WITH alias: SELECT t.[ColumnName] FROM [schema].[TableName] AS t WHERE t.[FilterColumn] = 'value'
   - Example WITHOUT alias (always safe): SELECT [schema].[TableName].[ColumnName] FROM [schema].[TableName] WHERE [schema].[TableName].[FilterColumn] = 'value'
   - **IMPORTANT**: If you're not sure about alias syntax, DON'T use alias - use full table name with schema prefix
   - **SAFETY TIP**: For simple queries, you can avoid aliases entirely and use full table names
   - Once you define an alias, use it consistently (don't mix alias and full table name)
6. **MANDATORY**: Use actual values from SAMPLE DATA in WHERE clauses and filters
7. **MANDATORY**: Ensure your query will return results by using realistic filters
8. Return ONLY the SQL query, no explanations, no markdown, no code blocks
9. The query must be executable on {db_type.upper()} database
10. Follow {db_type.upper()}-specific syntax rules above EXACTLY
11. Use correct identifier quoting for {db_type.upper()} (square brackets for SQL Server)
12. For SQL Server: TOP must come IMMEDIATELY after SELECT, before DISTINCT or columns
13. For SQL Server: NEVER use LIMIT, always use TOP
14. **UNICODE STRINGS (CRITICAL)**: For SQL Server, if sample data shows ANY non-ASCII characters:
    - ALWAYS use N'...' prefix (N before quotes) for Unicode strings
    - This includes: Any non-ASCII characters (Persian, Arabic, Chinese, etc.)
    - CORRECT: WHERE [ColumnName] = N'unicode_value' (with N prefix)
    - CORRECT: WHERE [DateColumn] = N'date_string' AND [TextColumn] = N'unicode_value' (both with N prefix if non-ASCII)
    - WRONG: WHERE [ColumnName] = 'unicode_value' (missing N prefix - will cause errors if non-ASCII)
    - WRONG: WHERE [DateColumn] = 'date_string' AND [TextColumn] = 'unicode_value' (missing N prefix - will cause errors if non-ASCII)
    - Check SAMPLE DATA: If you see ANY non-ASCII characters, use N prefix
    - **SAFETY RULE**: When in doubt, use N'...' prefix - it works for both ASCII and Unicode
15. **DATE COLUMNS STORED AS STRINGS (CRITICAL - PREVENT "CONVERSION FAILED" ERRORS)**:
    - **STEP 1: CHECK SAMPLE DATA FIRST** - Look at actual date values in SAMPLE DATA section
    - **STEP 2: IDENTIFY TYPE**:
      * If sample shows: 'YYYY/MM/DD', 'YYYY-MM-DD', 'DD/MM/YYYY' (with quotes, as text) → STRING column (nvarchar/varchar)
      * If sample shows: date/datetime type (no quotes, SQL Server date format) → DATE/DATETIME column
    - **STEP 3: USE CORRECT SYNTAX - PREVENT "CONVERSION FAILED" ERRORS**:
    
    **FOR STRING DATE COLUMNS (PREVENT ERRORS):**
    - **NEVER USE THESE (WILL CAUSE "CONVERSION FAILED" ERROR)**:
      * YEAR([DateColumn]) - doesn't work on strings
      * MONTH([DateColumn]) - doesn't work on strings
      * DAY([DateColumn]) - doesn't work on strings
      * DATEPART(year, [DateColumn]) - doesn't work on strings
      * DATEADD(), DATEDIFF() - don't work on strings
      * CAST([DateColumn] AS DATE) - may fail if format doesn't match
      * CONVERT(DATE, [DateColumn]) - may fail if format doesn't match
      * [DateColumn] = GETDATE() - comparison causes conversion error
      * [DateColumn] BETWEEN date1 AND date2 - may cause conversion error
    - **USE INSTEAD (SAFE FOR STRINGS)**:
      * WHERE [DateColumn] LIKE N'YYYY%' (extract year - SAFE, prevents errors)
      * WHERE SUBSTRING([DateColumn], 1, 4) = N'YYYY' (extract year - SAFE)
      * WHERE [DateColumn] LIKE N'YYYY/MM%' (year and month - SAFE)
      * WHERE [DateColumn] = N'YYYY/MM/DD' (exact date - SAFE)
      * WHERE [DateColumn] >= N'YYYY/MM/DD' AND [DateColumn] <= N'YYYY/MM/DD' (range - SAFE)
    
    **FOR DATE/DATETIME COLUMNS (actual date type):**
    - **CAN USE**: YEAR([DateColumn]), MONTH([DateColumn]), DAY([DateColumn])
    - **CAN USE**: DATEADD(), DATEDIFF(), DATEPART()
    - **CAN USE**: WHERE [DateColumn] BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
    
    **CRITICAL RULES TO PREVENT ERRORS:**
    - **RULE 1**: Always check SAMPLE DATA first - if dates are shown as strings (with quotes), use string functions
    - **RULE 2**: If unsure, assume STRING and use LIKE/SUBSTRING (safer, prevents "Conversion failed" errors)
    - **RULE 3**: NEVER use date functions (YEAR, MONTH, DAY, DATEPART, DATEADD, DATEDIFF) on string columns
    - **RULE 4**: NEVER use CAST/CONVERT on string dates unless you're 100% sure of the format
    - **RULE 5**: Always use N'...' prefix for string dates if they contain non-ASCII characters
16. **PREVENT "CONVERSION FAILED" ERRORS - CRITICAL CHECKLIST**:
    Before generating your query, ask yourself:
    - [ ] Did I check SAMPLE DATA to see if date columns are STRING or DATE type?
    - [ ] If date column is STRING (shown with quotes in sample data), did I use LIKE/SUBSTRING instead of YEAR/MONTH/DAY?
    - [ ] Did I avoid using CAST/CONVERT on string dates?
    - [ ] Did I avoid using date functions (YEAR, MONTH, DAY, DATEPART, DATEADD, DATEDIFF) on string columns?
    - [ ] Did I avoid comparing string date columns with GETDATE() or other date functions?
    - [ ] If I'm filtering by year on a string date, did I use LIKE N'YYYY%' or SUBSTRING instead of YEAR()?
    - [ ] Did I use N'...' prefix for all string literals containing non-ASCII characters (including in subqueries)?
    - [ ] If unsure about date column type, did I assume STRING and use LIKE/SUBSTRING (safer)?
    
    **REMEMBER**: "Conversion failed" errors happen when you use date functions on string columns or try to convert strings to dates with wrong format. Always check SAMPLE DATA first!
15. **VALIDATION**: Before returning query, check:
    - If you used alias (like t. or e.), is it defined in FROM clause?
    - Are all table names and column names from actual schema?
    - If sample data has Persian/Arabic text, did you use N'...' prefix?
    - Will this query execute without syntax errors?
16. Test your query mentally: Will it return results based on sample data? If not, adjust filters.

SQL Query:"""
        
        # Initialize ModelConnector
        config = {"models": []}
        provider_map = {
            "OpenAI": "openai",
            "Ollama": "ollama",
            "vLLM": "vllm",
        }
        provider = provider_map.get(active_model.service_name, "custom")
        
        config["models"].append({
            "id": str(active_model.id),
            "provider": provider,
            "base_url": active_model.base_url,
            "model_name": active_model.model_name,
            "api_key": decrypt_api_key(active_model.api_key) if active_model.api_key else None,
            "supports_chat": True,
            "supports_json": provider == "openai",
            "max_tokens": active_model.max_tokens,
            "is_active": True,
            "timeout_seconds": 1800.0,
        })
        
        # Generate using LLMService (unified interface)
        llm_request = LLMRequest(
            model_id=str(active_model.id),
            messages=[Message(role=MessageRole.USER, content=prompt)],
            temperature=0.1,  # Lower temperature for SQL generation
            max_tokens=1024
        )
        
        try:
            response = await generate_with_llm_service(session, llm_request)
            sql = response.text.strip()
            
            # Clean SQL
            if sql.startswith('```sql'):
                sql = sql[6:]
            elif sql.startswith('```'):
                sql = sql[3:]
            if sql.endswith('```'):
                sql = sql[:-3]
            sql = sql.strip()
            
            logger.info(f"[MATURATION_ENGINE] Generated SQL: {sql[:100]}...")
            return sql
            
        except Exception as e:
            logger.error(f"[MATURATION_ENGINE] Failed to generate SQL: {e}", exc_info=True)
            raise
    
    def _transform_sql_for_sqlserver(self, sql: str) -> str:
        """Transform SQL query to fix SQL Server compatibility issues
        
        Fixes common issues like strftime() which doesn't exist in SQL Server.
        """
        import re
        
        # Fix strftime() calls - SQL Server doesn't support strftime
        # Common patterns:
        # strftime('%Y', column) -> YEAR(column)
        # strftime('%m', column) -> MONTH(column)
        # strftime('%d', column) -> DAY(column)
        # strftime('%Y-%m-%d', column) -> FORMAT(column, 'yyyy-MM-dd')
        
        # Pattern 1: strftime('%Y', column) -> YEAR(column)
        sql = re.sub(
            r"strftime\s*\(\s*['\"]%Y['\"]\s*,\s*([^)]+)\s*\)",
            r"YEAR(\1)",
            sql,
            flags=re.IGNORECASE
        )
        
        # Pattern 2: strftime('%m', column) -> MONTH(column)
        sql = re.sub(
            r"strftime\s*\(\s*['\"]%m['\"]\s*,\s*([^)]+)\s*\)",
            r"MONTH(\1)",
            sql,
            flags=re.IGNORECASE
        )
        
        # Pattern 3: strftime('%d', column) -> DAY(column)
        sql = re.sub(
            r"strftime\s*\(\s*['\"]%d['\"]\s*,\s*([^)]+)\s*\)",
            r"DAY(\1)",
            sql,
            flags=re.IGNORECASE
        )
        
        # Pattern 4: strftime('%Y-%m-%d', column) -> FORMAT(column, 'yyyy-MM-dd')
        sql = re.sub(
            r"strftime\s*\(\s*['\"]%Y-%m-%d['\"]\s*,\s*([^)]+)\s*\)",
            r"FORMAT(\1, 'yyyy-MM-dd')",
            sql,
            flags=re.IGNORECASE
        )
        
        # Pattern 5: Generic strftime - try to extract format and column, convert to FORMAT
        # This handles other formats like '%Y/%m/%d'
        def replace_strftime(match):
            full_match = match.group(0)
            # Try to extract format and column
            # Pattern: strftime('format', column)
            format_match = re.search(r"strftime\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*([^)]+)\s*\)", full_match, re.IGNORECASE)
            if format_match:
                format_str = format_match.group(1)
                column = format_match.group(2)
                # Convert common format strings to SQL Server format
                format_map = {
                    '%Y-%m-%d': 'yyyy-MM-dd',
                    '%Y/%m/%d': 'yyyy/MM/dd',
                    '%d/%m/%Y': 'dd/MM/yyyy',
                    '%m/%d/%Y': 'MM/dd/yyyy',
                }
                sql_format = format_map.get(format_str, 'yyyy-MM-dd')
                return f"FORMAT({column}, '{sql_format}')"
            # If we can't parse it, just remove strftime and use column directly
            # This is a fallback - better than failing
            logger.warning(f"[MATURATION_ENGINE] Could not parse strftime format, using column directly: {full_match}")
            return column if format_match else full_match
        
        # Replace remaining strftime calls with generic handler
        sql = re.sub(
            r"strftime\s*\([^)]+\)",
            replace_strftime,
            sql,
            flags=re.IGNORECASE
        )
        
        if 'strftime' in sql.lower():
            logger.warning(f"[MATURATION_ENGINE] SQL still contains strftime after transformation: {sql[:200]}")
        
        return sql
    
    def _validate_unicode_strings(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validate that Unicode strings use N'...' prefix in SQL Server queries"""
        import re
        
        # Check if query contains non-ASCII characters in string literals
        # Pattern: '...' where ... contains non-ASCII
        string_pattern = r"'([^']*)'"
        matches = re.finditer(string_pattern, sql, re.IGNORECASE)
        
        unicode_strings_without_n = []
        for match in matches:
            string_content = match.group(1)
            # Check if string contains non-ASCII characters
            has_non_ascii = any(ord(char) > 127 for char in string_content)
            if has_non_ascii:
                # Check if this string has N prefix
                match_start = match.start()
                # Look backwards to see if there's N before the quote
                before_quote = sql[max(0, match_start - 2):match_start]
                if not before_quote.strip().upper().endswith('N'):
                    unicode_strings_without_n.append(f"'{string_content[:30]}...'")
        
        if unicode_strings_without_n:
            return False, f"Unicode strings found without N prefix: {', '.join(unicode_strings_without_n)}. Use N'...' for Unicode strings. Check SAMPLE DATA to see actual values and use N prefix if they contain non-ASCII characters."
        
        return True, None
    
    def _validate_sql_aliases(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validate that all aliases used in query are properly defined in FROM clause"""
        import re
        
        # SQL keywords to skip
        sql_keywords = {
            'SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'FULL', 'OUTER',
            'ON', 'AS', 'TOP', 'ORDER', 'GROUP', 'BY', 'HAVING', 'AND', 'OR', 'NOT', 
            'IN', 'LIKE', 'IS', 'NULL', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'DISTINCT',
            'UNION', 'ALL', 'EXISTS', 'BETWEEN', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END'
        }
        
        # Common schema names that should be ignored
        common_schemas = {'dbo', 'sys', 'information_schema', 'pg_catalog', 'mysql', 'performance_schema'}
        
        # Extract all aliases used (pattern: alias.column or alias.[column])
        # But we need to distinguish between schema.table and alias.column
        used_aliases = set()
        
        # First, find all FROM/JOIN clauses to identify table references and schema names
        # This helps us distinguish schema.table from alias.column
        # Pattern: FROM schema.table or FROM [schema].[table] (but not the alias part)
        table_ref_pattern = r'(?:FROM|JOIN)\s+([^\s,]+?)(?:\s+AS\s+|\s+WHERE|\s+JOIN|\s+ON|\s+ORDER|\s+GROUP|\s+HAVING|$)'
        table_refs = re.findall(table_ref_pattern, sql, re.IGNORECASE)
        
        # Extract schema names from table references (before AS keyword)
        schema_names = set()
        for ref in table_refs:
            ref = ref.strip()
            # Handle [schema].[table] or schema.table or [table] or dbo.table
            # But stop at AS keyword (which indicates alias definition)
            if ' AS ' in ref.upper():
                ref = ref.split(' AS ', 1)[0].strip()
            if '.' in ref:
                # Remove brackets if present for parsing
                ref_clean = ref.replace('[', '').replace(']', '')
                parts = ref_clean.split('.')
                if len(parts) >= 2:
                    # First part is likely schema
                    schema_names.add(parts[0].upper())
        
        # Now find alias usage patterns: alias.column
        # But exclude if the alias is a known schema name
        alias_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\.(?:\[?[a-zA-Z_][a-zA-Z0-9_]*\]?|\*)'
        matches = re.finditer(alias_pattern, sql, re.IGNORECASE)
        for match in matches:
            alias = match.group(1).strip()
            alias_upper = alias.upper()
            
            # Skip SQL keywords
            if alias_upper in sql_keywords:
                continue
            
            # Skip if it's a schema name we found in table references
            if alias_upper in schema_names:
                continue
            
            # Skip common schema names
            if alias_upper in {s.upper() for s in common_schemas}:
                continue
            
            # This looks like a real alias usage
            used_aliases.add(alias)
        
        if not used_aliases:
            return True, None  # No aliases used, validation passes
        
        # Extract aliases defined in FROM clauses
        defined_aliases = set()
        # Match: FROM [schema].[table] AS alias or FROM [schema].[table] alias
        # Also handle: FROM table AS alias, FROM [table] AS alias, FROM schema.table AS alias
        # Pattern 1: FROM [schema].[table] AS alias or FROM schema.table AS alias
        from_pattern1 = r'FROM\s+(?:\[?[^\]]+\]?\.)?\[?[^\]]+\]?\s+AS\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        from_matches1 = re.findall(from_pattern1, sql, re.IGNORECASE)
        for alias in from_matches1:
            alias = alias.strip()
            if alias.upper() not in sql_keywords:
                defined_aliases.add(alias)
        
        # Pattern 2: FROM [schema].[table] alias (without AS) or FROM schema.table alias
        # But we need to be careful - the word after table might be WHERE, JOIN, etc.
        from_pattern2 = r'FROM\s+(?:\[?[^\]]+\]?\.)?\[?[^\]]+\]?\s+([a-zA-Z_][a-zA-Z0-9_]+)(?=\s+(?:WHERE|JOIN|,|$|ORDER|GROUP|HAVING))'
        from_matches2 = re.findall(from_pattern2, sql, re.IGNORECASE)
        for alias in from_matches2:
            alias = alias.strip()
            # Skip if it's a SQL keyword (likely not an alias)
            if alias.upper() not in sql_keywords and alias.upper() not in {'INNER', 'LEFT', 'RIGHT', 'FULL', 'OUTER'}:
                defined_aliases.add(alias)
        
        # Also check JOIN clauses for alias definitions
        join_patterns = [
            r'(?:INNER|LEFT|RIGHT|FULL|OUTER)?\s*JOIN\s+(?:\[?[^\]]+\]?\.)?\[?[^\]]+\]?\s+AS\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'(?:INNER|LEFT|RIGHT|FULL|OUTER)?\s*JOIN\s+(?:\[?[^\]]+\]?\.)?\[?[^\]]+\]?\s+([a-zA-Z_][a-zA-Z0-9_]+)(?:\s|$|ON)',
            r'(?:INNER|LEFT|RIGHT|FULL|OUTER)?\s*JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]+)\s+AS\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'(?:INNER|LEFT|RIGHT|FULL|OUTER)?\s*JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]+)(?:\s|$|ON)',
        ]
        
        for pattern in join_patterns:
            join_matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in join_matches:
                if isinstance(match, tuple):
                    alias = match[-1].strip() if match[-1] else None
                else:
                    alias = match.strip()
                if alias and alias.upper() not in sql_keywords:
                    defined_aliases.add(alias)
        
        # Check if all used aliases are defined (case-insensitive comparison)
        used_upper = {a.upper() for a in used_aliases}
        defined_upper = {a.upper() for a in defined_aliases}
        undefined_aliases = [a for a in used_aliases if a.upper() not in defined_upper]
        
        if undefined_aliases:
            return False, f"Aliases used but not defined in FROM clause: {', '.join(undefined_aliases)}. You must define alias in FROM clause first: FROM [schema].[TableName] AS alias_name"
        
        return True, None
    
    def _extract_error_pattern(self, error: str) -> Optional[str]:
        """Extract error pattern from error message for learning and better retry logic
        
        Args:
            error: Error message string
            
        Returns:
            Error pattern identifier or None
        """
        if not error:
            return None
        
        error_lower = error.lower()
        
        # Common error patterns for SQL Server
        if "invalid column name" in error_lower:
            return "invalid_column_name"
        elif "not a recognized built-in function" in error_lower or "is not a recognized" in error_lower:
            return "unsupported_function"
        elif "conversion failed" in error_lower or "cannot convert" in error_lower or "converting date" in error_lower:
            return "type_conversion_error"
        elif "timeout" in error_lower:
            return "timeout_error"
        elif "alias" in error_lower and ("not defined" in error_lower or "undefined" in error_lower):
            return "alias_undefined"
        elif "unicode" in error_lower or "n prefix" in error_lower:
            return "unicode_string_error"
        elif "syntax error" in error_lower or "incorrect syntax" in error_lower:
            return "syntax_error"
        elif "no results" in error_lower or "empty" in error_lower or "returned no results" in error_lower:
            return "empty_results"
        elif "object has no attribute" in error_lower:
            return "attribute_error"
        else:
            return "unknown_error"
    
    def _get_error_pattern_guidance(self, error_pattern: str) -> Optional[str]:
        """Get guidance message for error pattern to help LLM fix the issue
        
        Args:
            error_pattern: Error pattern identifier
            
        Returns:
            Guidance message or None
        """
        guidance_map = {
            "invalid_column_name": "CRITICAL: Check DATABASE SCHEMA section to see ACTUAL column names. Use only column names that exist in the schema.",
            "unsupported_function": "CRITICAL: This function is not supported in SQL Server. Use alternative functions or manual calculation.",
            "type_conversion_error": "CRITICAL: Check SAMPLE DATA to determine if date column is STRING or DATE type. Use LIKE/SUBSTRING for string dates, NOT date functions.",
            "timeout_error": "Query execution timed out. Try simplifying the query or adding more specific filters.",
            "alias_undefined": "CRITICAL: If you use alias like 't.' or 'e.', you MUST define it in FROM clause first: FROM [schema].[TableName] AS alias_name",
            "unicode_string_error": "CRITICAL: For SQL Server, use N'...' prefix for ANY string containing non-ASCII characters. Check SAMPLE DATA to see actual values.",
            "syntax_error": "SQL syntax error. Check the query structure and ensure proper SQL Server syntax.",
            "empty_results": "Query returned no results. Use actual data values from SAMPLE DATA section in WHERE clauses to ensure results are returned.",
            "attribute_error": "Internal error. Please check the query structure.",
            "unknown_error": "Unknown error occurred. Please review the error message and fix the query."
        }
        return guidance_map.get(error_pattern)
    
    async def execute_sql(
        self,
        sql: str,
        snapshot_id: int,
        session: AsyncSession,
        validate_results: bool = True,
        timeout_seconds: int = 30
    ) -> Tuple[bool, Optional[Any], Optional[str]]:
        """Execute SQL query and return result with validation
        
        Args:
            sql: SQL query to execute
            snapshot_id: Schema snapshot ID
            session: Database session
            validate_results: Whether to validate result quality
            timeout_seconds: Maximum time to wait for query execution (default: 30 seconds)
        """
        logger.info(f"[MATURATION_ENGINE] Executing SQL: {sql[:100]}...")
        
        # Get database type first
        db_type = await self.get_database_type(snapshot_id, session)
        
        # Transform SQL for SQL Server compatibility (fix strftime and other issues)
        if db_type.lower() == "sqlserver":
            original_sql = sql
            sql = self._transform_sql_for_sqlserver(sql)
            if sql != original_sql:
                logger.info(f"[MATURATION_ENGINE] SQL transformed for SQL Server compatibility")
        
        # Validate alias usage before execution
        alias_valid, alias_error = self._validate_sql_aliases(sql)
        if not alias_valid:
            logger.warning(f"[MATURATION_ENGINE] Alias validation failed: {alias_error}")
            return False, None, alias_error
        
        # Validate Unicode strings for SQL Server
        if db_type.lower() == "sqlserver":
            unicode_valid, unicode_error = self._validate_unicode_strings(sql)
            if not unicode_valid:
                logger.warning(f"[MATURATION_ENGINE] Unicode string validation failed: {unicode_error}")
                return False, None, unicode_error
        
        db_connector = None
        try:
            db_connector = await create_db_connector_for_snapshot(snapshot_id, session)
            if not db_connector:
                return False, None, "Could not create database connector"
            
            await db_connector.connect()
            
            # Execute query with timeout
            async def execute_with_timeout():
                return await db_connector.execute_query(sql, limit=100)  # Limit results
            
            try:
                result = await asyncio.wait_for(execute_with_timeout(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.error(f"[MATURATION_ENGINE] Query execution timed out after {timeout_seconds} seconds")
                return False, None, f"Query execution timed out after {timeout_seconds} seconds"
            
            if result and len(result) > 0:
                # Enhanced validation results quality
                if validate_results:
                    meaningful_rows = 0
                    total_values = 0
                    non_null_values = 0
                    
                    for row in result:
                        row_has_meaningful = False
                        for col, val in row.items():
                            total_values += 1
                            if val is not None:
                                non_null_values += 1
                                val_str = str(val).strip()
                                # Check if value is meaningful (not empty, not "null" string)
                                if val_str != "" and val_str.lower() not in ["null", "none", "nan"]:
                                    row_has_meaningful = True
                        if row_has_meaningful:
                            meaningful_rows += 1
                    
                    # Quality metrics
                    meaningful_ratio = meaningful_rows / len(result) if result else 0
                    non_null_ratio = non_null_values / total_values if total_values > 0 else 0
                    
                    # Validation rules
                    if meaningful_rows == 0:
                        logger.warning("[MATURATION_ENGINE] Query returned rows but all values are NULL or empty")
                        return False, result, "Query returned empty or NULL results - no meaningful data"
                    
                    if meaningful_ratio < 0.5:  # Less than 50% meaningful rows
                        logger.warning(
                            f"[MATURATION_ENGINE] Query returned {len(result)} rows but only {meaningful_rows} ({meaningful_ratio:.1%}) have meaningful data"
                        )
                        # Still return success but log warning
                    
                    if non_null_ratio < 0.3:  # Less than 30% non-null values
                        logger.warning(
                            f"[MATURATION_ENGINE] Query returned {len(result)} rows but only {non_null_ratio:.1%} non-null values - may indicate data quality issues"
                        )
                    
                    # Check if result count is reasonable
                    if len(result) > 1000:
                        logger.warning(f"[MATURATION_ENGINE] Query returned {len(result)} rows - very large result set, may need filtering")
                    
                    if len(result) == 1 and meaningful_ratio < 1.0:
                        logger.warning("[MATURATION_ENGINE] Query returned only 1 row with no meaningful data - may need better filters")
                
                logger.info(f"[MATURATION_ENGINE] Query executed successfully, returned {len(result)} rows")
                return True, result, None
            else:
                logger.warning("[MATURATION_ENGINE] Query executed but returned no results")
                if validate_results:
                    return False, [], "Query returned no results - may need different filters based on actual data"
                return True, [], None  # Empty result is still success if validation disabled
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[MATURATION_ENGINE] Query execution failed: {error_msg}")
            return False, None, error_msg
        finally:
            if db_connector:
                try:
                    await db_connector.disconnect()
                except:
                    pass
    
    async def process_question(
        self,
        question: str,
        use_case: UseCase,
        context: MaturationContext,
        snapshot_id: int,
        language: str = "persian",
        session: AsyncSession = None
    ) -> GeneratedQuestion:
        """Process a single question: generate SQL, execute, retry if needed"""
        logger.info(f"[MATURATION_ENGINE] Processing question: {question[:50]}...")
        
        generated_question = GeneratedQuestion(question_text=question)
        
        while generated_question.retry_count <= generated_question.max_retries:
            try:
                # Generate SQL
                previous_error = generated_question.execution_error if generated_question.retry_count > 0 else None
                generated_question.generated_sql = await self.generate_sql(
                    question,
                    use_case,
                    context,
                    snapshot_id,
                    language,
                    previous_error,
                    session
                )
                
                # Validate alias usage before execution
                alias_valid, alias_error = self._validate_sql_aliases(generated_question.generated_sql)
                if not alias_valid:
                    logger.warning(f"[MATURATION_ENGINE] Alias validation failed before execution: {alias_error}")
                    generated_question.execution_error = alias_error
                    generated_question.retry_count += 1
                    if generated_question.retry_count <= generated_question.max_retries:
                        logger.info(f"[MATURATION_ENGINE] Retrying due to alias error (attempt {generated_question.retry_count}/{generated_question.max_retries})")
                        generated_question.execution_status = "retrying"
                        # Update error message for next retry
                        generated_question.execution_error = f"{alias_error}. CRITICAL: If you use alias like 't.' or 'e.', you MUST define it in FROM clause first: FROM [schema].[TableName] AS alias_name"
                        await asyncio.sleep(1)
                        continue
                    else:
                        logger.warning(f"[MATURATION_ENGINE] Question failed after {generated_question.max_retries} attempts due to alias errors")
                        generated_question.execution_status = "error"
                        return generated_question
                
                # Validate Unicode strings for SQL Server
                db_type = await self.get_database_type(snapshot_id, session)
                if db_type.lower() == "sqlserver":
                    unicode_valid, unicode_error = self._validate_unicode_strings(generated_question.generated_sql)
                    if not unicode_valid:
                        logger.warning(f"[MATURATION_ENGINE] Unicode string validation failed before execution: {unicode_error}")
                        generated_question.execution_error = unicode_error
                        generated_question.retry_count += 1
                        if generated_question.retry_count <= generated_question.max_retries:
                            logger.info(f"[MATURATION_ENGINE] Retrying due to Unicode string error (attempt {generated_question.retry_count}/{generated_question.max_retries})")
                            generated_question.execution_status = "retrying"
                            # Update error message for next retry
                            generated_question.execution_error = f"{unicode_error}. CRITICAL: For SQL Server, use N'...' prefix for ANY string containing non-ASCII characters. Check SAMPLE DATA to see actual values and use N prefix if they contain non-ASCII characters."
                            await asyncio.sleep(1)
                            continue
                        else:
                            logger.warning(f"[MATURATION_ENGINE] Question failed after {generated_question.max_retries} attempts due to Unicode string errors")
                            generated_question.execution_status = "error"
                            return generated_question
                
                # Execute SQL with validation
                success, result, error = await self.execute_sql(
                    generated_question.generated_sql,
                    snapshot_id,
                    session,
                    validate_results=True  # Enable result validation
                )
                
                if success:
                    # Additional validation: check if result is meaningful
                    if result and len(result) > 0:
                        generated_question.execution_status = "success"
                        generated_question.execution_result = result
                        generated_question.execution_error = None
                        logger.info(f"[MATURATION_ENGINE] Question processed successfully with {len(result)} meaningful rows")
                        return generated_question
                    else:
                        # Empty result - retry with better filters
                        generated_question.execution_status = "error"
                        generated_question.execution_error = "Query returned no results - need to adjust filters based on actual data"
                        generated_question.retry_count += 1
                        
                        if generated_question.retry_count <= generated_question.max_retries:
                            logger.info(f"[MATURATION_ENGINE] Retrying question due to empty results (attempt {generated_question.retry_count}/{generated_question.max_retries})")
                            generated_question.execution_status = "retrying"
                            # Update error message for next retry - will be passed as previous_error
                            generated_question.execution_error = "Query returned no results. Use actual data values from SAMPLE DATA section in WHERE clauses to ensure results are returned."
                            await asyncio.sleep(1)  # Brief delay before retry
                        else:
                            logger.warning(f"[MATURATION_ENGINE] Question failed after {generated_question.max_retries} attempts (empty results)")
                    return generated_question
                else:
                    # Execution failed - learn from error pattern
                    error_pattern = self._extract_error_pattern(error)
                    if error_pattern:
                        self._error_patterns[error_pattern] = self._error_patterns.get(error_pattern, 0) + 1
                        logger.debug(f"[MATURATION_ENGINE] Error pattern detected: {error_pattern} (count: {self._error_patterns[error_pattern]})")
                    
                    generated_question.execution_status = "error"
                    generated_question.execution_error = error
                    generated_question.retry_count += 1
                    
                    if generated_question.retry_count <= generated_question.max_retries:
                        logger.info(f"[MATURATION_ENGINE] Retrying question (attempt {generated_question.retry_count}/{generated_question.max_retries})")
                        generated_question.execution_status = "retrying"
                        # Use error pattern to provide better guidance in retry
                        if error_pattern:
                            pattern_guidance = self._get_error_pattern_guidance(error_pattern)
                            if pattern_guidance:
                                generated_question.execution_error = f"{error}. {pattern_guidance}"
                        await asyncio.sleep(1)  # Brief delay before retry
                    else:
                        logger.warning(f"[MATURATION_ENGINE] Question failed after {generated_question.max_retries} attempts")
                        return generated_question
                        
            except Exception as e:
                # Enhanced exception handling with error pattern learning
                error_msg = str(e)
                error_pattern = self._extract_error_pattern(error_msg)
                
                if error_pattern:
                    self._error_patterns[error_pattern] = self._error_patterns.get(error_pattern, 0) + 1
                    logger.debug(f"[MATURATION_ENGINE] Exception error pattern detected: {error_pattern} (count: {self._error_patterns[error_pattern]})")
                
                generated_question.execution_error = error_msg
                generated_question.retry_count += 1
                
                if generated_question.retry_count > generated_question.max_retries:
                    logger.error(f"[MATURATION_ENGINE] Question processing failed after {generated_question.max_retries} attempts: {error_msg}", exc_info=True)
                    generated_question.execution_status = "error"
                    return generated_question
                
                # Use error pattern guidance for retry
                if error_pattern:
                    pattern_guidance = self._get_error_pattern_guidance(error_pattern)
                    if pattern_guidance:
                        generated_question.execution_error = f"{error_msg}. {pattern_guidance}"
                
                logger.warning(f"[MATURATION_ENGINE] Retrying question after exception (attempt {generated_question.retry_count}/{generated_question.max_retries}): {error_msg[:100]}")
                generated_question.execution_status = "retrying"
                await asyncio.sleep(1)
        
        return generated_question


# Singleton instance
maturation_engine = MaturationEngine()

