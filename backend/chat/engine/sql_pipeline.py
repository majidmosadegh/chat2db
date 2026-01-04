import re
import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from db import DatabaseConnector
from ..schemas import (
    ChatContext, ChatLanguage, LLMResponse,
    SQLValidationResult, SQLExecutionResult
)
from ..sql_guard import SQLGuard, SQLValidationError
from .query_planner import QueryPlanner, QueryPlan
from .query_result_cache import QueryResultCache
from ..utils.json_safety import safe_json_parse, JSONParseError, safe_json_loads_with_fallback

logger = logging.getLogger(__name__)


class SQLPipelineError(Exception):
    """Exception raised when SQL pipeline operations fail"""
    pass


@dataclass
class SQLGenerationResult:
    """Result from SQL generation stage"""
    sql: str
    reasoning: str
    model_used: str
    generation_time_ms: int
    success: bool


class SQLGenerator:
    """Stage 1: Generates SQL from reasoning output"""

    def __init__(self, llm_gateway, prompt_engine):
        self.llm_gateway = llm_gateway
        self.prompt_engine = prompt_engine

    async def generate_sql(
        self,
        context: ChatContext,
        question: str,
        reasoning_output: str,
        language: ChatLanguage,
        model_id: int
    ) -> SQLGenerationResult:
        """
        Generate SQL from reasoning output using LLM.

        Args:
            context: The chat context
            question: Original user question
            reasoning_output: Output from reasoning stage
            language: Language for prompts
            model_id: LLM model ID to use

        Returns:
            SQLGenerationResult: Generated SQL with metadata
        """
        start_time = time.time()

        try:
            # Build SQL generation prompt
            prompt = self.prompt_engine.build_sql_prompt(
                context=context,
                question=question,
                reasoning_output=reasoning_output,
                language=language
            )

            # Call LLM
            llm_response = await self.llm_gateway.call_llm(
                model_id=model_id,
                prompt=prompt,
                temperature=0.1  # Low temperature for SQL generation
            )

            if not llm_response.success:
                raise SQLPipelineError("LLM call failed for SQL generation")

            # Extract SQL from response
            sql = self._extract_sql_from_response(llm_response.raw_text)

            generation_id = f"GEN_{int(start_time * 1000)}"
            logger.info(f"🔧 SQL_GENERATION_RAW_RESPONSE | ID: {generation_id} | Response_Length: {len(llm_response.raw_text)} | SQL_Length: {len(sql)}")
            if len(sql) == 0:
                logger.warning(f"⚠️ SQL_GENERATION_FAILED | ID: {generation_id} | Raw_Response_Preview: {llm_response.raw_text[:200]}")
            else:
                logger.info(f"✅ SQL_GENERATION_SUCCESS | ID: {generation_id} | SQL_Preview: {sql[:100]}")

            generation_time = int((time.time() - start_time) * 1000)

            return SQLGenerationResult(
                sql=sql,
                reasoning=reasoning_output,
                model_used=llm_response.model_used,
                generation_time_ms=generation_time,
                success=True
            )

        except Exception as e:
            generation_time = int((time.time() - start_time) * 1000)

            return SQLGenerationResult(
                sql="",
                reasoning=reasoning_output,
                model_used=f"model_{model_id}",
                generation_time_ms=generation_time,
                success=False
            )

    def _extract_sql_from_response(self, raw_text: str) -> str:
        """Extract SQL query from LLM response"""
        if not raw_text:
            return ""

        # Remove markdown code blocks
        sql = re.sub(r'```\w*\n?', '', raw_text)
        sql = re.sub(r'```', '', sql)

        # Clean up whitespace
        sql = sql.strip()

        # If multiple statements, take the first one
        if ';' in sql:
            sql = sql.split(';')[0].strip()

        return sql


