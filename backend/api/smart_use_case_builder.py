from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json
import hashlib
import re
import asyncio
from loguru import logger

from .db_models import (
    UseCase, SchemaSnapshot, SchemaMetadata, DataDictionary,
    Relationship, LLMModel, AiGenerationLog, DatabaseConnection, get_db_session
)
from llm import ModelConnector, LLMRequest, Message, MessageRole
from llm.registry import initialize_registry, ConfigRegistryLoader
from llm.exceptions import ModelNotFoundError, ModelGenerationError
from .database import decrypt_api_key
from services.db_connector_utils import create_db_connector_for_snapshot
from core.db_utils import get_table_sample_data, get_table_schema_with_relationships
from core.config import LOG_ENCODING, LOG_ERROR_HANDLING


router = APIRouter()


class SmartUseCaseBuilderRequest(BaseModel):
    """Request model for smart use case builder wizard - aggregates all multi-step form data"""
    snapshot_id: int
    business_context: str  # Domain description
    primary_audience: List[str]  # multi-select options
    typical_questions: List[str]  # checkbox options
    output_preference: str  # numeric, summary, analytical, combined
    number_of_use_cases: int  # 3-15
    language: str  # Language for generation (en, fa, etc.)
    sample_questions: Optional[List[str]] = None  # Optional sample questions to convert to SQL
    scope: Optional[str] = "snapshot"  # snapshot|table|column
    table: Optional[str] = None  # For table/column scope
    column: Optional[str] = None  # For column scope


class UseCaseGenerationResponse(BaseModel):
    """Response model for generated use cases - new business-driven structure"""
    title: str
    scope: str  # snapshot|table|column
    actor: str  # User type/role
    business_goal: str
    preconditions: List[str]
    main_flow: List[str]  # Step-by-step flow
    alternative_flows: List[str]  # Alternative/exception flows
    required_inputs: List[str]
    sql_intent: str  # Description of what SQL should achieve
    expected_output: str
    validation_metrics: List[str]
    confidence_reference: Optional[str] = None
    confidence_score: float  # 0.0-1.0
    
    # Optional fields for backward compatibility and additional context
    table: Optional[str] = None
    column: Optional[str] = None
    snapshot_id: Optional[int] = None
    # Legacy fields for backward compatibility
    usecase_name: Optional[str] = None  # Maps to title
    description: Optional[str] = None  # Maps to business_goal
    expected_sql_patterns: Optional[List[str]] = None
    required_relations: Optional[List[str]] = None
    edge_cases: Optional[List[str]] = None
    sample_examples: Optional[List[Dict[str, Any]]] = None
    query_feasibility_score: Optional[float] = None  # Maps to confidence_score
    reasoning: Optional[str] = None
    typical_questions: Optional[List[str]] = None
    example_queries: Optional[List[str]] = None
    output_type: Optional[str] = None
    main_tables: Optional[List[str]] = None
    risk_notes: Optional[str] = None


class SmartUseCaseBuilderResponse(BaseModel):
    """Response model for smart use case builder"""
    use_cases: List[UseCaseGenerationResponse]
    generation_log_id: int
    system_prompt_examples: str


def _minify_schema_metadata(schema_metadata: List[SchemaMetadata]) -> Dict[str, Dict[str, Any]]:
    """Minify schema metadata into structured format for prompt injection"""
    minified = {}
    for meta in schema_metadata:
        table_key = f"{meta.schema_name}.{meta.table_name}" if meta.schema_name else meta.table_name
        if table_key not in minified:
            minified[table_key] = {
                "schema_name": meta.schema_name,
                "table_name": meta.table_name,
                "columns": []
            }
        
        if meta.column_name:
            minified[table_key]["columns"].append({
                "name": meta.column_name,
                "type": meta.column_type,
                "is_primary_key": meta.is_primary_key,
                "is_foreign_key": meta.is_foreign_key,
                "foreign_key_table": meta.foreign_key_table,
                "foreign_key_column": meta.foreign_key_column
            })
    
    return minified


def _format_data_dictionary(data_dictionary: List[DataDictionary]) -> Dict[str, Dict[str, Any]]:
    """Format data dictionary entries by table/column for easy lookup"""
    formatted = {}
    for entry in data_dictionary:
        table_key = f"{entry.schema_name}.{entry.table_name}" if entry.schema_name else entry.table_name
        if table_key not in formatted:
            formatted[table_key] = {}
        
        col_key = entry.column_name if entry.column_name else "__table__"
        formatted[table_key][col_key] = {
            "description": entry.description or "",
            "example_values": [],
            "synonyms": entry.synonyms or ""
        }
        
        # Parse example_values
        if entry.example_values:
            try:
                if isinstance(entry.example_values, str):
                    examples = json.loads(entry.example_values)
                else:
                    examples = entry.example_values
                if isinstance(examples, list):
                    formatted[table_key][col_key]["example_values"] = [str(v) for v in examples if v]
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
    
    return formatted


def _format_relationships(relationships: List[Relationship]) -> List[Dict[str, Any]]:
    """Format relationships including explicit and inferred semantic relations"""
    formatted = []
    for rel in relationships:
        formatted.append({
            "source_table": rel.source_table,
            "source_column": rel.source_column,
            "target_table": rel.target_table,
            "target_column": rel.target_column,
            "relationship_type": rel.relationship_type,
            "join_type": rel.join_type,
            "cardinality": rel.cardinality,
            "description": rel.description or "",
            "is_explicit": rel.relationship_type == "foreign_key"
        })
    return formatted


