"""
Dictionary Generation Prompt Builders
Reusable functions for building schema-aware prompts
"""

import json
from typing import Dict, Any, List, Optional
from core.config import (
    LANGUAGE_MAP, 
    SCOPE_MAP, 
    DB_TYPE_MAP,
    MAX_COLUMNS_PER_TABLE,
    MAX_TABLES_PER_RESPONSE,
    MAX_JSON_OUTPUT_CHARS
)


def build_schema_context(schema_info: Dict[str, Any]) -> str:
    """
    Build schema context string for prompt injection.
    Returns EXACT same format as before for compatibility.
    
    Args:
        schema_info: Dictionary with schema_name, table_name, columns, relationships
        
    Returns:
        Formatted schema context string
    """
    schema_name = schema_info.get("schema_name", "")
    table_name = schema_info.get("table_name", "")
    columns = schema_info.get("columns", [])
    relationships = schema_info.get("relationships", [])
    
    # Format columns with constraints (same format as before)
    columns_text = "\n".join([
        f"  - {col['name']}: {col['data_type']}"
        + (" (Primary Key)" if col.get('is_primary_key') else "")
        + (" (Foreign Key -> " + f"{col.get('foreign_key_table', '')}.{col.get('foreign_key_column', '')})" if col.get('is_foreign_key') else "")
        + (" (Nullable)" if not col.get('is_primary_key') else " (NOT NULL)")
        for col in columns
    ])
    
    # Format relationships (same format as before)
    relationships_text = ""
    if relationships:
        rel_lines = []
        for rel in relationships:
            to_table = rel.get("to_table", "")
            to_column = rel.get("to_column", "")
            from_column = rel.get("from_column", "")
            if to_table and to_column:
                rel_lines.append(f"  - {from_column} -> {to_table}.{to_column}")
        if rel_lines:
            relationships_text = "\n".join(rel_lines)
    else:
        relationships_text = "  No foreign key relationships found"
    
    return f"""### SCHEMA:
**Table:** {schema_name}.{table_name}

**Columns:**
{columns_text}

**Foreign Key Relationships:**
{relationships_text}"""


def build_usecase_context(
    business_domain: str,
    audience: str,
    db_type: str,
    language: str
) -> str:
    """
    Build use case context string for prompt injection.
    Returns EXACT same format as before for compatibility.
    
    Args:
        business_domain: Business domain context
        audience: Target audience
        db_type: Database type
        language: Output language
        
    Returns:
        Formatted use case context string
    """
    language_name = LANGUAGE_MAP.get(language.lower(), language)
    db_type_name = DB_TYPE_MAP.get(db_type.lower(), db_type)
    
    return f"""### BUSINESS CONTEXT:
Domain: {business_domain}
Audience: {audience}
Database Type: {db_type_name}
Language Preference: {language_name}"""