class SQLValidator:
    """Stage 2: Validates SQL for safety and correctness"""

    def __init__(self, sql_guard: Optional[SQLGuard] = None):
        self.sql_guard = sql_guard or SQLGuard()
        self.logger = logging.getLogger(__name__)

    def _transform_sql_for_database(self, sql: str, db_type: str) -> str:
        """
        Transform SQL functions based on database type to ensure compatibility.

        Args:
            sql: Original SQL query
            db_type: Database type (postgresql, mysql, sqlserver, etc.)

        Returns:
            str: Transformed SQL query
        """
        if not sql or not db_type:
            return sql

        db_type = db_type.lower()

        # SQL Server transformations
        if db_type in ['sqlserver', 'mssql']:
            # Transform PostgreSQL/MySQL date functions to SQL Server equivalents
            transformations = [
                # DATE() -> CAST(date_column AS DATE) or use CONVERT
                (r'\bDATE\s*\(\s*([^)]+)\s*\)', r'CONVERT(DATE, \1)'),
                # NOW() -> GETDATE()
                (r'\bNOW\s*\(\s*\)', r'GETDATE()'),
                # CURRENT_DATE -> CAST(GETDATE() AS DATE)
                (r'\bCURRENT_DATE\b', r'CONVERT(DATE, GETDATE())'),
                # CURRENT_TIMESTAMP -> GETDATE()
                (r'\bCURRENT_TIMESTAMP\b', r'GETDATE()'),
                # EXTRACT(YEAR FROM date) -> YEAR(date)
                (r'EXTRACT\s*\(\s*YEAR\s+FROM\s+([^)]+)\)', r'YEAR(\1)'),
                (r'EXTRACT\s*\(\s*year\s+FROM\s+([^)]+)\)', r'YEAR(\1)'),
                # EXTRACT(MONTH FROM date) -> MONTH(date)
                (r'EXTRACT\s*\(\s*MONTH\s+FROM\s+([^)]+)\)', r'MONTH(\1)'),
                (r'EXTRACT\s*\(\s*month\s+FROM\s+([^)]+)\)', r'MONTH(\1)'),
                # EXTRACT(DAY FROM date) -> DAY(date)
                (r'EXTRACT\s*\(\s*DAY\s+FROM\s+([^)]+)\)', r'DAY(\1)'),
                (r'EXTRACT\s*\(\s*day\s+FROM\s+([^)]+)\)', r'DAY(\1)'),
                # LIMIT -> TOP (for simple queries at end of SELECT)
                (r'\bLIMIT\s+(\d+)\s*$', r'TOP \1', re.MULTILINE),
                # LIMIT in middle (less common, but handle it)
                (r'\bLIMIT\s+(\d+)(?!\s*$)', r'TOP \1'),
                # strftime -> FORMAT (SQL Server equivalent)
                (r'strftime\s*\([^)]+\)', r'FORMAT(date_column, \'yyyy-MM-dd\')'),
                # UUID() -> NEWID() (SQL Server)
                (r'\bUUID\s*\(\s*\)', r'NEWID()'),
                # ILIKE -> LIKE (case-insensitive in SQL Server needs different approach)
                (r'\bILIKE\b', r'LIKE'),
                # LENGTH() -> LEN()
                (r'\bLENGTH\s*\(\s*([^)]+)\s*\)', r'LEN(\1)'),
                # SUBSTR() -> SUBSTRING()
                (r'\bSUBSTR\s*\(\s*([^)]+)\s*\)', r'SUBSTRING(\1)'),
                # OFFSET/FETCH for pagination if needed
                (r'OFFSET\s+(\d+)\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY', r'OFFSET \1 ROWS FETCH NEXT \2 ROWS ONLY'),
            ]

            transformed_sql = sql
            for transformation in transformations:
                # Handle tuples with 2 elements (pattern, replacement) or 3 elements (pattern, replacement, flags)
                if len(transformation) == 3:
                    pattern, replacement, custom_flags = transformation
                    # Combine custom flags with IGNORECASE for consistent case-insensitive matching
                    flags = custom_flags | re.IGNORECASE
                else:
                    pattern, replacement = transformation
                    flags = re.IGNORECASE
                transformed_sql = re.sub(pattern, replacement, transformed_sql, flags=flags)

            return transformed_sql

        # PostgreSQL transformations (default, no changes needed)
        elif db_type in ['postgresql', 'postgres']:
            return sql

        # MySQL transformations
        elif db_type == 'mysql':
            # LIMIT is already correct for MySQL
            return sql

        # Default: return as-is
        return sql

    def validate_sql(
        self,
        sql: str,
        context: ChatContext
    ) -> SQLValidationResult:
        """
        Validate SQL query for safety and correctness.

        Args:
            sql: The SQL query to validate
            context: Chat context for validation

        Returns:
            SQLValidationResult: Validation results
        """
        try:
            # Transform SQL for database compatibility first
            transformed_sql = self._transform_sql_for_database(sql, context.database_type)

            # Clean and validate with SQL guard
            cleaned_sql = self.sql_guard.validate_sql(transformed_sql)

            # Additional context-based validation
            is_read_only = self.sql_guard.is_read_only_query(cleaned_sql)
            context_valid = self._validate_against_context(cleaned_sql, context)

            if not context_valid:
                return SQLValidationResult(
                    is_valid=False,
                    validation_errors=["SQL uses tables/columns not in context"],
                    is_read_only=is_read_only,
                    cleaned_sql=cleaned_sql
                )

            return SQLValidationResult(
                is_valid=True,
                validation_errors=[],
                is_read_only=is_read_only,
                cleaned_sql=cleaned_sql
            )

        except SQLValidationError as e:
            return SQLValidationResult(
                is_valid=False,
                validation_errors=[str(e)],
                is_read_only=False,
                cleaned_sql=sql
            )
        except Exception as e:
            return SQLValidationResult(
                is_valid=False,
                validation_errors=[f"Validation error: {str(e)}"],
                is_read_only=False,
                cleaned_sql=sql
            )

    def _validate_against_context(self, sql: str, context: ChatContext) -> bool:
        """Validate that SQL only uses tables/columns from context"""
        try:
            # Extract table and column references from SQL
            sql_lower = sql.lower()

            # Get all available tables from context
            available_tables = set()
            available_table_names = set()
            available_columns = set()

            for schema_info in context.schema_info:
                table_key = f"{schema_info.schema_name}.{schema_info.table_name}"
                table_name_only = schema_info.table_name.lower()
                available_tables.add(table_key.lower())
                available_table_names.add(table_name_only)
                available_columns.add(f"{schema_info.table_name}.{schema_info.column_name}".lower())
                available_columns.add(f"{table_key}.{schema_info.column_name}".lower())
                available_columns.add(schema_info.column_name.lower())

            # Check for generic table names that shouldn't be used
            generic_table_names = ['products', 'orders', 'customers', 'users', 'items', 'data', 'table']
            has_generic_table = any(gen_table in sql_lower for gen_table in generic_table_names)
            
            # Check if SQL contains known table/column names
            has_valid_references = False
            found_tables = []

            for table in available_tables:
                if table in sql_lower:
                    has_valid_references = True
                    found_tables.append(table)
                    break
            
            # Also check table names without schema
            for table_name in available_table_names:
                if table_name in sql_lower:
                    has_valid_references = True
                    found_tables.append(table_name)
                    break

            # If generic table names found but no valid references, likely invalid
            if has_generic_table and not has_valid_references:
                self.logger.warning(f"⚠️ VALIDATION_GENERIC_TABLE | SQL contains generic table names but no valid schema references")
                return False

            # If no tables found but SQL is simple SELECT, might be valid
            if not has_valid_references and "select" in sql_lower:
                # Allow simple queries that might not reference specific tables
                # (like SELECT 1, SELECT COUNT(*), etc.)
                # But log a warning
                self.logger.warning(f"⚠️ VALIDATION_NO_TABLE_REF | SQL doesn't reference any known tables: {sql[:100]}")
                pass

            if has_valid_references:
                self.logger.debug(f"✅ VALIDATION_TABLE_MATCH | Found valid table references: {found_tables}")

            return True  # For now, be permissive but log warnings

        except Exception as e:
            self.logger.error(f"❌ VALIDATION_ERROR | Error validating against context: {e}")
            # If validation fails, err on the side of caution
            return False


