"""
AI Dictionary Generation Prompt Builder
Single deterministic prompt template for data dictionary generation
"""
import json
from typing import List, Tuple


class DictionaryPromptBuilder:
    """Deterministic prompt builder for AI dictionary generation"""

    @staticmethod
    def build_prompt(
        schema_name: str,
        table_name: str,
        columns: List[Tuple[str, str]],  # [(column_name, column_type), ...]
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str = "persian"
    ) -> str:
        """Build deterministic prompt for table description generation

        Args:
            schema_name: Database schema name
            table_name: Table name
            columns: List of (column_name, column_type) tuples
            business_domain: Business domain context
            database_description: Database purpose description
            target_user: Target user type
            language: Output language (persian/english)

        Returns:
            Deterministic prompt string
        """
        # Format column information
        column_info = []
        for col_name, col_type in columns[:20]:  # Limit to first 20 columns for token efficiency
            column_info.append(f"  - {col_name}: {col_type}")

        columns_text = "\n".join(column_info)

        # Language-specific instructions
        if language.lower() == "persian":
            lang_instructions = """
**دستورالعمل‌های زبان:**
- تمام توصیفات باید به زبان فارسی باشد
- از اصطلاحات فنی مناسب فارسی استفاده کنید
- جملات باید کامل و معنادار باشند"""
        else:
            lang_instructions = """
**Language Instructions:**
- All descriptions must be in English
- Use appropriate technical terminology
- Sentences should be complete and meaningful"""

        prompt = f"""# Data Dictionary Generation Task

## Database Context
- **Schema**: {schema_name}
- **Table**: {table_name}
- **Business Domain**: {business_domain}
- **Database Purpose**: {database_description}
- **Target Users**: {target_user}

## Table Structure
Columns ({len(columns)} total):
{columns_text}

## Task
Generate comprehensive descriptions for this database table and its columns.

## Output Requirements
You MUST respond with valid JSON in this exact format:
{{
  "table_description": "Brief description of what this table represents in the business context",
  "column_descriptions": {{
    "column_name_1": "Description of column purpose and content",
    "column_name_2": "Description of column purpose and content",
    ...
  }}
}}

## Guidelines
- **table_description**: 1-2 sentences explaining the table's business purpose
- **column_descriptions**: Each column should have a clear, concise description
- Focus on business meaning, not technical details
- Be specific about data types and relationships where relevant
- Keep descriptions actionable for {target_user}

{lang_instructions}

## Important
- Output must be valid JSON only
- No additional text or explanations outside the JSON structure
- All descriptions should be non-empty strings
- Use the exact column names as provided

JSON Output:"""

        return prompt.strip()

    @staticmethod
    def validate_prompt_structure(prompt: str) -> bool:
        """Validate that prompt contains required structural elements"""
        required_elements = [
            "Data Dictionary Generation Task",
            "Database Context",
            "Table Structure",
            "Output Requirements",
            "You MUST respond with valid JSON",
            '"table_description"',
            '"column_descriptions"',
            "JSON Output:"
        ]

        return all(element in prompt for element in required_elements)