def build_single_table_use_case_prompt(
    request: SmartUseCaseBuilderRequest,
    table_key: str,
    table_schema: Dict[str, Any],
    table_dictionary: Dict[str, Any],
    table_relationships: List[Dict[str, Any]],
    table_sample_data: List[Dict[str, Any]],
    language: str = "en",
    database_type: Optional[str] = None,
    table_row_count: Optional[int] = None
) -> str:
    """Build prompt for a single table with its own sample data (20-30 rows)
    
    This function creates a focused prompt for one table at a time, allowing
    the model to see actual data patterns and generate better use cases.
    """
    import json
    
    # Format single table schema
    row_count_info = f" ({table_row_count:,} rows)" if table_row_count else ""
    schema_lines = [f"Table: {table_key}{row_count_info}"]
    schema_lines.append(f"  Columns ({len(table_schema.get('columns', []))}):")
    for col in table_schema.get("columns", []):
        col_line = f"  - {col['name']} ({col['type']})"
        if col.get("is_primary_key"):
            col_line += " [PRIMARY KEY]"
        if col.get("is_foreign_key"):
            col_line += f" [FOREIGN KEY -> {col.get('foreign_key_table', '?')}.{col.get('foreign_key_column', '?')}]"
        if col.get("is_nullable") == False:
            col_line += " [NOT NULL]"
        schema_lines.append(col_line)
    
    # Format single table dictionary
    dict_lines = [f"Table: {table_key}"]
    for col_key, col_info in table_dictionary.items():
        if col_key == "__table__":
            dict_lines.append(f"  Table Description: {col_info['description']}")
        else:
            dict_lines.append(f"  Column: {col_key}")
            if col_info.get("description"):
                dict_lines.append(f"    Description: {col_info['description']}")
            if col_info.get("example_values"):
                dict_lines.append(f"    Examples: {', '.join(col_info['example_values'][:5])}")
            if col_info.get("synonyms"):
                dict_lines.append(f"    Synonyms: {col_info['synonyms']}")
    
    # Format relationships for this table
    rel_lines = []
    explicit_rels = [r for r in table_relationships if r.get("is_explicit", False)]
    inferred_rels = [r for r in table_relationships if not r.get("is_explicit", False)]
    
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
    
    # Format sample data (20-30 rows for this table)
    sample_lines = []
    if table_sample_data:
        sample_lines.append("=" * 80)
        sample_lines.append(f"SAMPLE DATA FOR TABLE '{table_key}' - USE THESE ACTUAL VALUES")
        sample_lines.append("=" * 80)
        sample_lines.append(f"CRITICAL: This table has {len(table_sample_data)} sample rows. Extract actual values from these rows for WHERE clauses, filters, and validations.")
        sample_lines.append("CRITICAL: Use these real values in your queries, not generic placeholders.")
        sample_lines.append("")
        for i, row in enumerate(table_sample_data[:30], 1):  # Show up to 30 rows
            row_str = json.dumps(row, ensure_ascii=False)
            if len(row_str) > 500:
                row_str = row_str[:500] + "... (truncated)"
            sample_lines.append(f"  Row {i}: {row_str}")
        if len(table_sample_data) > 30:
            sample_lines.append(f"  ... ({len(table_sample_data) - 30} more rows available)")
        sample_lines.append("")
        sample_lines.append("=" * 80)
    
    # Language instruction
    target_language = request.language.lower() if hasattr(request, 'language') else language.lower()
    language_name_map = {
        "en": "English", "english": "English",
        "fa": "Persian (Farsi)", "persian": "Persian (Farsi)", "farsi": "Persian (Farsi)",
        "ar": "Arabic", "arabic": "Arabic",
        "tr": "Turkish", "turkish": "Turkish",
        "de": "German", "german": "German",
        "fr": "French", "french": "French",
        "es": "Spanish", "spanish": "Spanish"
    }
    language_display_name = language_name_map.get(target_language, "English")
    
    selected_language_instruction = f"""LANGUAGE REQUIREMENT:
Generate ALL use cases, descriptions, questions, and content EXCLUSIVELY in {language_display_name} language.
- All typical_questions must be in {language_display_name}
- All business_goal, title, actor descriptions must be in {language_display_name}
- Use appropriate {language_display_name} business terminology from the data dictionary"""
    
    # SQL Server instructions
    sql_server_instructions = ""
    if database_type and database_type.lower() in ["sqlserver", "mssql", "sql server"]:
        sql_server_instructions = """
SQL SERVER COMPATIBILITY REQUIREMENTS:
- Use SQL Server syntax: TOP instead of LIMIT, [] for identifiers if needed
- Use SQL Server functions: ISNULL, COALESCE, CAST, CONVERT
- Use SQL Server date functions: GETDATE(), DATEADD, DATEDIFF, YEAR(), MONTH(), DAY()
- Use SQL Server string functions: LEN(), SUBSTRING(), CHARINDEX(), REPLACE()
- Use SQL Server aggregation: COUNT, SUM, AVG, MIN, MAX, STDEV, VAR
- Avoid unsupported functions from other databases (e.g., LIMIT, EXTRACT, TO_CHAR, strftime)
- Use proper SQL Server JOIN syntax: INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL OUTER JOIN
- Use SQL Server window functions: ROW_NUMBER(), RANK(), DENSE_RANK(), OVER() with PARTITION BY
- Use SQL Server CTEs (WITH clause) when appropriate
- Use proper SQL Server data type casting: CAST(value AS type) or CONVERT(type, value)
"""
    elif not database_type or database_type.lower() not in ["postgresql", "mysql", "oracle"]:
        sql_server_instructions = """
SQL SERVER COMPATIBILITY (Default):
- Use SQL Server syntax: TOP instead of LIMIT
- Use SQL Server functions: ISNULL, COALESCE, CAST, CONVERT
- Use SQL Server date functions: GETDATE(), DATEADD, DATEDIFF
- Avoid unsupported functions from other databases
"""
    
    # Build focused prompt for single table
    prompt = f"""You are a **Professional SQL Server Database Use Case Generator AI** specialized in generating production-grade database use cases.

### Your mission:
Generate **high-quality, production-ready Use Cases** for THIS SPECIFIC TABLE: **{table_key}**

Focus on:
- Business-meaningful scenarios specific to this table
- Technically accurate with 100% question-SQL alignment
- Validated against the actual sample data provided below (20-30 rows)
- Optimized for SQL Server dialect and performance

### Core Principles (DO NOT BREAK):
1. **DO NOT** create new database or LLM connectors. Always use:
   - Database calls → `backend/db/connector.py (DatabaseConnector)`
   - LLM calls → `backend/llm/connector.py (ModelConnector)`
   - Prompt building → `backend/chat/engine/prompt_engine.py`
2. Keep queue, websocket, and running tasks intact. Only improve the LLM output.
3. Generate 1-3 use cases for THIS TABLE ONLY
4. Use only **SQL Server compatible logic**, avoid unsupported functions.
5. Output must be **valid JSON** (parsable without truncation).

{sql_server_instructions}

{selected_language_instruction}

### REQUIRED OUTPUT FORMAT (JSON array):
Generate 1-3 use cases for table '{table_key}'. Each use case must be a JSON object:

{{
  "title": "Business-focused title for this table",
  "scope": "table",
  "actor": "User role from: {', '.join(request.primary_audience) if request.primary_audience else 'Business User'}",
  "business_goal": "Description using ACTUAL business terminology from data dictionary for THIS table",
  "preconditions": ["Table {table_key} contains data", "Required columns are populated"],
  "main_flow": [
    "Step 1: User provides parameters",
    "Step 2: System validates",
    "Step 3: SQL executes on {table_key}",
    "Step 4: Returns results"
  ],
  "alternative_flows": ["ALT1: Error handling", "ALT2: Edge cases"],
  "required_inputs": ["Based on ACTUAL columns from THIS table"],
  "sql_intent": "Intent using ACTUAL table and column names from THIS table",
  "expected_output": "Output structure using ACTUAL column names from THIS table",
  "validation_metrics": ["Result count > 0", "All required columns present"],
  "confidence_reference": "Reference to relationships for THIS table",
  "confidence_score": 0.95,
  "typical_questions": ["Question 1 in {language_display_name} using ACTUAL column names", "Question 2", "Question 3"],
  "example_queries": ["SELECT query for THIS table using ACTUAL columns", "Query 2", "Query 3"]
}}

### CRITICAL REQUIREMENTS:
1. **MANDATORY**: Use ONLY columns from THIS table: {table_key}
2. **MANDATORY**: Extract actual values from SAMPLE DATA below for WHERE clauses
3. **MANDATORY**: Each query must use actual values seen in sample rows (not placeholders)
4. **MANDATORY**: Question and SQL query must be 100% logically equivalent
5. **MANDATORY**: At least 3 questions and 3 corresponding queries
6. **FORBIDDEN**: Never use hallucinated columns or values
7. **FORBIDDEN**: Never use filter values not present in sample data

### TABLE SCHEMA:
{chr(10).join(schema_lines)}

### DATA DICTIONARY FOR THIS TABLE:
{chr(10).join(dict_lines)}

### RELATIONSHIPS FOR THIS TABLE:
{chr(10).join(rel_lines) if rel_lines else "No relationships defined for this table."}

{chr(10).join(sample_lines) if sample_lines else "No sample data available for this table."}

### BUSINESS CONTEXT:
{request.business_context}

### PRIMARY AUDIENCE:
{', '.join(request.primary_audience) if request.primary_audience else 'General users'}

### TYPICAL QUESTION TYPES:
{', '.join(request.typical_questions) if request.typical_questions else 'Various analytical questions'}

### OUTPUT PREFERENCE:
{request.output_preference}

### CRITICAL OUTPUT REQUIREMENT:
Return ONLY a valid JSON array with 1-3 use cases for table '{table_key}'. No markdown, no explanations, no code blocks. Pure JSON array starting with '[' and ending with ']'.
"""
    
    return prompt