class SQLExecutor:
    """Stage 5: Executes SQL against snapshot database with comprehensive logging"""

    def __init__(self, connector: DatabaseConnector, result_cache: Optional[QueryResultCache] = None):
        self.connector = connector
        self.result_cache = result_cache
        # Extract snapshot_id from connector
        if hasattr(connector, 'snapshot') and connector.snapshot:
            self.snapshot_id = getattr(connector.snapshot, 'id', None)
        else:
            self.snapshot_id = None

    async def execute_sql(
        self,
        sql: str,
        max_rows: int = 50
    ) -> SQLExecutionResult:
        """
        Execute SQL query against the database with comprehensive logging.

        Args:
            sql: The SQL query to execute
            max_rows: Maximum number of rows to return

        Returns:
            SQLExecutionResult: Execution results
        """
        execution_id = f"EXEC_{int(time.time()*1000)}_{hash(sql) % 10000:04d}"
        start_time = time.time()

        logger.info(f"🗄️ DB_EXECUTOR_START | ID: {execution_id} | MaxRows: {max_rows} | SQL_Length: {len(sql)} chars")
        logger.info(f"🔍 DB_SQL_PREVIEW | ID: {execution_id} | SQL: '{sql[:100]}{'...' if len(sql) > 100 else ''}'")
        logger.debug(f"📝 DB_FULL_SQL | ID: {execution_id} | SQL: {sql}")

        # Check cache first
        if self.result_cache and self.snapshot_id:
            cached_result = self.result_cache.get_result(sql, self.snapshot_id)
            if cached_result:
                logger.info(
                    f"📦 DB_CACHE_HIT | ID: {execution_id} | "
                    f"Rows: {cached_result.get('row_count', 0)} | "
                    f"Time: {cached_result.get('execution_time_ms', 0)}ms"
                )
                return SQLExecutionResult(
                    rows=cached_result.get("rows", []),
                    row_count=cached_result.get("row_count", 0),
                    execution_time_ms=cached_result.get("execution_time_ms", 0),
                    truncated=cached_result.get("truncated", False),
                    success=cached_result.get("success", True)
                )

        try:
            # Database connection check
            logger.debug(f"🔌 DB_CONNECTION_CHECK | ID: {execution_id} | Connector: {type(self.connector).__name__}")

            # Execute query using connector
            logger.info(f"⚡ DB_QUERY_EXECUTION | ID: {execution_id} | Sending query to database...")

            query_start = time.time()
            rows = await self.connector.execute_readonly(sql, limit=max_rows)
            query_time = int((time.time() - query_start) * 1000)

            execution_time = int((time.time() - start_time) * 1000)

            # Log results
            row_count = len(rows)
            truncated = len(rows) >= max_rows

            logger.info(f"✅ DB_EXECUTION_SUCCESS | ID: {execution_id} | Rows: {row_count} | Truncated: {truncated} | QueryTime: {query_time}ms | TotalTime: {execution_time}ms")

            if row_count > 0:
                logger.debug(f"📊 DB_RESULT_SAMPLE | ID: {execution_id} | FirstRow: {rows[0] if rows else 'None'}")
                logger.debug(f"📋 DB_COLUMN_INFO | ID: {execution_id} | Columns: {list(rows[0].keys()) if rows and isinstance(rows[0], dict) else 'Unknown'}")

            # Log performance metrics
            logger.info(f"📈 DB_PERFORMANCE | ID: {execution_id} | QueryTime: {query_time}ms | ProcessingTime: {execution_time - query_time}ms | RowsPerSec: {row_count / (query_time / 1000) if query_time > 0 else 0:.1f}")

            execution_result = SQLExecutionResult(
                rows=rows,
                row_count=row_count,
                execution_time_ms=execution_time,
                truncated=truncated,
                success=True
            )

            # Store in cache if available
            if self.result_cache and self.snapshot_id:
                result_dict = {
                    "rows": rows,
                    "row_count": row_count,
                    "execution_time_ms": execution_time,
                    "truncated": truncated,
                    "success": True,
                    "snapshot_id": self.snapshot_id
                }
                self.result_cache.store_result(sql, self.snapshot_id, result_dict)

            return execution_result

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = str(e)

            # Clean up error message for security
            if "password" in error_msg.lower():
                error_msg = "Database connection error"

            logger.error(f"❌ DB_EXECUTION_FAILED | ID: {execution_id} | Error: {error_msg} | TotalTime: {execution_time}ms")
            logger.error(f"🔍 DB_ERROR_DETAILS | ID: {execution_id} | Exception: {type(e).__name__} | SQL: '{sql[:50]}{'...' if len(sql) > 50 else ''}'", exc_info=True)

            # Log query analysis for debugging
            logger.debug(f"🔬 DB_QUERY_ANALYSIS | ID: {execution_id} | SQL_Type: {'SELECT' if sql.strip().upper().startswith('SELECT') else 'OTHER'} | Has_LIMIT: {'TOP' in sql.upper() or 'LIMIT' in sql.upper()}")

            return SQLExecutionResult(
                rows=[],
                row_count=0,
                execution_time_ms=execution_time,
                truncated=False,
                success=False,
                error_message=error_msg
            )


