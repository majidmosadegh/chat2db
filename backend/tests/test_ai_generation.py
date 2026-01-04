#!/usr/bin/env python3

import asyncio
from api.smart_use_case_builder import build_use_case_generation_prompt, SmartUseCaseBuilderRequest
from api.db_models import SchemaMetadata, DataDictionary, Relationship

def test_prompt_building():
    print('Testing AI prompt building functionality...')

    # Create mock request
    request = SmartUseCaseBuilderRequest(
        snapshot_id=1,
        business_context="A retail management system for tracking sales and inventory",
        primary_audience=["manager", "analyst"],
        typical_questions=["numeric_stats", "comparative"],
        output_preference="summary_table",
        number_of_use_cases=3,
        language="english"
    )

    # Create mock schema metadata
    schema_metadata = [
        SchemaMetadata(
            id=1,
            schema_snapshot_id=1,
            table_name="products",
            column_name="product_id",
            column_type="INTEGER",
            is_primary_key=True,
            is_foreign_key=False,
            foreign_key_table=None,
            foreign_key_column=None
        ),
        SchemaMetadata(
            id=2,
            schema_snapshot_id=1,
            table_name="products",
            column_name="product_name",
            column_type="VARCHAR(100)",
            is_primary_key=False,
            is_foreign_key=False,
            foreign_key_table=None,
            foreign_key_column=None
        ),
        SchemaMetadata(
            id=3,
            schema_snapshot_id=1,
            table_name="sales",
            column_name="sale_id",
            column_type="INTEGER",
            is_primary_key=True,
            is_foreign_key=False,
            foreign_key_table=None,
            foreign_key_column=None
        )
    ]

    # Create mock data dictionary
    data_dictionary = [
        DataDictionary(
            id=1,
            schema_snapshot_id=1,
            table_name="products",
            column_name="product_name",
            description="Name of the product",
            example_values='["iPhone", "MacBook", "iPad"]',
            synonyms="product title,item name"
        ),
        DataDictionary(
            id=2,
            schema_snapshot_id=1,
            table_name="sales",
            column_name="sale_id",
            description="Unique identifier for each sale transaction",
            example_values=None,
            synonyms="transaction id,order id"
        )
    ]

    # Create mock relationships
    relationships = [
        Relationship(
            id=1,
            schema_snapshot_id=1,
            source_table="sales",
            source_column="product_id",
            target_table="products",
            target_column="product_id",
            relationship_type="Foreign Key",
            join_type="INNER JOIN",
            cardinality="Many-to-One",
            description="Each sale references a product"
        )
    ]

    # Create mock sample data
    sample_data = {
        "products": {
            "columns": ["product_id", "product_name"],
            "sample_rows": [
                {"product_id": "1", "product_name": "iPhone"},
                {"product_id": "2", "product_name": "MacBook"},
                {"product_id": "3", "product_name": "iPad"}
            ]
        },
        "sales": {
            "columns": ["sale_id", "product_id", "quantity", "sale_date"],
            "sample_rows": [
                {"sale_id": "1", "product_id": "1", "quantity": "2", "sale_date": "2024-01-15"},
                {"sale_id": "2", "product_id": "2", "quantity": "1", "sale_date": "2024-01-16"}
            ]
        }
    }

    try:
        # Build the prompt
        prompt = build_use_case_generation_prompt(
            request, schema_metadata, data_dictionary, relationships, sample_data, "english"
        )

        print('[OK] Prompt built successfully')
        print(f'[OK] Prompt length: {len(prompt)} characters')

        # Check that key sections are present
        required_sections = [
            "DATABASE SCHEMA:",
            "DATA DICTIONARY:",
            "RELATIONSHIPS:",
            "SAMPLE DATA FROM TABLES:",
            "BUSINESS CONTEXT:",
            "PRIMARY AUDIENCE:",
            "TYPICAL QUESTIONS TYPES:",
            "OUTPUT PREFERENCE:",
            "NUMBER OF USE CASES TO GENERATE:"
        ]

        missing_sections = []
        for section in required_sections:
            if section not in prompt:
                missing_sections.append(section)

        if missing_sections:
            print(f'[ERROR] Missing sections in prompt: {missing_sections}')
            return False
        else:
            print('[OK] All required sections present in prompt')

        # Check that the prompt ends with the correct instruction
        expected_end = 'Return ONLY a valid JSON array. Do not include any text before or after the JSON. Make sure the JSON is complete and properly formatted.'
        if prompt.strip().endswith(expected_end):
            print('[OK] Prompt ends with correct JSON instruction')
        else:
            print('[ERROR] Prompt does not end with correct JSON instruction')
            print(f'Expected to end with: "{expected_end}"')
            print(f'Actually ends with: "...{prompt.strip()[-100:]}"')
            return False

        print('[OK] AI prompt building test completed successfully')
        return True

    except Exception as e:
        print(f'[ERROR] Failed to build prompt: {e}')
        return False

if __name__ == "__main__":
    test_prompt_building()