def build_relationship_map(schema_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build relationship map from schema info.
    Returns dictionary with relationship information.
    
    Args:
        schema_info: Dictionary with schema_name, table_name, columns, relationships
        
    Returns:
        Dictionary with relationship mappings
    """
    relationships = schema_info.get("relationships", [])
    
    # Build relationship map
    relationship_map = {}
    for rel in relationships:
        from_column = rel.get("from_column", "")
        to_table = rel.get("to_table", "")
        to_column = rel.get("to_column", "")
        
        if from_column and to_table and to_column:
            if from_column not in relationship_map:
                relationship_map[from_column] = []
            relationship_map[from_column].append({
                "table": to_table,
                "column": to_column
            })
    
    return relationship_map


def build_dictionary_prompt(
    job: Any,  # DictionaryJob type
    table_task: Any,  # TableTask type
    schema_info: Dict[str, Any],
    sample_data: List[Dict[str, Any]],
    db_type: str = "Unknown"
) -> str:
    """
    Build complete dictionary generation prompt.
    Returns EXACT same format as before for compatibility.
    
    Args:
        job: DictionaryJob instance
        table_task: TableTask instance
        schema_info: Schema information dictionary
        sample_data: Sample data rows
        db_type: Database type
        
    Returns:
        Complete prompt string
    """
    # Map scope to specification format
    # Handle both enum and string values
    scope_value = job.scope.value if hasattr(job.scope, 'value') else str(job.scope)
    snapshot_scope = SCOPE_MAP.get(scope_value.lower(), "SINGLE_TABLE")
    
    # Build schema context
    schema_context = build_schema_context(schema_info)
    
    # Format sample data as JSON (5 unique rows)
    sample_json = "[]"
    if sample_data:
        unique_rows = []
        seen = set()
        for row in sample_data[:5]:
            row_str = json.dumps(row, sort_keys=True, default=str)
            if row_str not in seen:
                seen.add(row_str)
                unique_rows.append(row)
                if len(unique_rows) >= 5:
                    break
        sample_json = json.dumps(unique_rows, default=str, ensure_ascii=False, indent=2)
    
    # Build use case context
    usecase_context = build_usecase_context(
        job.business_domain,
        job.audience,
        db_type,
        job.language
    )
    
    # Build complete prompt (same format as before)
    prompt = f"""You are an AI specializing in producing **clean, valid, fully-parsable JSON only**.
Do not include explanations outside JSON.

## ⚠️ CRITICAL OUTPUT RULES
1. Response must be a **single valid JSON object** - NO markdown, NO comments, NO extra text
2. Never generate more than **{MAX_TABLES_PER_RESPONSE} table objects** per response batch
3. Never exceed **{MAX_JSON_OUTPUT_CHARS} characters** in the JSON output
4. Never exceed **{MAX_COLUMNS_PER_TABLE} columns** inside any table
5. If output gets long, **split into multiple queue responses** instead of continuing in the same JSON
6. JSON must never be truncated. You MUST:
   - Close all `{{` `}}` and `[` `]`
   - Ensure every item is separated by commas
   - Never leave a trailing comma
   - Ensure all strings are properly closed with `"`
7. Avoid verbose text. Keep all descriptions concise, practical, and structured
8. Ensure all sampled DB rows are converted into **short real examples**, not full dataset dumps
9. Replace vague queries like `COUNT(*)` with **schema-aware insights** if intent is detected
10. Before returning JSON, run an internal validation check to guarantee:
    ```python
    json.loads(output)
    ```
    will never fail

## 🎯 Supported Scopes
You must support:
1. FULL_SNAPSHOT → All tables in snapshot
2. SINGLE_TABLE → Only one requested table
3. SINGLE_COLUMN → Only one requested column inside a table

## 📥 Inputs Provided by Backend
You will receive these at runtime:
- form data (business_domain, audience, language, etc.)
- database schema for target scope (tables, columns, PK, FK, indexes, constraints)
- 5 unique real rows sampled from each table (already attached in prompt)
- database type (PostgreSQL, MySQL, SQL Server, SQLite, Oracle, etc.)
- active LLM model connection info via ModelConnector service
- database access via existing DatabaseConnector module

## 🧠 Strict Generation Rules
1. NEVER hallucinate. Only infer meaning from real sample data and schema.
2. Output MUST be **VALID JSON ONLY**, no markdown, no comments, no extra text.
3. Descriptions must be **business-aware, short, real-world and useful**.
4. If meaning cannot be inferred → return `"description": "Not enough data to infer"`
5. For each requested scope:

### Table Level (if applicable)
Return:
- `business_description` → max 120 characters, clear and real-world usage
- `usage_notes` → max 100 characters, who uses it, when, important considerations
- `sample_insights` → max 5 items, each max 60 characters, key insights from sample data patterns

### Column Level (if applicable)
For each column you must generate:
- `description` → max 70 characters, business meaning
- `example` → max 40 characters, exact value taken from provided sample rows
- `use_cases` → max 3 items, each max 50 characters, real business use cases
- `synonyms` → max 3 items, each max 30 characters, alternative names or aliases commonly used for this column

### Relationship Level (if applicable)
If table has foreign keys or relations:
Return:
- `related_table`
- `relation_type` → ONE_TO_ONE / ONE_TO_MANY / MANY_TO_ONE / MANY_TO_MANY
- `join_purpose` → 1 short business explanation of why these tables join

## 🧾 Required JSON Schema (must match exactly)

For SINGLE_TABLE scope, return a single table object (NOT wrapped in "tables" array):

{{
  "table_name": "{schema_info.get('table_name', '')}",
  "business_description": "string (max 120 chars)",
  "usage_notes": "string (max 100 chars)",
  "sample_insights": ["string (each max 60 chars, max 5 items)"],
  "columns": [
    {{
      "name": "string",
      "type": "string",
      "description": "string (max 70 chars)",
      "example": "string (max 40 chars)",
      "use_cases": ["string (each max 50 chars, max 3 items)"],
      "synonyms": ["string (each max 30 chars, max 3 items)"]
    }}
  ]
}}

**IMPORTANT:**
- Return ONLY this JSON structure, no wrapper, no markdown
- All string fields have character limits - enforce them strictly
- All arrays have item limits - enforce them strictly
- Ensure JSON is complete and valid before returning
- Test internally: `json.loads(your_output)` must succeed

## 📊 Schema Information

{schema_context}

### SAMPLE DATA:
{sample_json}

{usecase_context}

## ⚙️ Additional System Behavior
- You may be asked to generate query hints to retrieve more context if needed, but NOT required
- You must write dictionary content that can be stored in DB directly without transformation
- Keep structure clean for future extension (new fields may be added later)

## 💡 Quality Checklist Before Responding
✔ JSON valid and complete (all brackets closed)  
✔ Character limits enforced (120/70/50/40/30 chars)  
✔ Array limits enforced (max 5 insights, max 3 use_cases, max 3 synonyms)  
✔ No trailing commas  
✔ All strings properly closed  
✔ Business-aware, not generic  
✔ Examples only from sample data  
✔ No technical rambling  
✔ Internal validation: `json.loads(output)` succeeds  

## 🚨 Final Validation
Before returning your response:
1. Count all opening `{{` and closing `}}` - they must match
2. Count all opening `[` and closing `]` - they must match
3. Check for trailing commas before `}}` or `]`
4. Ensure all strings are closed with `"`
5. Verify total length is under {MAX_JSON_OUTPUT_CHARS} characters
6. Verify column count is under {MAX_COLUMNS_PER_TABLE}
7. Test: `json.loads(your_output)` must not raise any error

---

Now generate dictionary. Return ONLY valid JSON, no markdown, no comments, no extra text."""

    return prompt