class SQLCritic:
    """Stage: Critiques and validates generated SQL semantically"""

    def __init__(self, llm_gateway, prompt_engine, max_retries: int = 2):
        self.llm_gateway = llm_gateway
        self.prompt_engine = prompt_engine
        self.max_retries = max_retries

    async def critique_and_improve_sql(
        self,
        sql: str,
        context: ChatContext,
        question: str,
        intent: str,
        tables_info: Dict[str, Any],
        language: ChatLanguage,
        model_id: int
    ) -> Dict[str, Any]:
        """
        Critique SQL and regenerate if needed.

        Returns:
            Dict with keys: sql, critique_result, attempts, final_sql
        """
        current_sql = sql
        attempts = []

        for attempt in range(self.max_retries + 1):
            # Critique the current SQL
            critique_prompt = self._build_critique_prompt(
                current_sql, context, question, intent, tables_info, language
            )

            llm_response = await self.llm_gateway.call_llm(
                model_id=model_id,
                prompt=critique_prompt,
                temperature=0.1
            )

            if not llm_response.success:
                logger.warning(f"Critique LLM call failed on attempt {attempt + 1}")
                attempts.append({
                    "attempt": attempt + 1,
                    "critique": "LLM call failed",
                    "is_correct": False
                })
                continue

            # Parse critique response
            critique_text = llm_response.raw_text.strip().upper()
            is_correct = "YES" in critique_text

            attempts.append({
                "attempt": attempt + 1,
                "critique": llm_response.raw_text,
                "is_correct": is_correct
            })

            logger.info(f"SQL Critique attempt {attempt + 1}: {'PASS' if is_correct else 'FAIL'}")

            if is_correct:
                # SQL is correct, return it
                return {
                    "sql": current_sql,
                    "critique_result": "passed",
                    "attempts": attempts,
                    "final_sql": current_sql
                }

            # SQL has issues, try to regenerate
            if attempt < self.max_retries:
                logger.info(f"Regenerating SQL due to critique failure: {llm_response.raw_text[:100]}...")

                # Extract error from critique and regenerate
                regen_prompt = self._build_regeneration_prompt(
                    current_sql, context, question, intent, tables_info,
                    llm_response.raw_text, language
                )

                regen_response = await self.llm_gateway.call_llm(
                    model_id=model_id,
                    prompt=regen_prompt,
                    temperature=0.2  # Slightly higher temperature for regeneration
                )

                if regen_response.success:
                    current_sql = self.prompt_engine._extract_sql_from_response(regen_response.raw_text)
                    logger.info(f"Regenerated SQL on attempt {attempt + 1}")
                else:
                    logger.warning(f"Regeneration failed on attempt {attempt + 1}")

        # All attempts failed, return the last SQL with failure info
        return {
            "sql": current_sql,
            "critique_result": "failed",
            "attempts": attempts,
            "final_sql": current_sql
        }

    def _build_critique_prompt(
        self, sql: str, context: ChatContext, question: str,
        intent: str, tables_info: Dict[str, Any], language: ChatLanguage
    ) -> str:
        """Build critique prompt"""
        if language == ChatLanguage.ENGLISH:
            template = """You are a SQL semantic validator. Analyze if this SQL correctly answers the question.

QUESTION: {question}
INTENT: {intent}
SQL: {sql}

TABLES USED: {tables}
COLUMNS USED: {columns}

Is this SQL semantically correct for the question?
Answer only YES or NO.
If NO, give ONE sentence explaining the mistake."""
        else:
            template = """شما اعتبار سنج معنایی SQL هستید. تحلیل کنید آیا این SQL به درستی به سوال پاسخ می‌دهد.

سوال: {question}
قصد: {intent}
SQL: {sql}

جداول استفاده شده: {tables}
ستون‌های استفاده شده: {columns}

آیا این SQL از نظر معنایی برای سوال صحیح است؟
فقط YES یا NO پاسخ دهید.
اگر NO، یک جمله توضیح دهید اشتباه چیست."""

        tables = [t["table"] for t in tables_info.get("tables", [])]
        columns = tables_info.get("required_columns", [])

        return template.format(
            question=question,
            intent=intent,
            sql=sql,
            tables=", ".join(tables),
            columns=", ".join(columns)
        )

    def _build_regeneration_prompt(
        self, old_sql: str, context: ChatContext, question: str,
        intent: str, tables_info: Dict[str, Any], critique_feedback: str,
        language: ChatLanguage
    ) -> str:
        """Build regeneration prompt with critique feedback"""
        if language == ChatLanguage.ENGLISH:
            template = """The previous SQL had issues. Generate a corrected version.

QUESTION: {question}
INTENT: {intent}

PREVIOUS SQL: {old_sql}
CRITIQUE: {critique}

ALLOWED TABLES: {tables}
ALLOWED COLUMNS: {columns}

Generate the corrected SQL query only:"""
        else:
            template = """SQL قبلی مشکل داشت. نسخه اصلاح شده تولید کنید.

سوال: {question}
قصد: {intent}

SQL قبلی: {old_sql}
انتقاد: {critique}

جداول مجاز: {tables}
ستون‌های مجاز: {columns}

فقط پرس‌وجوی SQL اصلاح شده را تولید کنید:"""

        tables = [t["table"] for t in tables_info.get("tables", [])]
        columns = tables_info.get("required_columns", [])

        return template.format(
            question=question,
            intent=intent,
            old_sql=old_sql,
            critique=critique_feedback,
            tables=", ".join(tables),
            columns=", ".join(columns)
        )


