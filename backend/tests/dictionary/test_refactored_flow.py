"""
Simple Test Script for Refactored Dictionary Generation Flow
Run with: python test_refactored_flow.py
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def test_config():
    """Test configuration constants"""
    print("Testing configuration constants...")
    from core.config import (
        DEFAULT_ROW_SAMPLE_LIMIT,
        MAX_CONCURRENT_JOBS,
        MAX_RETRIES,
        DB_TYPE_MAP,
        LANGUAGE_MAP
    )
    
    assert DEFAULT_ROW_SAMPLE_LIMIT == 5, "DEFAULT_ROW_SAMPLE_LIMIT should be 5"
    assert MAX_CONCURRENT_JOBS == 3, "MAX_CONCURRENT_JOBS should be 3"
    assert MAX_RETRIES == 2, "MAX_RETRIES should be 2"
    assert "sqlserver" in DB_TYPE_MAP, "DB_TYPE_MAP should contain sqlserver"
    assert "persian" in LANGUAGE_MAP, "LANGUAGE_MAP should contain persian"
    print("[OK] Configuration constants test passed")


def test_json_safety():
    """Test JSON safety utilities"""
    print("\nTesting JSON safety utilities...")
    from core.json_safety import (
        repair_json_text,
        parse_llm_json_response,
        ensure_valid_json_structure,
        validate_dictionary_result
    )
    
    # Test 1: Repair trailing comma
    broken_json = '{"name": "test",}'
    fixed = repair_json_text(broken_json)
    result = json.loads(fixed)
    assert result["name"] == "test", "Should repair trailing comma"
    print("[OK] Trailing comma repair test passed")
    
    # Test 2: Auto-close brackets
    incomplete = '{"name": "test"'
    fixed = ensure_valid_json_structure(incomplete)
    result = json.loads(fixed)
    assert result["name"] == "test", "Should auto-close brackets"
    print("[OK] Auto-close brackets test passed")
    
    # Test 3: Parse valid JSON
    valid_json = '{"tables": [{"table_name": "test", "columns": []}]}'
    result = parse_llm_json_response(valid_json)
    assert result is not None, "Should parse valid JSON"
    assert "tables" in result, "Should contain tables key"
    print("[OK] Parse valid JSON test passed")
    
    # Test 4: Parse markdown-wrapped JSON
    markdown_json = '```json\n{"tables": []}\n```'
    result = parse_llm_json_response(markdown_json)
    assert result is not None, "Should parse markdown-wrapped JSON"
    print("[OK] Parse markdown JSON test passed")
    
    # Test 5: Validate dictionary result
    valid_result = {
        "tables": [
            {
                "table_name": "test",
                "columns": [{"column_name": "id"}]
            }
        ]
    }
    assert validate_dictionary_result(valid_result), "Should validate correct structure"
    print("[OK] Validate dictionary result test passed")


def test_prompt_builders():
    """Test prompt builder functions"""
    print("\nTesting prompt builders...")
    from core.prompts.dictionary_prompts import (
        build_schema_context,
        build_usecase_context,
        build_relationship_map,
        build_dictionary_prompt
    )
    
    # Test schema context
    schema_info = {
        "schema_name": "dbo",
        "table_name": "Users",
        "columns": [
            {"name": "id", "data_type": "int", "is_primary_key": True},
            {"name": "name", "data_type": "varchar", "is_foreign_key": False}
        ],
        "relationships": [
            {"from_column": "id", "to_table": "Orders", "to_column": "user_id"}
        ]
    }
    context = build_schema_context(schema_info)
    assert "dbo.Users" in context, "Should contain table name"
    assert "id" in context, "Should contain column names"
    assert "Primary Key" in context, "Should contain constraints"
    print("[OK] Build schema context test passed")
    
    # Test use case context
    usecase_context = build_usecase_context(
        business_domain="E-commerce",
        audience="Business Analysts",
        db_type="sqlserver",
        language="persian"
    )
    assert "E-commerce" in usecase_context, "Should contain business domain"
    assert "SQL Server" in usecase_context, "Should contain database type"
    assert "Persian" in usecase_context, "Should contain language"
    print("[OK] Build use case context test passed")
    
    # Test relationship map
    rel_map = build_relationship_map(schema_info)
    assert "id" in rel_map, "Should contain relationship mappings"
    print("[OK] Build relationship map test passed")
    
    # Test complete prompt (mock objects)
    class MockJob:
        def __init__(self):
            self.scope = type('obj', (object,), {'value': 'table'})()
            self.business_domain = "E-commerce"
            self.audience = "Analysts"
            self.language = "persian"
    
    class MockTableTask:
        def __init__(self):
            self.schema_name = "dbo"
            self.table_name = "Users"
    
    prompt = build_dictionary_prompt(
        job=MockJob(),
        table_task=MockTableTask(),
        schema_info=schema_info,
        sample_data=[{"id": 1, "name": "Test"}],
        db_type="SQL Server"
    )
    assert "SQL PT Dictionary Engine" in prompt, "Should contain engine name"
    assert "dbo.Users" in prompt, "Should contain table name"
    assert "VALID JSON ONLY" in prompt, "Should contain JSON requirement"
    print("[OK] Build dictionary prompt test passed")


def test_db_utils():
    """Test database utilities"""
    print("\nTesting database utilities...")
    from core.db_utils import (
        extract_query_keywords,
        detect_query_intent
    )
    
    # Test keyword extraction
    query = "SELECT * FROM Users WHERE id = 1"
    keywords = extract_query_keywords(query)
    assert "SELECT" in keywords, "Should extract SELECT keyword"
    assert "FROM" in keywords, "Should extract FROM keyword"
    assert "WHERE" in keywords, "Should extract WHERE keyword"
    print("[OK] Extract query keywords test passed")
    
    # Test intent detection
    agg_query = "SELECT COUNT(*) FROM Users"
    intent = detect_query_intent(agg_query)
    assert intent == "aggregation", "Should detect aggregation intent"
    
    filter_query = "SELECT * FROM Users WHERE age > 18"
    intent = detect_query_intent(filter_query)
    assert intent == "filtering", "Should detect filtering intent"
    
    join_query = "SELECT * FROM Users JOIN Orders ON Users.id = Orders.user_id"
    intent = detect_query_intent(join_query)
    assert intent == "join", "Should detect join intent"
    print("[OK] Detect query intent test passed")


def test_integration():
    """Test integration of components"""
    print("\nTesting component integration...")
    from core.json_safety import parse_llm_json_response, validate_dictionary_result
    from core.prompts.dictionary_prompts import build_schema_context, build_usecase_context
    
    # Simulate complete flow
    schema_info = {
        "schema_name": "dbo",
        "table_name": "Users",
        "columns": [{"name": "id", "data_type": "int"}],
        "relationships": []
    }
    
    # Build contexts
    schema_context = build_schema_context(schema_info)
    usecase_context = build_usecase_context(
        "E-commerce", "Analysts", "sqlserver", "persian"
    )
    assert schema_context and usecase_context, "Should build contexts"
    
    # Parse and validate JSON
    sample_json = '{"tables": [{"table_name": "Users", "columns": []}]}'
    parsed = parse_llm_json_response(sample_json)
    assert parsed is not None, "Should parse JSON"
    assert validate_dictionary_result(parsed), "Should validate result"
    print("[OK] Integration test passed")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Refactored Dictionary Generation Flow")
    print("=" * 60)
    
    try:
        test_config()
        test_json_safety()
        test_prompt_builders()
        test_db_utils()
        test_integration()
        
        print("\n" + "=" * 60)
        print("[OK] ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\nX TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