def build_use_case_generation_prompt(
    request: SmartUseCaseBuilderRequest,
    minified_schema: Dict[str, Dict[str, Any]],
    data_dictionary: Dict[str, Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    sample_data: Dict[str, List[Dict[str, Any]]],
    language: str = "en",
    database_type: Optional[str] = None,
    table_row_counts: Optional[Dict[str, int]] = None
) -> str:
    """Build reasoning-oriented prompt for accurate use case generation
    
    Args:
        request: Use case generation request
        minified_schema: Schema information
        data_dictionary: Data dictionary with descriptions
        relationships: List of relationships
        sample_data: Sample data per table
        language: Target language
        database_type: Database type (postgresql, mysql, sqlserver, etc.)
        table_row_counts: Dictionary mapping table names to row counts
    """
    
    # Format schema information (minified) with row counts
    schema_lines = []
    for table_key, table_info in minified_schema.items():
        row_count_info = ""
        if table_row_counts and table_key in table_row_counts:
            row_count = table_row_counts[table_key]
            row_count_info = f" ({row_count:,} rows)"
        
        schema_lines.append(f"Table: {table_key}{row_count_info}")
        schema_lines.append(f"  Columns ({len(table_info['columns'])}):")
        for col in table_info["columns"]:
            col_line = f"  - {col['name']} ({col['type']})"
            if col.get("is_primary_key"):
                col_line += " [PRIMARY KEY]"
            if col.get("is_foreign_key"):
                col_line += f" [FOREIGN KEY -> {col.get('foreign_key_table', '?')}.{col.get('foreign_key_column', '?')}]"
            if col.get("is_nullable") == False:
                col_line += " [NOT NULL]"
            schema_lines.append(col_line)
        schema_lines.append("")
    
    # Format data dictionary with context
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
    
    # Format relationships (explicit + inferred)
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
    
    # Format sample data (30+ rows if available, otherwise 3 rows per table)
    sample_lines = []
    if sample_data:
        sample_lines.append("=" * 80)
        sample_lines.append("SAMPLE DATA - USE THESE ACTUAL VALUES FOR QUERY VALIDATION")
        sample_lines.append("=" * 80)
        sample_lines.append("CRITICAL: Extract actual values from these rows for WHERE clauses, filters, and validations.")
        sample_lines.append("CRITICAL: Use these real values in your queries, not generic placeholders.")
        sample_lines.append("")
        for table_key, rows in sample_data.items():
            if rows and len(rows) > 0:
                sample_lines.append(f"\nTable: {table_key} ({len(rows)} sample rows)")
                # Show up to 30 rows if available, otherwise show all
                rows_to_show = min(30, len(rows)) if len(rows) > 3 else len(rows)
                for i, row in enumerate(rows[:rows_to_show], 1):
                    row_str = json.dumps(row, ensure_ascii=False)
                    # Truncate very long rows but keep key information
                    if len(row_str) > 500:
                        row_str = row_str[:500] + "... (truncated)"
                    sample_lines.append(f"  Row {i}: {row_str}")
                if len(rows) > rows_to_show:
                    sample_lines.append(f"  ... ({len(rows) - rows_to_show} more rows available)")
        sample_lines.append("")
        sample_lines.append("=" * 80)
        sample_lines.append("END SAMPLE DATA - Remember to use actual values from above in your queries!")
        sample_lines.append("=" * 80)
        sample_lines.append("")
    
    # Dynamic language instruction based on user selection
    target_language = request.language.lower() if hasattr(request, 'language') else language.lower()
    language_name_map = {
        "en": "English", "english": "English",
        "fa": "Persian (Farsi)", "persian": "Persian (Farsi)", "farsi": "Persian (Farsi)",
        "ar": "Arabic", "arabic": "Arabic",
        "tr": "Turkish", "turkish": "Turkish",
        "de": "German", "german": "German",
        "fr": "French", "french": "French",
        "es": "Spanish", "spanish": "Spanish"
    }
    language_display_name = language_name_map.get(target_language, "English")
    
    # Build dynamic language instruction
    selected_language_instruction = f"""LANGUAGE REQUIREMENT:
Generate ALL use cases, descriptions, questions, and content EXCLUSIVELY in {language_display_name} language.
- All typical_questions must be in {language_display_name}
- All business_goal, title, actor descriptions must be in {language_display_name}
- Use appropriate {language_display_name} business terminology from the data dictionary
- Base your questions on actual column names and business terms found in the DATA DICTIONARY section above"""
    
    # Dynamic scope-specific instructions based on user selection
    table_list = list(minified_schema.keys())
    if request.scope == "table" and request.table:
        # Find table in schema to get actual column count
        table_info = minified_schema.get(request.table, {})
        column_count = len(table_info.get('columns', []))
        scope_instructions = f"""
SCOPE: Generate use cases ONLY for table '{request.table}'.
- This table has {column_count} columns: {', '.join([col['name'] for col in table_info.get('columns', [])[:10]])}{'...' if column_count > 10 else ''}
- MANDATORY: Generate at least 1 use case for this specific table
- MANDATORY: Each use case must have 3+ questions and queries
- Base your use cases on the actual columns and data patterns from this table"""
    elif request.scope == "column" and request.table and request.column:
        # Get specific column info
        table_info = minified_schema.get(request.table, {})
        column_info = next((col for col in table_info.get('columns', []) if col['name'] == request.column), None)
        column_type = column_info.get('type', 'unknown') if column_info else 'unknown'
        scope_instructions = f"""
SCOPE: Generate use cases ONLY for column '{request.table}.{request.column}'.
- Column type: {column_type}
- MANDATORY: Generate at least 1 use case focused on this specific column
- MANDATORY: Each use case must have 3+ questions and queries
- Base your use cases on the actual data type, constraints, and sample values for this column"""
    else:
        scope_instructions = f"""
SCOPE: Generate use cases for ALL tables in the snapshot.
- Total tables: {len(table_list)}
- Tables: {', '.join(table_list[:20])}{'...' if len(table_list) > 20 else ''}
- MANDATORY: Generate at least 1 use case for EACH table
- MANDATORY: Each table use case must have 3+ questions and queries
- Distribute use cases across all tables based on their business importance and data volume"""
    
    # Database type information - emphasize SQL Server compatibility
    db_type_info = ""
    sql_server_instructions = ""
    if database_type:
        db_type_info = f"\nDATABASE TYPE: {database_type.upper()}\n- Generate SQL queries compatible with {database_type.upper()} syntax\n- Use appropriate {database_type.upper()} functions and operators\n- Consider {database_type.upper()}-specific features and limitations"
    
    # SQL Server specific instructions
    if database_type and database_type.lower() in ["sqlserver", "mssql", "sql server"]:
        sql_server_instructions = """
SQL SERVER COMPATIBILITY REQUIREMENTS:
- Use SQL Server syntax: TOP instead of LIMIT, [] for identifiers if needed
- Use SQL Server functions: ISNULL, COALESCE, CAST, CONVERT
- Use SQL Server date functions: GETDATE(), DATEADD, DATEDIFF, YEAR(), MONTH(), DAY()
- Use SQL Server string functions: LEN(), SUBSTRING(), CHARINDEX(), REPLACE()
- Use SQL Server aggregation: COUNT, SUM, AVG, MIN, MAX, STDEV, VAR
- Avoid unsupported functions from other databases (e.g., LIMIT, EXTRACT, TO_CHAR)
- Use proper SQL Server JOIN syntax: INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL OUTER JOIN
- Use SQL Server window functions: ROW_NUMBER(), RANK(), DENSE_RANK(), OVER() with PARTITION BY
- Use SQL Server CTEs (WITH clause) when appropriate
- Use proper SQL Server data type casting: CAST(value AS type) or CONVERT(type, value)
"""
    elif not database_type or database_type.lower() not in ["postgresql", "mysql", "oracle"]:
        # Default to SQL Server if not specified
        sql_server_instructions = """
SQL SERVER COMPATIBILITY (Default):
- Use SQL Server syntax: TOP instead of LIMIT
- Use SQL Server functions: ISNULL, COALESCE, CAST, CONVERT
- Use SQL Server date functions: GETDATE(), DATEADD, DATEDIFF
- Avoid unsupported functions from other databases
"""
    
    # Build reasoning-oriented prompt with new structure
    prompt = f"""You are a **Professional SQL Server Database Use Case Generator AI** specialized in generating production-grade database use cases.

### Your mission:
Generate **high-quality, production-ready Use Cases** for SQL Server databases that are:
- Business-meaningful with clear real-world scenarios
- Technically accurate with 100% question-SQL alignment
- Validated against actual sample data patterns
- Optimized for SQL Server dialect and performance

### Core Principles (DO NOT BREAK):
1. **DO NOT** create new database or LLM connectors. Always use:
   - Database calls → `backend/db/connector.py (DatabaseConnector)`
   - LLM calls → `backend/llm/connector.py (ModelConnector)`
   - Prompt building → `backend/chat/engine/prompt_engine.py`
2. Keep queue, websocket, and running tasks intact. Only improve the LLM output.
3. Use Cases must be **business-meaningful, practical, and modular**.
4. Cover 3 possible scopes:
   - Whole snapshot
   - Specific table(s)
   - Specific column(s)
5. Each Use Case must include all required fields (see JSON structure below).
6. Use only **SQL Server compatible logic**, avoid unsupported functions.
7. Do not remove or contradict existing relations. Extend insights instead.
8. Use Cases must be **ready for future expansion** (RAG, query improvement, automation, UI triggers).
9. Keep structure clean, non-repetitive, no hallucinated column names.
10. Tone: practical, product-oriented, slightly informal but professional.
11. Output must be **valid JSON** (parsable without truncation).

{db_type_info}
{sql_server_instructions}

{scope_instructions}

### REQUIRED OUTPUT FORMAT (JSON array):
Each use case must be a JSON object with these EXACT fields. ALL examples below are PLACEHOLDERS - you MUST use ACTUAL data from the schema, data dictionary, and sample data provided above:

{{
  "title": "Business-focused title based on ACTUAL table/column names from schema (use terms from data dictionary)",
  "scope": "{request.scope}",
  "actor": "User role from: {', '.join(request.primary_audience) if request.primary_audience else 'Business User'} - choose the most appropriate one",
  "business_goal": "Description using ACTUAL business terminology from data dictionary for the specific tables/columns",
  "preconditions": ["Based on ACTUAL table names and relationships", "Use real column constraints from schema"],
  "main_flow": [
    "Step 1: User provides parameters based on ACTUAL required_inputs",
    "Step 2: System validates using ACTUAL table/column constraints",
    "Step 3: SQL executes on ACTUAL tables from schema",
    "Step 4: Returns results matching ACTUAL expected_output structure"
  ],
  "alternative_flows": [
    "ALT1: Handle cases based on ACTUAL data patterns from sample_data",
    "ALT2: Error handling for ACTUAL column constraints",
    "ALT3: Edge cases from ACTUAL relationships"
  ],
  "required_inputs": ["Based on ACTUAL columns that need filtering (e.g., date columns, category columns from schema)"],
  "sql_intent": "Intent using ACTUAL table names, column names, and relationships from schema above",
  "expected_output": "Output structure using ACTUAL column names and data types from schema",
  "validation_metrics": ["Based on ACTUAL table row counts", "Using ACTUAL column constraints"],
  "confidence_reference": "Reference to ACTUAL relationships from RELATIONSHIPS section (explicit or inferred)",
  "confidence_score": 0.95,
  "typical_questions": ["Question 1 using ACTUAL column names and business terms from data dictionary in {language_display_name}", "Question 2 using ACTUAL data patterns from sample_data", "Question 3 based on ACTUAL relationships"],
  "example_queries": ["SELECT using ACTUAL table.column FROM ACTUAL table WHERE ...", "JOIN using ACTUAL relationships", "GROUP BY using ACTUAL columns"]
}}

### FIELD REQUIREMENTS:

1. **title**: Short, business-focused title without SQL/database jargon. Use business terminology.

2. **scope**: Must be one of: "snapshot", "table", or "column"

3. **actor**: MUST be one of the PRIMARY AUDIENCE values provided by the user: {', '.join(request.primary_audience) if request.primary_audience else 'General Business User'}. Choose the most appropriate role for each use case.

4. **business_goal**: Clear 1-2 sentence description using ACTUAL business terminology from the DATA DICTIONARY section. Reference specific tables and columns from the schema. Must be in {language_display_name}.

5. **preconditions**: Array based on ACTUAL schema constraints:
   - Reference ACTUAL table names from schema
   - Use ACTUAL NOT NULL constraints from column definitions
   - Reference ACTUAL foreign key relationships
   - Example based on real schema: ["Table {list(minified_schema.keys())[0] if minified_schema else 'X'} contains data", "Required columns from ACTUAL schema are populated"]

6. **main_flow**: Step-by-step array describing the primary user journey:
   - Step 1: User action/input
   - Step 2: System validation/processing
   - Step 3: SQL execution
   - Step 4: Result delivery
   - Each step should be a clear, actionable description

7. **alternative_flows**: Array of alternative scenarios:
   - Error handling paths
   - Edge cases
   - Exception scenarios
   - Format: "ALT1: Description", "ALT2: Description"

8. **required_inputs**: Array based on ACTUAL columns that need filtering:
   - Use ACTUAL date/datetime columns from schema for date ranges
   - Use ACTUAL category/enum columns from schema for filters
   - Reference ACTUAL column names from the schema
   - Example based on real columns: ["Use ACTUAL date column name from schema", "Use ACTUAL category column name from schema"]

9. **sql_intent**: Description using ACTUAL table and column names from schema:
   - Reference ACTUAL table names from DATABASE SCHEMA section
   - Use ACTUAL column names from schema
   - Reference ACTUAL relationships from RELATIONSHIPS section
   - Example based on real schema: "Retrieve data from ACTUAL table names using ACTUAL column names, join via ACTUAL relationships, filter by ACTUAL date columns"

10. **expected_output**: Description using ACTUAL column names and data types from schema:
    - Use ACTUAL column names from DATABASE SCHEMA
    - Use ACTUAL data types from column definitions
    - Reference ACTUAL row counts from table_row_counts if available
    - Example based on real schema: "Table with ACTUAL column names (ACTUAL data types). Expected rows based on ACTUAL table size."

11. **validation_metrics**: Array of success criteria:
    - Data quality checks
    - Result completeness
    - Performance expectations
    - Example: ["Result count > 0", "All required columns present", "Query execution time < 5 seconds"]

12. **confidence_reference**: Reference to ACTUAL relationships from RELATIONSHIPS section:
    - If explicit FK exists: "Based on explicit FK relationship between ACTUAL source_table.ACTUAL source_column -> ACTUAL target_table.ACTUAL target_column"
    - If inferred: "Inferred from semantic analysis between ACTUAL table names with confidence score"
    - Reference ACTUAL relationship descriptions from RELATIONSHIPS section above

13. **confidence_score**: Float between 0.0 and 1.0 indicating accuracy and reliability:
    - **0.9-1.0**: Explicit FK relationships exist, all required columns present, sample data validates query patterns, query tested against sample values
    - **0.8-0.89**: Explicit relationships exist, most columns present, sample data partially validates patterns
    - **0.7-0.79**: Inferred relationships, some columns may be missing, limited sample data validation
    - **0.5-0.69**: Inferred relationships, missing key columns, no sample data validation
    - **<0.5**: Significant uncertainty - missing relationships, incomplete schema, no sample data
    - **CRITICAL**: Double-check query correctness against sample data patterns before assigning confidence
    - **CRITICAL**: Lower confidence if filters use values not seen in sample data
    - **CRITICAL**: Higher confidence if query uses actual sample values and validates correctly

14. **typical_questions**: **MANDATORY** - Array of AT LEAST 3 natural language questions in the target language:
    - Each question must be a complete, natural language question that a user would ask
    - Questions must use actual column names and business terminology from the data dictionary
    - Questions should be specific to the use case and business context
    - **CRITICAL**: Questions must NOT start with "Query:", "SQL:", or any technical prefix
    - **CRITICAL**: Questions must be in natural language format (e.g., "کدام محصولات بیشترین فروش را داشته‌اند؟" not "Query: ...")
    - Example for Persian: "کدام محصولات بیشترین فروش را در ماه گذشته داشته‌اند؟"
    - Example for English: "Which products had the highest sales in the last month?"
    - Each question must be unique and directly related to the use case

15. **example_queries**: **MANDATORY** - Array of AT LEAST 3 corresponding SQL queries:
    - Each query must be a valid, executable SQL statement that answers the corresponding question in typical_questions
    - Queries must use ACTUAL table names and column names from the schema (NOT placeholders)
    - The order of queries MUST match the order of questions (query[0] answers question[0], query[1] answers question[1], etc.)
    - Queries must be SQL Server compatible (use TOP instead of LIMIT, proper SQL Server functions)
    - Queries should demonstrate different SQL patterns: filtering, joining, aggregation, sorting
    - **CRITICAL**: Each query must be logically equivalent to its corresponding question - they must return the same logical result
    - **CRITICAL**: Use actual values from SAMPLE DATA section for WHERE clauses (e.g., if sample shows status='Active', use that value)
    - **CRITICAL**: Optimize queries using indexed/filterable columns when possible
    - **CRITICAL**: Avoid full table scans when unnecessary - use WHERE clauses with actual sample values
    - **CRITICAL**: Prefer analytical aggregations (GROUP BY, WINDOW functions, PERCENTILE_CONT) when needed
    - Example: ["SELECT TOP 10 ProductName, SUM(Quantity) as TotalSales FROM Orders WHERE OrderDate >= DATEADD(month, -1, GETDATE()) GROUP BY ProductName ORDER BY TotalSales DESC", ...]

### CRITICAL REQUIREMENTS FOR QUESTIONS AND QUERIES:
1. **MANDATORY**: Each use case MUST have exactly 3 or more questions in typical_questions array
2. **MANDATORY**: Each use case MUST have exactly 3 or more queries in example_queries array
3. **MANDATORY**: The number of questions MUST equal the number of queries
4. **MANDATORY**: Each query must directly answer its corresponding question (query[0] answers question[0])
5. **MANDATORY**: Question and SQL query must be **100% logically equivalent** - they must return the same logical result
6. **MANDATORY**: Validate query correctness against sample data patterns - use actual values seen in sample rows
7. **MANDATORY**: Ensure filters reflect actual values from SAMPLE DATA section (not generic placeholders)
8. **MANDATORY**: Ensure aggregation logic matches business intent described in the question
9. **FORBIDDEN**: Never start questions with "Query:", "SQL:", or any technical prefix
10. **FORBIDDEN**: Never use placeholder queries like "SELECT * FROM information_schema.tables"
11. **FORBIDDEN**: Never use generic questions like "What information can I get from this use case?"
12. **FORBIDDEN**: Never use hallucinated column names, relations, or values not present in the schema/sample data

### GENERATION RULES & VALIDATION CHECKLIST:
- **MANDATORY**: Each use case must use ONLY ACTUAL table names, column names, and data types from the DATABASE SCHEMA section above
- **MANDATORY**: Use ACTUAL business terminology from the DATA DICTIONARY section (not generic terms)
- **MANDATORY**: Reference ACTUAL relationships from the RELATIONSHIPS section (explicit or inferred)
- **MANDATORY**: Base preconditions, inputs, and outputs on ACTUAL column constraints and sample data patterns
- **MANDATORY**: Use ACTUAL sample values from SAMPLE DATA section to create realistic questions AND queries
- **MANDATORY**: Consider ACTUAL table row counts when designing queries (larger tables = more complex queries)
- Focus on business value specific to THIS database schema, not generic examples
- **MANDATORY**: Generate at least 1 use case for EACH table in the schema (for snapshot scope)
- **MANDATORY**: Use actual data patterns from sample_data to create realistic use cases
- **MANDATORY**: Consider table row counts - larger tables may need more complex queries
- **MANDATORY**: Confidence scores should reflect relationship reliability (explicit > inferred) AND data validation success
- **MANDATORY**: Each use case MUST have at least 3 natural language questions (NOT starting with "Query:")
- **MANDATORY**: Each use case MUST have at least 3 corresponding SQL queries
- **MANDATORY**: Questions must be in the target language (as specified in language instructions)
- **MANDATORY**: Questions must use actual column names and business terminology from the data dictionary
- **MANDATORY**: Queries must use REAL table and column names from the schema, never placeholders
- **MANDATORY**: Validate each query against sample data - ensure WHERE clause values exist in sample rows
- **MANDATORY**: Ensure aggregation logic matches business intent - verify GROUP BY columns exist in schema
- **MANDATORY**: Use proper JOIN paths if relationships exist - verify join columns match relationship definitions
- **MANDATORY**: Optimize queries using indexed/filterable columns when possible
- **FORBIDDEN**: Never use hallucinated column names or tables
- **FORBIDDEN**: Never skip generating use cases for required tables
- **FORBIDDEN**: Never use placeholder or generic descriptions
- **FORBIDDEN**: Never start questions with "Query:", "SQL:", or any technical prefix
- **FORBIDDEN**: Never use placeholder queries like "SELECT * FROM information_schema.tables"
- **FORBIDDEN**: Never use filter values not present in sample data (unless explicitly required for the use case)
- **FORBIDDEN**: Never use non-SQL-Server date functions like strftime, date() - use GETDATE(), DATEADD, DATEDIFF instead

### USE CASE QUALITY CHECKLIST (Apply to EACH use case):
Before finalizing each use case, verify:
- [ ] Question and SQL query return the same logical result (100% alignment)
- [ ] No hallucinated columns, relations, or values
- [ ] SQL uses optimized filters based on sample data
- [ ] Uses existing DBConnector and ModelConnector modules (do not create new ones)
- [ ] SQL Server dialect compliant (TOP, GETDATE(), DATEADD, not LIMIT, NOW(), strftime)
- [ ] Includes business explanation
- [ ] Includes JOIN explanation if applicable
- [ ] Includes a confidence score based on data validation
- [ ] Filters use actual values seen in sample rows (when applicable)
- [ ] Aggregation logic matches business intent

{selected_language_instruction}

### CRITICAL: USE ACTUAL DATA FROM BELOW
**DO NOT** use generic examples or placeholder values. **MUST** use:
- ACTUAL table names from DATABASE SCHEMA section
- ACTUAL column names and types from schema
- ACTUAL business terminology from DATA DICTIONARY section
- ACTUAL relationships from RELATIONSHIPS section
- ACTUAL sample values from SAMPLE DATA section (use these for WHERE clauses!)
- ACTUAL row counts from table statistics

**VALIDATION REQUIREMENT**: Before generating queries, examine the SAMPLE DATA section:
- Extract actual values from sample rows (e.g., status='Active', date='2024-01-15', category='Premium')
- Use these actual values in WHERE clauses, not generic placeholders
- Verify that filter columns exist in the schema
- Ensure aggregation columns are numeric/aggregatable types
- Check that JOIN columns match relationship definitions

**FORBIDDEN**: Generic examples like "Product", "Order", "Customer" unless they actually exist in the schema below.
**FORBIDDEN**: Using filter values not present in sample data (unless the use case explicitly requires it)

DATABASE SCHEMA (Minified):
{chr(10).join(schema_lines)}

DATA DICTIONARY:
{chr(10).join(dict_lines)}

RELATIONSHIPS:
{chr(10).join(rel_lines) if rel_lines else "No relationships defined."}

{sample_lines[0] if sample_lines else ""}
{chr(10).join(sample_lines[1:]) if len(sample_lines) > 1 else ""}

### BUSINESS CONTEXT:
{request.business_context}

### PRIMARY AUDIENCE (User-selected - USE THESE IN YOUR ACTOR FIELD):
{', '.join(request.primary_audience) if request.primary_audience else 'General users'}
- IMPORTANT: Set the "actor" field to match these user types
- Each use case should reflect the perspective and needs of the primary audience
- Use business terminology appropriate for: {', '.join(request.primary_audience) if request.primary_audience else 'general users'}

### TYPICAL QUESTION TYPES (User-selected - USE THESE TO CREATE YOUR QUESTIONS):
{', '.join(request.typical_questions) if request.typical_questions else 'Various analytical questions'}
- **CRITICAL**: Generate questions in typical_questions array that match these question types
- Distribute question types across different use cases
- Example question types: {', '.join(request.typical_questions) if request.typical_questions else 'analytical, filtering, aggregation, comparison, trend analysis'}
- Each use case should have questions representing different types from this list

### QUESTION FORMAT EXAMPLES (Based on ACTUAL schema):
**CORRECT (Natural Language using ACTUAL column names):**
- Use ACTUAL table and column names from DATABASE SCHEMA section
- Use ACTUAL business terminology from DATA DICTIONARY section
- Reference ACTUAL sample values from SAMPLE DATA section
- Example format (replace with ACTUAL names): "Which [ACTUAL column name from schema] had the highest [ACTUAL metric column] in [ACTUAL date column]?"
- Must be in {language_display_name} language

**INCORRECT (Technical Prefix - FORBIDDEN):**
- "Query: ..." or "SQL: ..." or "کوئری: ..."
- Generic placeholders instead of ACTUAL column names
- Not using ACTUAL business terms from data dictionary

### OUTPUT PREFERENCE (User-selected - MATCH THIS IN YOUR SQL INTENT):
{request.output_preference}
- Reflect this preference in the sql_intent and expected_output fields
- If "numeric": SQL intent should focus on COUNT, SUM, AVG, MIN, MAX aggregations
- If "summary": SQL intent should focus on GROUP BY, DISTINCT, summary reports
- If "analytical": SQL intent should focus on complex joins, subqueries, window functions
- If "detailed": SQL intent should focus on SELECT with specific columns, filtering, sorting

{f"### ADDITIONAL SAMPLE QUESTIONS (Reference for SQL Intent):{chr(10)}{chr(10).join(request.sample_questions)}" if request.sample_questions else ""}

### NUMBER OF USE CASES TO GENERATE:
{request.number_of_use_cases}

### PER-TABLE USE CASE GENERATION STRATEGY:
For each table in the scope, generate use cases that:
1. **Explain the real business scenario** this table serves (use business context: telematics, fleet, oil products, logistics, etc.)
2. **Create precise question-SQL pairs** where each question logically matches its SQL query
3. **Validate against sample data** - ensure WHERE clause values exist in sample rows
4. **Use proper JOINs** if relationships exist - follow explicit FK relationships first
5. **Optimize for SQL Server** - use TOP, GETDATE(), DATEADD, proper window functions
6. **Assign accurate confidence** - higher for explicit relationships + validated sample data

### VALIDATION & ACCURACY GUARD:
Before finalizing each use case:
1. **Double-check query correctness** against sample data patterns
2. **Ensure filters reflect actual values** seen in sample rows (not generic placeholders)
3. **Ensure aggregation logic matches** business intent described in the question
4. **Verify JOIN paths** match relationship definitions from RELATIONSHIPS section
5. **Check SQL Server syntax** - no LIMIT, strftime, NOW() - use TOP, GETDATE(), DATEADD instead
6. **Calculate confidence score** based on:
   - Relationship reliability (explicit FK > inferred)
   - Sample data validation success
   - Schema completeness for the use case
   - Query correctness verification

### CRITICAL OUTPUT REQUIREMENT:
Return ONLY a valid JSON array. No markdown, no explanations, no code blocks. Pure JSON array starting with '[' and ending with ']'. Each object must have all required fields. Ensure JSON is valid and parsable.

**IMPORTANT**: If a table does NOT serve a meaningful standalone use case, you may propose a relationship-driven composite use case, or explicitly mark it with "no_standalone_usecase": true but still provide column insights.
"""
    
    return prompt


@router.post("/generate", response_model=SmartUseCaseBuilderResponse)
async def generate_smart_use_cases(
    request: SmartUseCaseBuilderRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Generate use cases using AI with enhanced context injection and reasoning
    
    NOTE: This endpoint is kept for backward compatibility.
    For new implementations, use /api/use-case-job/generate which provides
    WebSocket updates and better error handling.
    """
    
    try:
        # Validate snapshot exists
        snapshot_result = await session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.id == request.snapshot_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Schema snapshot not found")
        
        logger.info(f"Generating use cases for snapshot {request.snapshot_id}, scope: {request.scope}")
        
        # Get active LLM model
        model_result = await session.execute(select(LLMModel).where(LLMModel.is_active == True))
        active_model = model_result.scalar_one_or_none()
        if not active_model:
            raise HTTPException(status_code=400, detail="No active LLM model found")
        
        # Get schema metadata (filtered by scope if needed)
        schema_query = select(SchemaMetadata).where(
            SchemaMetadata.schema_snapshot_id == request.snapshot_id
        )
        if request.scope == "table" and request.table:
            schema_query = schema_query.where(SchemaMetadata.table_name == request.table)
        elif request.scope == "column" and request.table and request.column:
            schema_query = schema_query.where(
                and_(
                    SchemaMetadata.table_name == request.table,
                    SchemaMetadata.column_name == request.column
                )
            )
        
        schema_result = await session.execute(schema_query)
        schema_metadata = schema_result.scalars().all()
        
        if not schema_metadata:
            raise HTTPException(status_code=400, detail="No schema metadata found for the specified scope")
        
        # Minify schema for prompt injection
        minified_schema = _minify_schema_metadata(schema_metadata)
        logger.info(f"Minified schema: {len(minified_schema)} tables")
        
        # Get data dictionary (filtered by scope)
        dict_query = select(DataDictionary).where(
            DataDictionary.schema_snapshot_id == request.snapshot_id
        )
        if request.scope == "table" and request.table:
            dict_query = dict_query.where(DataDictionary.table_name == request.table)
        elif request.scope == "column" and request.table and request.column:
            dict_query = dict_query.where(
                and_(
                    DataDictionary.table_name == request.table,
                    DataDictionary.column_name == request.column
                )
            )
        
        dict_result = await session.execute(dict_query)
        data_dictionary_raw = dict_result.scalars().all()
        data_dictionary = _format_data_dictionary(data_dictionary_raw)
        logger.info(f"Data dictionary: {len(data_dictionary)} tables with descriptions")
        
        # Get relationships (all known semantic relations - explicit + inferred)
        rel_query = select(Relationship).where(
            Relationship.schema_snapshot_id == request.snapshot_id
        )
        if request.scope == "table" and request.table:
            rel_query = rel_query.where(
                (Relationship.source_table == request.table) | 
                (Relationship.target_table == request.table)
            )
        elif request.scope == "column" and request.table and request.column:
            rel_query = rel_query.where(
                and_(
                    (Relationship.source_table == request.table) | (Relationship.target_table == request.table),
                    (Relationship.source_column == request.column) | (Relationship.target_column == request.column)
                )
            )
        
        rel_result = await session.execute(rel_query)
        relationships_raw = rel_result.scalars().all()
        relationships = _format_relationships(relationships_raw)
        logger.info(f"Relationships: {len(relationships)} total ({sum(1 for r in relationships if r.get('is_explicit'))} explicit, {sum(1 for r in relationships if not r.get('is_explicit'))} inferred)")
        
        # Get database type from connection
        database_type = None
        try:
            connection_result = await session.execute(
                select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
            )
            connection = connection_result.scalar_one_or_none()
            if connection:
                database_type = connection.db_type.lower() if connection.db_type else None
                logger.info(f"Database type: {database_type}")
        except Exception as e:
            logger.warning(f"Could not get database type: {e}")
        
        # Get sample data and row counts using DBConnector (3 unique rows per relevant table)
        sample_data = {}
        table_row_counts = {}
        db_connector = None
        
        try:
            # Use DBConnector utility to create connector
            db_connector = await create_db_connector_for_snapshot(request.snapshot_id, session)
            
            if db_connector:
                await db_connector.connect()
                logger.info("Connected to database via DBConnector")
                
                # Determine which tables to sample based on scope
                tables_to_sample = list(minified_schema.keys())
                if request.scope == "table" and request.table:
                    tables_to_sample = [t for t in tables_to_sample if request.table in t]
                elif request.scope == "column" and request.table:
                    tables_to_sample = [t for t in tables_to_sample if request.table in t]
                
                # Sample 3 rows per table using DBConnector and get row counts
                for table_key in tables_to_sample[:50]:  # Limit to 50 tables for performance
                    try:
                        # Extract schema and table name
                        if '.' in table_key:
                            schema_name, table_name = table_key.split('.', 1)
                        else:
                            schema_name = None
                            table_name = table_key
                        
                        # Use DBConnector to sample rows
                        full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name
                        sample_rows = await db_connector.sample_rows(full_table_name, limit=3)
                        
                        if sample_rows:
                            sample_data[table_key] = sample_rows
                            logger.debug(f"Sampled {len(sample_rows)} rows from {table_key}")
                        
                        # Try to get row count (optional, may fail)
                        try:
                            if database_type == "sqlserver":
                                count_query = f"SELECT COUNT(*) as cnt FROM [{schema_name}].[{table_name}]" if schema_name else f"SELECT COUNT(*) as cnt FROM [{table_name}]"
                            elif database_type == "mysql":
                                count_query = f"SELECT COUNT(*) as cnt FROM `{schema_name}`.`{table_name}`" if schema_name else f"SELECT COUNT(*) as cnt FROM `{table_name}`"
                            elif database_type == "postgresql":
                                count_query = f'SELECT COUNT(*) as cnt FROM "{schema_name}"."{table_name}"' if schema_name else f'SELECT COUNT(*) as cnt FROM "{table_name}"'
                            else:
                                count_query = f"SELECT COUNT(*) as cnt FROM {full_table_name}"
                            
                            count_result = await db_connector.execute_readonly(count_query, limit=1)
                            if count_result and len(count_result) > 0:
                                row_count = int(count_result[0].get('cnt', count_result[0].get(list(count_result[0].keys())[0], 0)))
                                table_row_counts[table_key] = row_count
                        except Exception as e:
                            logger.debug(f"Could not get row count for {table_key}: {e}")
                            pass
                    except Exception as e:
                        logger.warning(f"Failed to sample data from {table_key}: {e}")
                        # Continue without sample data for this table
                        sample_data[table_key] = []
            else:
                logger.warning("Could not create DBConnector, using schema-only data")
        
        except Exception as e:
            logger.warning(f"Database sampling failed: {e}, continuing with schema-only data")
        finally:
            if db_connector:
                try:
                    await db_connector.disconnect()
                except:
                    pass
        
        logger.info(f"Sample data collected for {len(sample_data)} tables, row counts for {len(table_row_counts)} tables")
        
        # Calculate optimal number of use cases if not specified
        if not request.number_of_use_cases or request.number_of_use_cases <= 0:
            num_tables = len(minified_schema)
            use_cases_per_table = 3
            request.number_of_use_cases = min(15, num_tables * use_cases_per_table)
        
        # Build enhanced reasoning-oriented prompt
        prompt = build_use_case_generation_prompt(
            request, minified_schema, data_dictionary, relationships, sample_data, request.language,
            database_type=database_type, table_row_counts=table_row_counts
        )
        
        logger.debug(f"Prompt length: {len(prompt)} characters")
        
        # Calculate prompt hash
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        
        # Log the generation attempt
        generation_log = AiGenerationLog(
            schema_snapshot_id=request.snapshot_id,
            model_id=active_model.id,
            business_domain=request.business_context,
            database_description="Smart Use Case Builder (Enhanced)",
            target_user=",".join(request.primary_audience) if request.primary_audience else "",
            optional_notes=f"Scope: {request.scope}, Output: {request.output_preference}, Questions: {','.join(request.typical_questions) if request.typical_questions else 'N/A'}",
            prompt_hash=prompt_hash
        )
        session.add(generation_log)
        await session.flush()
        
        # Initialize ModelConnector for LLM generation
        result = await session.execute(select(LLMModel).where(LLMModel.is_active == True))
        models = result.scalars().all()
        
        config = {"models": []}
        for db_model in models:
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
                "timeout_seconds": 1800.0,
            })
        
        # Initialize registry and connector
        loader = ConfigRegistryLoader(config)
        registry = initialize_registry(loader)
        await registry.load()
        
        connector = ModelConnector(registry)
        await connector.initialize()  # Initialize the connector before use
        
        # Create LLM request
        llm_request = LLMRequest(
            model_id=str(active_model.id),
            messages=[Message(role=MessageRole.USER, content=prompt)],
            temperature=active_model.temperature,
            max_tokens=min(4096, active_model.max_tokens * 2)
        )
        
        # Generate use cases using ModelConnector
        try:
            response = await connector.generate(llm_request)
            generated_text = response.text
            
            if not generated_text:
                raise HTTPException(
                    status_code=503,
                    detail="AI service returned empty response. Please try again later."
                )
        
        except (ModelNotFoundError, ModelGenerationError) as e:
            generation_log.error_message = str(e)
            await session.commit()
            raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")
        
        # Parse JSON response
        try:
            # Clean response (remove markdown code blocks)
            cleaned_text = generated_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            try:
                use_cases_data = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # Try to extract JSON array using regex
                json_match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
                if json_match:
                    extracted_json = json_match.group()
                    # Fix common JSON issues
                    extracted_json = re.sub(r',(\s*[}\]])', r'\1', extracted_json)
                    use_cases_data = json.loads(extracted_json)
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid JSON response from AI. Could not find JSON array."
                    )
            
            if not isinstance(use_cases_data, list):
                use_cases_data = [use_cases_data]  # Convert single object to array
            
            # Validate and convert to response format
            validated_use_cases = []
            for uc_data in use_cases_data:
                if not isinstance(uc_data, dict):
                    continue
                
                # Check if this is new format (has 'title' field) or old format
                is_new_format = "title" in uc_data
                
                if is_new_format:
                    # New format - map directly
                    validated_uc = UseCaseGenerationResponse(
                        title=uc_data.get("title", "Unnamed Use Case"),
                        scope=uc_data.get("scope", request.scope),
                        actor=uc_data.get("actor", "General User"),
                        business_goal=uc_data.get("business_goal", ""),
                        preconditions=uc_data.get("preconditions", []),
                        main_flow=uc_data.get("main_flow", []),
                        alternative_flows=uc_data.get("alternative_flows", []),
                        required_inputs=uc_data.get("required_inputs", []),
                        sql_intent=uc_data.get("sql_intent", ""),
                        expected_output=uc_data.get("expected_output", ""),
                        validation_metrics=uc_data.get("validation_metrics", []),
                        confidence_reference=uc_data.get("confidence_reference"),
                        confidence_score=float(uc_data.get("confidence_score", 0.5)),
                        # Optional fields
                        table=uc_data.get("table") if uc_data.get("table") != "null" else (request.table if request.scope in ["table", "column"] else None),
                        column=uc_data.get("column") if uc_data.get("column") != "null" else (request.column if request.scope == "column" else None),
                        snapshot_id=uc_data.get("snapshot_id", request.snapshot_id),
                        # Legacy fields for backward compatibility
                        usecase_name=uc_data.get("title"),  # Map title to usecase_name
                        description=uc_data.get("business_goal"),  # Map business_goal to description
                        query_feasibility_score=float(uc_data.get("confidence_score", 0.5)),  # Map confidence_score
                        expected_sql_patterns=uc_data.get("expected_sql_patterns"),
                        required_relations=uc_data.get("required_relations"),
                        edge_cases=uc_data.get("edge_cases") or uc_data.get("alternative_flows", []),
                        sample_examples=uc_data.get("sample_examples"),
                        reasoning=uc_data.get("reasoning"),
                        typical_questions=uc_data.get("typical_questions"),
                        example_queries=uc_data.get("example_queries"),
                        output_type=uc_data.get("output_type"),
                        main_tables=uc_data.get("main_tables"),
                        risk_notes=uc_data.get("risk_notes")
                    )
                else:
                    # Old format - map to new structure with backward compatibility
                    validated_uc = UseCaseGenerationResponse(
                        title=uc_data.get("usecase_name") or uc_data.get("name", "Unnamed Use Case"),
                        scope=uc_data.get("scope", request.scope),
                        actor="General User",  # Default for old format
                        business_goal=uc_data.get("description", ""),
                        preconditions=[],  # Not in old format
                        main_flow=[],  # Not in old format
                        alternative_flows=uc_data.get("edge_cases", []),
                        required_inputs=[],  # Not in old format
                        sql_intent=uc_data.get("reasoning", ""),  # Use reasoning as sql_intent
                        expected_output="",  # Not in old format
                        validation_metrics=[],  # Not in old format
                        confidence_reference=None,
                        confidence_score=float(uc_data.get("query_feasibility_score", 0.5)),
                        # Optional fields
                    table=uc_data.get("table") if uc_data.get("table") != "null" else (request.table if request.scope in ["table", "column"] else None),
                    column=uc_data.get("column") if uc_data.get("column") != "null" else (request.column if request.scope == "column" else None),
                        snapshot_id=uc_data.get("snapshot_id", request.snapshot_id),
                        # Legacy fields
                        usecase_name=uc_data.get("usecase_name") or uc_data.get("name", "Unnamed Use Case"),
                    description=uc_data.get("description", ""),
                    expected_sql_patterns=uc_data.get("expected_sql_patterns", []),
                    required_relations=uc_data.get("required_relations", []),
                    edge_cases=uc_data.get("edge_cases", []),
                    sample_examples=uc_data.get("sample_examples", []),
                    query_feasibility_score=float(uc_data.get("query_feasibility_score", 0.5)),
                    reasoning=uc_data.get("reasoning", ""),
                    typical_questions=uc_data.get("typical_questions"),
                    example_queries=uc_data.get("example_queries"),
                    output_type=uc_data.get("output_type"),
                    main_tables=uc_data.get("main_tables"),
                    risk_notes=uc_data.get("risk_notes")
                )
                validated_use_cases.append(validated_uc)
            
            if not validated_use_cases:
                raise HTTPException(status_code=500, detail="No valid use cases generated")
            
            # Update generation log with success
            # Note: response_hash field doesn't exist in AiGenerationLog model
            await session.commit()
            
            # Generate system prompt examples (for backward compatibility)
            system_prompt_examples = "\n".join([
                f"Example {i+1}: {uc.title or uc.usecase_name or 'Unnamed'}\nDescription: {uc.business_goal or uc.description or ''}\n"
                for i, uc in enumerate(validated_use_cases[:3])
            ])
            
            logger.info(f"Successfully generated {len(validated_use_cases)} use cases")
            
            return SmartUseCaseBuilderResponse(
                use_cases=validated_use_cases,
                generation_log_id=generation_log.id,
                system_prompt_examples=system_prompt_examples
            )
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}", exc_info=True)
            generation_log.error_message = str(e)
            await session.commit()
            raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during use case generation: {e}", exc_info=True)
        try:
            error_msg = str(e).encode(LOG_ENCODING, errors=LOG_ERROR_HANDLING).decode(LOG_ENCODING, errors=LOG_ERROR_HANDLING)
            raise HTTPException(status_code=500, detail=f"Unexpected error: {error_msg}")
        except:
            raise HTTPException(status_code=500, detail="Unexpected error during use case generation")


@router.post("/save/{generation_log_id}")
async def save_generated_use_cases(
    generation_log_id: int,
    selected_use_cases: List[Dict[str, Any]],
    session: AsyncSession = Depends(get_db_session)
):
    """Save selected generated use cases to the database using DBConnector.save_usecase pattern"""
    
    logger.info(f"[USECASE_SAVE] Starting save process for generation_log_id={generation_log_id}, use_cases_count={len(selected_use_cases)}")
    
    # Get the generation log
    log_result = await session.execute(
        select(AiGenerationLog).where(AiGenerationLog.id == generation_log_id)
    )
    generation_log = log_result.scalar_one_or_none()
    if not generation_log:
        logger.error(f"[USECASE_SAVE] Generation log {generation_log_id} not found")
        raise HTTPException(status_code=404, detail="Generation log not found")
    
    logger.info(f"[USECASE_SAVE] Found generation log: snapshot_id={generation_log.schema_snapshot_id}")
    
    # Get version information
    dict_count_result = await session.execute(
        select(func.count(DataDictionary.id)).where(
            DataDictionary.schema_snapshot_id == generation_log.schema_snapshot_id
        )
    )
    dict_version = dict_count_result.scalar()
    
    rel_count_result = await session.execute(
        select(func.count(Relationship.id)).where(
            Relationship.schema_snapshot_id == generation_log.schema_snapshot_id
        )
    )
    rel_version = rel_count_result.scalar()
    
    logger.info(f"[USECASE_SAVE] Dictionary version: {dict_version}, Relationships version: {rel_version}")
    logger.info(f"[USECASE_SAVE] Processing {len(selected_use_cases)} use cases to save")
    
    saved_use_cases = []
    
    for idx, uc_data in enumerate(selected_use_cases):
        logger.debug(f"[USECASE_SAVE] Processing use case {idx + 1}/{len(selected_use_cases)}: {uc_data.get('title') or uc_data.get('name') or uc_data.get('usecase_name')}")
        # Extract data (support both new and legacy formats)
        usecase_name = uc_data.get("title") or uc_data.get("usecase_name") or uc_data.get("name", "Unnamed Use Case")
        description = uc_data.get("business_goal") or uc_data.get("description", "")
        
        # Ensure typical_questions and example_queries are arrays
        typical_questions = uc_data.get("typical_questions")
        if not typical_questions:
            typical_questions = []
        elif not isinstance(typical_questions, list):
            typical_questions = [typical_questions] if typical_questions else []
        
        example_queries = uc_data.get("example_queries")
        if not example_queries:
            example_queries = []
        elif not isinstance(example_queries, list):
            example_queries = [example_queries] if example_queries else []
        
        # Filter out placeholder queries and generic questions - MAINTAIN PAIRING AND ORDER
        # Process as pairs to ensure questions and queries stay matched
        filtered_pairs = []
        max_len = max(len(typical_questions), len(example_queries))
        
        for i in range(max_len):
            q = typical_questions[i] if i < len(typical_questions) else None
            query = example_queries[i] if i < len(example_queries) else None
            
            # Skip if either is missing (must have both question and query)
            if not q or not query:
                continue
            
            # Skip generic placeholder queries
            if isinstance(query, str):
                query_lower = query.lower().strip()
                if "information_schema" in query_lower or "select * from information_schema" in query_lower:
                    logger.warning(f"[USECASE_SAVE] Skipping placeholder query: {query[:50]}...")
                    continue
            
            # Skip generic questions
            if isinstance(q, str):
                q_lower = q.lower().strip()
                if "what information can i get" in q_lower or "what can i get" in q_lower:
                    logger.warning(f"[USECASE_SAVE] Skipping generic question: {q[:50]}...")
                    continue
            
            # Add as a pair to maintain order
            filtered_pairs.append({
                "question": q,
                "query": query
            })
        
        # Extract filtered lists maintaining order
        if filtered_pairs:
            typical_questions = [pair["question"] for pair in filtered_pairs]
            example_queries = [pair["query"] for pair in filtered_pairs]
        else:
            # If no valid pairs, ensure both lists are empty
            typical_questions = []
            example_queries = []
        
        # Final validation: ensure questions and queries match in count (should always be true after filtering)
        if len(typical_questions) != len(example_queries):
            logger.error(f"[USECASE_SAVE] CRITICAL: Use case '{usecase_name}' has mismatched counts after filtering ({len(typical_questions)} questions vs {len(example_queries)} queries). This should not happen!")
            # Force match by truncating to minimum
            min_length = min(len(typical_questions), len(example_queries))
            typical_questions = typical_questions[:min_length] if typical_questions else []
            example_queries = example_queries[:min_length] if example_queries else []
        
        # Ensure at least 3 question/query pairs exist (required by business rules)
        if len(typical_questions) < 3:
            logger.warning(f"[USECASE_SAVE] Use case '{usecase_name}' has only {len(typical_questions)} questions/queries, expected at least 3. This may indicate a problem with the LLM generation.")
            # Don't add placeholders - log the issue and use what we have
        
        # Map output type
        output_type_to_style = {
            "aggregation": "numeric",
            "list": "summary",
            "trend": "analytical",
            "comparison": "analytical",
            "report": "analytical"
        }
        output_type = uc_data.get("output_type", "aggregation")
        output_style = output_type_to_style.get(output_type, "analytical")
        
        # Get wizard inputs from generation log
        wizard_inputs = {}
        if generation_log.optional_notes:
            try:
                notes_parts = generation_log.optional_notes.split(', ')
                for part in notes_parts:
                    if 'Output preference:' in part:
                        wizard_inputs['output_preference'] = part.replace('Output preference: ', '')
                    elif 'Question types:' in part:
                        wizard_inputs['typical_questions'] = part.replace('Question types: ', '').split(',')
            except (ValueError, AttributeError):
                pass
        
        # Create use case record
        try:
            # Ensure we have valid values
            if not usecase_name or usecase_name.strip() == "":
                usecase_name = "Unnamed Use Case"
            if not description or description.strip() == "":
                description = "No description provided"
            
            use_case = UseCase(
                schema_snapshot_id=generation_log.schema_snapshot_id,
                name=usecase_name.strip(),
                business_goal=description.strip(),
                example_questions=json.dumps(typical_questions) if typical_questions else json.dumps([]),
                example_queries=json.dumps(example_queries) if example_queries else json.dumps([]),
                output_style=output_style,
                is_ai_generated=True,
                generation_log_id=generation_log.id,
                generation_version=1,
                business_context=generation_log.business_domain,
                primary_audience=json.dumps(generation_log.target_user.split(',') if generation_log.target_user else []),
                typical_questions=json.dumps(wizard_inputs.get('typical_questions', [])),
                output_preference=wizard_inputs.get('output_preference', ''),
                dictionary_version=dict_version,
                relationships_version=rel_version
            )
            
            session.add(use_case)
            saved_use_cases.append(use_case)
            logger.info(f"[USECASE_SAVE] Added use case '{usecase_name}' to session (snapshot_id={generation_log.schema_snapshot_id})")
        except Exception as e:
            logger.error(f"[USECASE_SAVE] Failed to create use case '{usecase_name}': {e}", exc_info=True)
            raise
    
    try:
        logger.info(f"[USECASE_SAVE] Committing {len(saved_use_cases)} use cases to database")
        await session.commit()
        logger.info(f"[USECASE_SAVE] Successfully committed use cases")
        
        # Refresh to get IDs
        for uc in saved_use_cases:
            try:
                await session.refresh(uc)
                logger.debug(f"[USECASE_SAVE] Refreshed use case ID: {uc.id}, Name: {uc.name}")
            except Exception as e:
                logger.warning(f"[USECASE_SAVE] Failed to refresh use case: {e}")
        
        logger.info(f"[USECASE_SAVE] Successfully saved {len(saved_use_cases)} use cases with IDs: {[uc.id for uc in saved_use_cases]}")
        
        return {
            "message": f"Successfully saved {len(saved_use_cases)} use cases",
            "saved_use_cases": [
                {
                    "id": uc.id,
                    "name": uc.name,
                    "business_goal": uc.business_goal
                } for uc in saved_use_cases
            ]
        }
    except Exception as e:
        await session.rollback()
        logger.error(f"[USECASE_SAVE] Failed to commit use cases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save use cases: {str(e)}")
