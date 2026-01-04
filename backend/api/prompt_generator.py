from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
from datetime import datetime

from .db_models import (
    SchemaMetadata, DataDictionary, Relationship, UseCase,
    GeneratedPrompt, LLMModel, SchemaSnapshot, get_db_session
)


router = APIRouter()


class PromptGenerationRequest(BaseModel):
    schema_snapshot_id: int
    include_data_dictionary: bool = True
    include_relationships: bool = True
    include_use_cases: bool = True


class GeneratedPromptResponse(BaseModel):
    id: int
    version: int
    prompt_text: str
    schema_snapshot_name: str
    created_at: str


def build_deterministic_system_prompt(
    schema_data: List[dict],
    data_dictionary: List[dict],
    relationships: List[dict],
    use_cases: List[dict],
    model_name: str = "Unknown Model"
) -> str:
    """
    Deterministically build a system prompt for Text-to-SQL agent.

    Algorithm:
    1. Start with fixed SYSTEM ROLE section
    2. Inject schema information (tables & columns)
    3. Inject data dictionary with higher priority than schema
    4. Inject explicit relationships ONLY
    5. Inject business context if provided
    6. Append strict SQL rules
    7. Append refusal rules for unknown questions
    8. Append output formatting rules
    """

    prompt_lines = []

    # 1. Fixed SYSTEM ROLE section
    prompt_lines.extend([
        "# 🧠 Chat with Database – Standard System Prompt",
        "",
        "## Role",
        "You are an expert **Text-to-SQL Assistant**.",
        "Your job is to convert natural language questions into **accurate, safe, and executable SQL queries**.",
        "",
        "You MUST strictly follow the provided database knowledge.",
        "You are not allowed to guess or hallucinate.",
        "",
        "---",
        "",
        "## 📦 Available Knowledge",
        "",
        "### 1. Database Schema",
        "The database schema includes:",
        "- Tables",
        "- Columns",
        "- Primary keys",
        "- Foreign keys",
        "- Data types",
        "",
        "> You may ONLY use tables and columns that exist in the schema.",
        "",
    ])

    # 2. Inject schema information
    if schema_data:
        prompt_lines.extend([
            "### Schema Tables and Columns",
            "",
        ])

        # Group by schema and table
        schema_tables = {}
        for item in schema_data:
            schema_key = item['schema_name']
            table_key = item['table_name']

            if schema_key not in schema_tables:
                schema_tables[schema_key] = {}
            if table_key not in schema_tables[schema_key]:
                schema_tables[schema_key][table_key] = []

            schema_tables[schema_key][table_key].append({
                'name': item['column_name'],
                'type': item['column_type'],
                'is_primary_key': item['is_primary_key'],
                'is_foreign_key': item['is_foreign_key'],
                'foreign_key_table': item.get('foreign_key_table'),
                'foreign_key_column': item.get('foreign_key_column')
            })

        for schema_name, tables in schema_tables.items():
            for table_name, columns in tables.items():
                prompt_lines.append(f"#### {schema_name}.{table_name}")
                prompt_lines.append("")
                for col in columns:
                    pk_marker = " (PRIMARY KEY)" if col['is_primary_key'] else ""
                    fk_marker = f" (FOREIGN KEY -> {col['foreign_key_table']}.{col['foreign_key_column']})" if col['is_foreign_key'] else ""
                    prompt_lines.append(f"- {col['name']} ({col['type']}){pk_marker}{fk_marker}")
                prompt_lines.append("")

    # 3. Inject data dictionary with higher priority
    if data_dictionary:
        prompt_lines.extend([
            "### 2. Data Dictionary (Very Important)",
            "Each table and column has a business description.",
            "",
            "Rules:",
            "- Prefer the data dictionary over assumptions",
            "- If column meaning is unclear, use the dictionary explanation",
            "- Do NOT infer business meaning without dictionary support",
            "",
        ])

        for item in data_dictionary:
            table_key = f"{item['schema_name']}.{item['table_name']}"

            if item['column_name']:
                prompt_lines.append(f"#### Column: {table_key}.{item['column_name']}")
            else:
                prompt_lines.append(f"#### Table: {table_key}")

            if item['description']:
                prompt_lines.append(f"Description: {item['description']}")

            if item['example_values']:
                try:
                    examples = json.loads(item['example_values'])
                    if examples:
                        prompt_lines.append(f"Example values: {', '.join(examples)}")
                except (json.JSONDecodeError, TypeError):
                    prompt_lines.append(f"Example values: {item['example_values']}")

            if item['synonyms']:
                prompt_lines.append(f"Synonyms: {item['synonyms']}")

            if item['is_sensitive']:
                prompt_lines.append("⚠️ SENSITIVE DATA - Handle with care")

            prompt_lines.append("")

    # 4. Inject explicit relationships ONLY
    if relationships:
        prompt_lines.extend([
            "### 3. Explicit Relationships",
            "Relationships between tables are explicitly defined.",
            "",
            "Rules:",
            "- Use ONLY defined relationships",
            "- Do NOT create implicit or guessed joins",
            "- Always use explicit JOIN syntax",
            "",
        ])

        for rel in relationships:
            prompt_lines.append(f"- {rel['source_table']}.{rel['source_column']} {rel['join_type']} JOIN {rel['target_table']}.{rel['target_column']}")
            if rel['description']:
                prompt_lines.append(f"  Description: {rel['description']}")
            prompt_lines.append("")

    # 4. Inject use cases if provided
    if use_cases:
        prompt_lines.extend([
            "### 4. Business Use Cases",
            "The following use cases describe common business scenarios:",
            "",
        ])

        for uc in use_cases:
            prompt_lines.append(f"#### Use Case: {uc['name']}")
            prompt_lines.append(f"**Business Goal:** {uc['business_goal']}")
            prompt_lines.append(f"**Output Style:** {uc['output_style']}")

            if uc['example_questions']:
                try:
                    questions = json.loads(uc['example_questions'])
                    if questions:
                        prompt_lines.append("**Example Questions:**")
                        for q in questions[:3]:  # Limit to 3 examples
                            prompt_lines.append(f"- {q}")
                except (json.JSONDecodeError, TypeError):
                    pass

            if uc['example_queries']:
                try:
                    queries = json.loads(uc['example_queries'])
                    if queries:
                        prompt_lines.append("**Example SQL Patterns:**")
                        for sql in queries[:2]:  # Limit to 2 examples
                            prompt_lines.append(f"```sql")
                            prompt_lines.append(f"{sql}")
                            prompt_lines.append("```")
                except (json.JSONDecodeError, TypeError):
                    pass

            prompt_lines.append("")


    # 6-8. Append strict SQL rules, refusal rules, and output formatting
    prompt_lines.extend([
        "---",
        "",
        "## 🎯 Your Task",
        "",
        "Given:",
        "- A natural language question from the user",
        "",
        "You must:",
        "1. Understand the business intent",
        "2. Identify relevant tables and columns",
        "3. Build a correct SQL SELECT query",
        "",
        "---",
        "",
        "## 📐 SQL Generation Rules (STRICT)",
        "",
        "- ONLY generate `SELECT` queries",
        "- NEVER generate `INSERT`, `UPDATE`, `DELETE`, `DROP`, or `ALTER`",
        "- Always use explicit `JOIN`",
        "- Always use table aliases",
        "- Use `LIMIT 50` unless aggregation requires otherwise",
        "- Never select `*` — always specify columns",
        "- Use correct aggregation functions when needed",
        "- Do NOT guess missing fields",
        "- Do NOT fabricate filters or conditions",
        "",
        "---",
        "",
        "## 🚨 Error Handling Rules",
        "",
        "If the question:",
        "- Cannot be answered with the provided schema",
        "- Requires missing tables or columns",
        "- Is ambiguous or underspecified",
        "",
        "Then respond with:",
        "> `The question cannot be answered using the available database schema.`",
        "",
        "Do NOT attempt a partial or guessed query.",
        "",
        "---",
        "",
        "## 🧪 Output Format",
        "",
        "Return ONLY the SQL query.",
        "",
        "No explanations.",
        "No comments.",
        "No markdown.",
        "",
        "---",
        "",
        "## ✅ Example Behavior",
        "",
        "User Question:",
        "\"لیست سفارش‌هایی که مجموع مبلغ آن‌ها بیشتر از ۱۰۰ میلیون تومان است\"",
        "",
        "Expected Behavior:",
        "- Identify orders table",
        "- Identify total amount column",
        "- Use GROUP BY if needed",
        "- Apply HAVING clause",
        "- Limit results",
        "",
        "---",
        "",
        "## 🔒 Safety Constraints",
        "",
        "- Read-only access",
        "- No schema modification",
        "- No performance-heavy queries",
        "- No subqueries unless necessary",
        "",
        "---",
        "",
        "## 🧠 Final Reminder",
        "",
        "Accuracy is more important than completeness.",
        "If unsure — refuse.",
    ])

    return '\n'.join(prompt_lines)