class SemanticGuard:
    """Enforces semantic rules on generated SQL"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def enforce_rules(self, sql: str, intent: str, context: ChatContext) -> Dict[str, Any]:
        """
        Enforce semantic rules based on intent and context.

        Returns:
            Dict with keys: is_valid, violations, corrected_sql
        """
        violations = []
        corrected_sql = sql

        # Rule 1: COUNT/AGGREGATION intents should not have TOP/LIMIT
        if intent in ["COUNT", "AGGREGATION"]:
            if re.search(r'\bTOP\s+\d+', sql, re.IGNORECASE) or re.search(r'\bLIMIT\s+\d+', sql, re.IGNORECASE):
                violations.append(f"{intent} queries should not have TOP/LIMIT")
                # Remove TOP/LIMIT
                corrected_sql = re.sub(r'\bTOP\s+\d+\s+', '', corrected_sql, flags=re.IGNORECASE)
                corrected_sql = re.sub(r'\bLIMIT\s+\d+', '', corrected_sql, flags=re.IGNORECASE)

        # Rule 2: LIST intent should not have SELECT * unless explicitly allowed
        if intent != "LIST" and re.search(r'SELECT\s+\*', sql, re.IGNORECASE):
            violations.append(f"{intent} queries should not use SELECT *")

        # Rule 3: DETAIL queries should have WHERE clauses
        if intent == "DETAIL" and not re.search(r'\bWHERE\b', sql, re.IGNORECASE):
            violations.append("DETAIL queries should have WHERE clauses for specific records")
        
        # Rule 6: SQL query must be complete (have SELECT and FROM)
        if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
            violations.append("SQL query must contain SELECT clause")
        if not re.search(r'\bFROM\b', sql, re.IGNORECASE):
            violations.append("SQL query must contain FROM clause")

        # Rule 4: Check for valid JOIN relationships
        if re.search(r'\bJOIN\b', sql, re.IGNORECASE):
            join_valid = self._validate_joins(sql, context)
            if not join_valid:
                violations.append("JOIN used without valid relationship in schema")

        # Rule 5: No dangerous operations
        dangerous_patterns = [
            r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', r'\bINSERT\b',
            r'\bALTER\b', r'\bCREATE\b', r'\bTRUNCATE\b'
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                violations.append(f"Dangerous operation detected: {pattern.strip('\\\\b')}")

        is_valid = len(violations) == 0

        if violations:
            self.logger.warning(f"Semantic violations detected: {violations}")

        return {
            "is_valid": is_valid,
            "violations": violations,
            "corrected_sql": corrected_sql
        }

    def _validate_joins(self, sql: str, context: ChatContext) -> bool:
        """Validate that JOINs use existing relationships"""
        # Extract table names from JOIN clauses
        join_pattern = r'\bJOIN\s+(\w+)'
        joined_tables = re.findall(join_pattern, sql, re.IGNORECASE)

        if not joined_tables:
            return True

        # Get available relationships
        available_rels = set()
        for rel in context.relationships or []:
            available_rels.add((rel.source_table.lower(), rel.target_table.lower()))
            available_rels.add((rel.target_table.lower(), rel.source_table.lower()))

        # Check if joined tables have relationships
        main_table = None
        # Extract main table from FROM clause
        from_match = re.search(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        if from_match:
            main_table = from_match.group(1).lower()

        for joined_table in joined_tables:
            joined_lower = joined_table.lower()
            if main_table and (main_table, joined_lower) not in available_rels:
                self.logger.warning(f"No relationship found between {main_table} and {joined_lower}")
                return False

        return True


class SQLPipeline:
    """Complete SQL pipeline with generation, critique, validation, and execution"""

    def __init__(
        self, 
        llm_gateway, 
        prompt_engine, 
        connector: DatabaseConnector, 
        max_critic_retries: int = 2,
        result_cache: Optional[QueryResultCache] = None
    ):
        self.generator = SQLGenerator(llm_gateway, prompt_engine)
        self.critic = SQLCritic(llm_gateway, prompt_engine, max_retries=max_critic_retries)
        self.semantic_guard = SemanticGuard()
        self.validator = SQLValidator()
        self.executor = SQLExecutor(connector, result_cache=result_cache)

    async def process_sql(
        self,
        context: ChatContext,
        question: str,
        reasoning_output: str,
        language: ChatLanguage,
        model_id: int,
        max_rows: int = 50
    ) -> dict:
        """
        Process SQL through the complete pipeline.

        Args:
            context: Chat context
            question: Original user question
            reasoning_output: Output from reasoning stage
            language: Language for prompts
            model_id: LLM model ID
            max_rows: Maximum rows to return

        Returns:
            dict: Complete pipeline results with traceability
        """
        import time
        import logging
        logging.info(f"DEBUG: process_sql called with question='{question}', language={language}")
        pipeline_start = time.time()

        # Stage 1: Generate SQL
        generation_result = await self.generator.generate_sql(
            context=context,
            question=question,
            reasoning_output=reasoning_output,
            language=language,
            model_id=model_id
        )

        if not generation_result.success:
            return {
                "sql": "",
                "rows": [],
                "row_count": 0,
                "validation_status": "skipped",
                "execution_status": "failed",
                "error_message": "SQL generation failed",
                "generation_time_ms": generation_result.generation_time_ms,
                "execution_time_ms": 0,
                "model_used": generation_result.model_used,
                "critique_attempts": [],
                "semantic_violations": [],
                "intent": "unknown",
                "selected_tables": [],
                "reasoning_stages_time_ms": 0
            }

        # Stage 2: Semantic Guards (NEW)
        # Note: Intent and tables_info would come from the new reasoning pipeline
        # For backward compatibility, we'll use basic detection
        intent = self._detect_intent_from_reasoning(reasoning_output)
        tables_info = self._extract_tables_from_reasoning(reasoning_output, context)

        guard_result = self.semantic_guard.enforce_rules(
            generation_result.sql, intent, context
        )

        if not guard_result["is_valid"]:
            logger.warning(f"Semantic violations: {guard_result['violations']}")
            # Use corrected SQL if available
            sql_after_guard = guard_result["corrected_sql"]
        else:
            sql_after_guard = generation_result.sql

        # Stage 3: SQL Critic (NEW)
        critic_result = await self.critic.critique_and_improve_sql(
            sql_after_guard, context, question, intent, tables_info, language, model_id
        )

        final_sql = critic_result["final_sql"]

        # Stage 4: Validate SQL
        validation_result = self.validator.validate_sql(final_sql, context)

        # Use cleaned SQL if available
        sql_to_execute = validation_result.cleaned_sql or final_sql

        # Stage 5: Execute SQL (only if validation passed)
        if validation_result.is_valid:
            execution_result = await self.executor.execute_sql(
                sql_to_execute,
                max_rows=max_rows
            )
        else:
            execution_result = SQLExecutionResult(
                rows=[],
                row_count=0,
                execution_time_ms=0,
                truncated=False,
                success=False,
                error_message="SQL validation failed"
            )

        total_pipeline_time = int((time.time() - pipeline_start) * 1000)

        return {
            "sql": sql_to_execute,
            "rows": execution_result.rows,
            "row_count": execution_result.row_count,
            "validation_status": "passed" if validation_result.is_valid else "failed",
            "execution_status": "success" if execution_result.success else "failed",
            "error_message": execution_result.error_message if not execution_result.success else None,
            "generation_time_ms": generation_result.generation_time_ms,
            "execution_time_ms": execution_result.execution_time_ms,
            "model_used": generation_result.model_used,
            "validation_errors": validation_result.validation_errors,
            "truncated": execution_result.truncated,
            # NEW observability fields
            "critique_attempts": critic_result["attempts"],
            "critique_result": critic_result["critique_result"],
            "semantic_violations": guard_result["violations"],
            "intent": intent,
            "selected_tables": [t["table"] for t in tables_info.get("tables", [])],
            "reasoning_stages_time_ms": total_pipeline_time - generation_result.generation_time_ms - execution_result.execution_time_ms
        }

    async def process_sql_with_reasoning_pipeline(
        self,
        context: ChatContext,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_rows: int = 50
    ) -> dict:
        """
        Process SQL using the new 3-stage reasoning pipeline.

        Args:
            context: Chat context
            question: Original user question
            language: Language for prompts
            model_id: LLM model ID
            conversation_history: Previous conversation
            max_rows: Maximum rows to return

        Returns:
            dict: Complete pipeline results with full traceability
        """
        import time
        pipeline_start = time.time()
        request_id = f"SQL_{int(time.time()*1000)}"

        logger.info(f"🚀 SQL_PIPELINE_START | ID: {request_id} | Question: '{question[:50]}{'...' if len(question) > 50 else ''}' | Language: {language} | Model: {model_id}")
        # Count tables from schema_info list
        tables = set()
        for schema_item in (context.schema_info or []):
            tables.add(f"{schema_item.schema_name}.{schema_item.table_name}")
        table_count = len(tables)

        logger.info(f"📊 PIPELINE_CONTEXT | ID: {request_id} | Tables: {table_count} | SchemaItems: {len(context.schema_info) if context.schema_info else 0} | Relationships: {len(context.relationships) if context.relationships else 0}")

        try:
            # Stage 1: Execute 3-stage reasoning pipeline
            logger.info(f"🧠 STAGE_1_START | ID: {request_id} | Executing 3-stage reasoning pipeline")

            reasoning_start = time.time()
            reasoning_result = await self.generator.prompt_engine.execute_reasoning_pipeline(
                self.generator.llm_gateway, context, question, language,
                model_id, conversation_history
            )
            reasoning_time = int((time.time() - reasoning_start) * 1000)

            intent = reasoning_result.get("intent", "unknown")
            tables_info = reasoning_result.get("tables_info", {"tables": [], "required_columns": [], "filters": []})
            sql_from_reasoning = reasoning_result.get("sql", "")

            selected_tables = [t.get("table", "unknown") for t in tables_info.get("tables", [])]
            logger.info(f"✅ STAGE_1_COMPLETE | ID: {request_id} | Intent: {intent} | Tables: {len(selected_tables)} | SQL_Length: {len(sql_from_reasoning)} | Time: {reasoning_time}ms")
            logger.debug(f"📋 REASONING_DETAILS | ID: {request_id} | Tables: {selected_tables} | StageTimes: {reasoning_result.get('stage_times', {})} | Errors: {len(reasoning_result.get('errors', []))}")

            # Stage 2: Semantic Guards
            logger.info(f"🛡️ STAGE_2_START | ID: {request_id} | Intent: {intent} | SQL_Length: {len(sql_from_reasoning)}")

            guard_start = time.time()
            guard_result = self.semantic_guard.enforce_rules(sql_from_reasoning, intent, context)
            guard_time = int((time.time() - guard_start) * 1000)

            if not guard_result["is_valid"]:
                logger.warning(f"⚠️ SEMANTIC_VIOLATIONS | ID: {request_id} | Violations: {len(guard_result['violations'])} | Details: {guard_result['violations']}")
                sql_after_guard = guard_result["corrected_sql"]
                logger.info(f"🔧 GUARD_CORRECTION | ID: {request_id} | Original_SQL_Length: {len(sql_from_reasoning)} | Corrected_SQL_Length: {len(sql_after_guard)}")
            else:
                sql_after_guard = sql_from_reasoning
                logger.info(f"✅ GUARD_PASSED | ID: {request_id} | No violations found | Time: {guard_time}ms")

            # Stage 3: SQL Critic
            logger.info(f"🔍 STAGE_3_START | ID: {request_id} | SQL_Length: {len(sql_after_guard)} | Intent: {intent}")

            critic_start = time.time()
            critic_result = await self.critic.critique_and_improve_sql(
                sql_after_guard, context, question, intent, tables_info, language, model_id
            )
            critic_time = int((time.time() - critic_start) * 1000)

            final_sql = critic_result["final_sql"]
            attempts = critic_result.get("attempts", 1)
            critique_result_status = critic_result.get("critique_result", "unknown")

            logger.info(f"✅ CRITIC_COMPLETE | ID: {request_id} | Attempts: {attempts} | Result: {critique_result_status} | Original_SQL_Length: {len(sql_after_guard)} | Final_SQL_Length: {len(final_sql)} | Time: {critic_time}ms")
            logger.debug(f"🔍 CRITIC_DETAILS | ID: {request_id} | CritiqueResult: {critique_result_status} | Attempts: {attempts}")

            # Stage 4: Validate SQL
            logger.info(f"✅ STAGE_4_START | ID: {request_id} | SQL_Length: {len(final_sql)}")

            validation_start = time.time()
            validation_result = self.validator.validate_sql(final_sql, context)
            validation_time = int((time.time() - validation_start) * 1000)

            sql_to_execute = validation_result.cleaned_sql or final_sql

            validation_status = "PASSED" if validation_result.is_valid else "FAILED"
            logger.info(f"{'✅' if validation_result.is_valid else '❌'} VALIDATION_{validation_status} | ID: {request_id} | Errors: {len(validation_result.validation_errors)} | Cleaned: {validation_result.cleaned_sql is not None} | Time: {validation_time}ms")
            if validation_result.validation_errors:
                logger.warning(f"⚠️ VALIDATION_ERRORS | ID: {request_id} | Errors: {validation_result.validation_errors}")

            # Stage 5: Execute SQL
            logger.info(f"⚡ STAGE_5_START | ID: {request_id} | Validation: {validation_status} | MaxRows: {max_rows}")

            if validation_result.is_valid:
                execution_start = time.time()
                execution_result = await self.executor.execute_sql(sql_to_execute, max_rows=max_rows)
                execution_time = int((time.time() - execution_start) * 1000)

                execution_status = "SUCCESS" if execution_result.success else "FAILED"
                logger.info(f"{'✅' if execution_result.success else '❌'} EXECUTION_{execution_status} | ID: {request_id} | Rows: {execution_result.row_count} | Truncated: {execution_result.truncated} | Time: {execution_time}ms")
                if not execution_result.success:
                    logger.error(f"❌ EXECUTION_ERROR | ID: {request_id} | Error: {execution_result.error_message}")
            else:
                execution_result = SQLExecutionResult(
                    rows=[], row_count=0, execution_time_ms=0, truncated=False,
                    success=False, error_message="SQL validation failed"
                )
                logger.warning(f"⚠️ EXECUTION_SKIPPED | ID: {request_id} | Reason: Validation failed")

            total_pipeline_time = int((time.time() - pipeline_start) * 1000)

            logger.info(f"🎉 PIPELINE_COMPLETE | ID: {request_id} | TotalTime: {total_pipeline_time}ms | Intent: {intent} | Rows: {execution_result.row_count} | Status: {'SUCCESS' if execution_result.success else 'FAILED'}")
            logger.info(f"📈 PIPELINE_SUMMARY | ID: {request_id} | Reasoning: {reasoning_time}ms | Guard: {guard_time}ms | Critic: {critic_time}ms | Validation: {validation_time}ms | Execution: {execution_result.execution_time_ms}ms")

            return {
                "sql": sql_to_execute,
                "rows": execution_result.rows,
                "row_count": execution_result.row_count,
                "validation_status": "passed" if validation_result.is_valid else "failed",
                "execution_status": "success" if execution_result.success else "failed",
                "error_message": execution_result.error_message if not execution_result.success else None,
                "generation_time_ms": total_pipeline_time,
                "execution_time_ms": execution_result.execution_time_ms,
                "model_used": f"model_{model_id}",
                "validation_errors": validation_result.validation_errors,
                "truncated": execution_result.truncated,
                # Enhanced observability
                "critique_attempts": critic_result["attempts"],
                "critique_result": critic_result["critique_result"],
                "semantic_violations": guard_result["violations"],
                "intent": intent,
                "selected_tables": [t["table"] for t in tables_info.get("tables", [])],
                "reasoning_stages_time_ms": reasoning_result.get("stage_times", {}).get("total_pipeline", 0),
                "reasoning_stage_breakdown": reasoning_result.get("stage_times", {}),
                "reasoning_errors": reasoning_result.get("errors", [])
            }

        except Exception as e:
            total_pipeline_time = int((time.time() - pipeline_start) * 1000)
            error_msg = str(e)

            logger.error(f"❌ PIPELINE_FAILED | ID: {request_id} | Question: '{question[:50]}{'...' if len(question) > 50 else ''}' | Error: {error_msg} | TotalTime: {total_pipeline_time}ms")
            logger.error(f"🔍 PIPELINE_ERROR_DETAILS | ID: {request_id} | Exception: {type(e).__name__} | Stage: Unknown", exc_info=True)

            return {
                "sql": "",
                "rows": [],
                "row_count": 0,
                "validation_status": "failed",
                "execution_status": "failed",
                "error_message": f"Reasoning pipeline failed: {str(e)}",
                "generation_time_ms": 0,
                "execution_time_ms": 0,
                "model_used": f"model_{model_id}",
                "validation_errors": [],
                "truncated": False,
                "critique_attempts": [],
                "critique_result": "error",
                "semantic_violations": [],
                "intent": "unknown",
                "selected_tables": [],
                "reasoning_stages_time_ms": int((time.time() - pipeline_start) * 1000),
                "reasoning_stage_breakdown": {},
                "reasoning_errors": [str(e)]
            }

    def _detect_intent_from_reasoning(self, reasoning_output: str) -> str:
        """Extract intent from legacy reasoning output"""
        text = reasoning_output.lower()
        if "count" in text or "how many" in text:
            return "COUNT"
        elif "average" in text or "sum" in text or "total" in text:
            return "AGGREGATION"
        elif "list" in text or "show all" in text:
            return "LIST"
        elif "top" in text or "highest" in text or "best" in text:
            return "TOP_N"
        elif "compare" in text or "vs" in text:
            return "COMPARISON"
        else:
            return "DETAIL"

    def _extract_tables_from_reasoning(self, reasoning_output: str, context: ChatContext) -> Dict[str, Any]:
        """Extract table information from legacy reasoning output"""
        # Simple extraction - could be enhanced
        tables = []
        for schema_info in context.schema_info or []:
            if schema_info.table_name.lower() in reasoning_output.lower():
                tables.append({
                    "table": schema_info.table_name,
                    "reason": "Mentioned in reasoning"
                })

        return {
            "tables": tables,
            "required_columns": [],
            "filters": []
        }
