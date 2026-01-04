# Prompt Enhancement Summary

## Overview
Enhanced the LLM prompt to enforce strict JSON output rules and prevent parsing errors. The prompt now includes explicit validation instructions and character/array limits.

## Key Changes

### 1. **Strict JSON Output Rules** (`backend/core/prompts/dictionary_prompts.py`)
- Added **CRITICAL OUTPUT RULES** section at the top of prompt
- Enforces single valid JSON object only (no markdown, no comments)
- Limits: 5 tables per response, 3500 characters max, 120 columns max
- Explicit instructions to close all brackets and avoid trailing commas
- Internal validation check requirement: `json.loads(output)` must succeed

### 2. **Character Limits Enforced**
- `business_description`: max 120 chars
- `usage_notes`: max 100 chars
- `description`: max 80 chars
- `real_example`: max 50 chars
- `sample_insights`: max 5 items, each max 60 chars
- `constraints`: max 5 items, each max 40 chars
- `use_case_examples`: max 5 items, each max 60 chars

### 3. **Updated JSON Schema**
- Simplified to match exact required format
- Removed optional fields that aren't in the required schema
- Clear instructions for SINGLE_TABLE scope (single object, not wrapped in array)

### 4. **Configuration Updates** (`backend/core/config.py`)
- `MAX_COLUMNS_PER_TABLE`: 100 → 120
- Added `MAX_TABLES_PER_RESPONSE = 5`
- Added `MAX_JSON_OUTPUT_CHARS = 3500`

### 5. **Validation Function Update** (`backend/core/json_safety.py`)
- Updated `validate_dictionary_result()` to handle both formats:
  - SINGLE_TABLE: single object with `table_name` and `columns` at top level
  - FULL_SNAPSHOT: `tables` array format
- More robust validation logic

### 6. **Final Validation Checklist**
Added explicit checklist in prompt:
- Count and match all brackets
- Check for trailing commas
- Ensure all strings are closed
- Verify character and column limits
- Test: `json.loads(output)` must succeed

## Expected Impact

1. **Reduced JSON Parsing Errors**: Strict rules and validation instructions should reduce malformed JSON
2. **Prevented Token Cut-offs**: Character limits (3500) help prevent responses that exceed token limits
3. **Better Structure**: Clear schema and limits ensure consistent output format
4. **Improved Reliability**: Internal validation requirement forces LLM to check its own output

## Testing

The enhanced prompt will be used in the next dictionary generation job. Monitor logs for:
- Reduced "Failed to parse JSON" errors
- Responses staying under 3500 characters
- Valid JSON structure in all responses
- Proper bracket closing