@router.post("/generate", response_model=GeneratedPromptResponse)
async def generate_prompt(
    request: PromptGenerationRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Generate a new system prompt using deterministic algorithm"""

    # Get specified schema snapshot
    schema_result = await session.execute(
        select(SchemaSnapshot).where(SchemaSnapshot.id == request.schema_snapshot_id)
    )
    schema_snapshot = schema_result.scalar_one_or_none()
    if not schema_snapshot:
        raise HTTPException(status_code=400, detail=f"Schema snapshot with ID {request.schema_snapshot_id} not found.")

    # Use a default model reference (no active model required)
    model_result = await session.execute(select(LLMModel).limit(1))
    model = model_result.scalar_one_or_none()
    if not model:
        # Create a dummy model for template generation
        model = type('obj', (object,), {
            'id': 1,
            'name': 'Template Generator',
            'model_name': 'template'
        })()

    # Collect schema data
    schema_data = []
    schema_metadata_result = await session.execute(
        select(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == schema_snapshot.id)
    )
    schema_items = schema_metadata_result.scalars().all()
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

    # Collect data dictionary if requested
    data_dictionary = []
    if request.include_data_dictionary:
        dd_result = await session.execute(
            select(DataDictionary).where(DataDictionary.schema_snapshot_id == schema_snapshot.id)
        )
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

    # Collect relationships if requested
    relationships = []
    if request.include_relationships:
        rel_result = await session.execute(
            select(Relationship).where(Relationship.schema_snapshot_id == schema_snapshot.id)
        )
        rel_items = rel_result.scalars().all()
        for item in rel_items:
            relationships.append({
                "source_table": item.source_table,
                "source_column": item.source_column,
                "target_table": item.target_table,
                "target_column": item.target_column,
                "join_type": item.join_type,
                "description": item.description
            })

    # Collect use cases if requested
    use_cases = []
    if request.include_use_cases:
        uc_result = await session.execute(
            select(UseCase).where(UseCase.schema_snapshot_id == schema_snapshot.id)
        )
        uc_items = uc_result.scalars().all()
        for item in uc_items:
            use_cases.append({
                "name": item.name,
                "business_goal": item.business_goal,
                "example_questions": item.example_questions,
                "example_queries": item.example_queries,
                "output_style": item.output_style
            })

    # Build deterministic prompt
    prompt_text = build_deterministic_system_prompt(
        schema_data=schema_data,
        data_dictionary=data_dictionary,
        relationships=relationships,
        use_cases=use_cases,
        model_name=model.name
    )

    # Get next version number for this schema snapshot
    version_result = await session.execute(
        select(func.max(GeneratedPrompt.version))
        .where(GeneratedPrompt.schema_snapshot_id == schema_snapshot.id)
    )
    max_version = version_result.scalar() or 0
    next_version = max_version + 1

    # Save the generated prompt
    generated_prompt = GeneratedPrompt(
        schema_snapshot_id=schema_snapshot.id,
        version=next_version,
        prompt_text=prompt_text,
        model_id=model.id
    )

    session.add(generated_prompt)
    await session.commit()
    await session.refresh(generated_prompt)

    return GeneratedPromptResponse(
        id=generated_prompt.id,
        version=generated_prompt.version,
        prompt_text=generated_prompt.prompt_text,
        schema_snapshot_name=schema_snapshot.name,
        created_at=generated_prompt.created_at.isoformat()
    )


@router.get("/", response_model=List[GeneratedPromptResponse])
async def get_generated_prompts(session: AsyncSession = Depends(get_db_session)):
    """Get all generated prompts"""
    result = await session.execute(
        select(GeneratedPrompt, SchemaSnapshot.name)
        .join(SchemaSnapshot, GeneratedPrompt.schema_snapshot_id == SchemaSnapshot.id)
        .order_by(GeneratedPrompt.created_at.desc())
    )

    prompts = []
    for prompt, schema_name in result:
        prompts.append(GeneratedPromptResponse(
            id=prompt.id,
            version=prompt.version,
            prompt_text=prompt.prompt_text,
            schema_snapshot_name=schema_name,
            created_at=prompt.created_at.isoformat()
        ))

    return prompts


@router.get("/latest", response_model=GeneratedPromptResponse)
async def get_latest_prompt(session: AsyncSession = Depends(get_db_session)):
    """Get the latest generated prompt"""
    result = await session.execute(
        select(GeneratedPrompt, SchemaSnapshot.name)
        .join(SchemaSnapshot, GeneratedPrompt.schema_snapshot_id == SchemaSnapshot.id)
        .order_by(GeneratedPrompt.created_at.desc())
        .limit(1)
    )

    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="No prompts found")

    prompt, schema_name = row
    return GeneratedPromptResponse(
        id=prompt.id,
        version=prompt.version,
        prompt_text=prompt.prompt_text,
        schema_snapshot_name=schema_name,
        created_at=prompt.created_at.isoformat()
    )


@router.get("/{id}", response_model=GeneratedPromptResponse)
async def get_prompt_by_id(id: int, session: AsyncSession = Depends(get_db_session)):
    """Get a specific prompt by ID"""
    result = await session.execute(
        select(GeneratedPrompt, SchemaSnapshot.name)
        .join(SchemaSnapshot, GeneratedPrompt.schema_snapshot_id == SchemaSnapshot.id)
        .where(GeneratedPrompt.id == id)
    )

    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt, schema_name = row
    return GeneratedPromptResponse(
        id=prompt.id,
        version=prompt.version,
        prompt_text=prompt.prompt_text,
        schema_snapshot_name=schema_name,
        created_at=prompt.created_at.isoformat()
    )















