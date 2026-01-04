"""
JSON Safety Utilities
Strict JSON safety guards for LLM output
"""

import json
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def fix_unterminated_strings(json_text: str) -> str:
    """
    Fix unterminated strings that occur when JSON is cut off mid-token.
    This handles cases where the LLM response hits max_tokens limit.
    
    Args:
        json_text: JSON string that may have unterminated strings
        
    Returns:
        JSON string with unterminated strings fixed
    """
    if not json_text:
        return json_text
    
    # Use a state machine to track string boundaries
    result = []
    in_string = False
    escape_next = False
    i = 0
    
    while i < len(json_text):
        char = json_text[i]
        
        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue
        
        if char == '\\':
            escape_next = True
            result.append(char)
            i += 1
            continue
        
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue
        
        result.append(char)
        i += 1
    
    # If we end in the middle of a string, close it
    # This typically happens when JSON is cut off at max_tokens
    if in_string:
        result.append('"')
        logger.debug("Fixed unterminated string at end of JSON (likely token cut-off)")
    
    return ''.join(result)


def repair_json_text(json_text: str) -> str:
    """
    Repair common JSON issues from LLM responses.
    Enhanced version with better bracket matching and safety.
    Now handles unterminated strings from token cut-offs.
    
    Args:
        json_text: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string
    """
    if not json_text:
        return json_text
    
    # Remove markdown code blocks
    if json_text.startswith('```json'):
        json_text = json_text.replace('```json', '').replace('```', '').strip()
    elif json_text.startswith('```'):
        json_text = json_text.replace('```', '').strip()
    
    # Remove BOM and other invisible characters
    json_text = json_text.lstrip('\ufeff')
    
    # FIRST: Fix unterminated strings (critical for token cut-offs)
    json_text = fix_unterminated_strings(json_text)
    
    # SECOND: Remove all trailing commas before closing brackets/braces
    json_text = re.sub(r',(\s*)(\}|\])', r'\1\2', json_text)
    
    # Remove duplicate commas
    json_text = re.sub(r',{2,}', ',', json_text)
    
    # Fix missing commas between objects
    json_text = re.sub(r'\}\s*(\n\s*)\{', r'},\1{', json_text)
    json_text = re.sub(r'\}\s*"name"', r'}, {"name"', json_text)
    json_text = re.sub(r'\}\s*\{', r'},{', json_text)
    json_text = re.sub(r']\s*\{', '],{', json_text)
    json_text = re.sub(r'\}\s*\[', '},[', json_text)
    
    # Fix missing commas after closing braces in columns array
    json_text = re.sub(r'\}\s+("name"|\{)', r'}, \1', json_text)
    
    # Fix missing commas after values before closing brace
    json_text = re.sub(r'"([^"]+)"\s+(\})', r'"\1",\2', json_text)
    
    # Fix missing commas after numbers before closing brace
    json_text = re.sub(r'(\d+)\s+(\})', r'\1,\2', json_text)
    
    # Fix unclosed column objects
    lines = json_text.split('\n')
    fixed_lines = []
    for i, line in enumerate(lines):
        fixed_lines.append(line)
        if i < len(lines) - 1:
            next_line = lines[i + 1].strip()
            if line.rstrip().endswith('}') and (next_line.startswith('{') or next_line.startswith('"name"')):
                if not line.rstrip().endswith(',}') and not line.rstrip().endswith(', }'):
                    fixed_lines[-1] = line.rstrip()[:-1] + ',' + line.rstrip()[-1]
    
    json_text = '\n'.join(fixed_lines)
    
    # FINAL: Remove any trailing commas that might have been created
    json_text = re.sub(r',(\s*)(\}|\])', r'\1\2', json_text)
    
    return json_text


def ensure_valid_json_structure(json_text: str) -> str:
    """
    Ensure JSON structure is valid by auto-closing brackets and braces.
    
    Args:
        json_text: JSON string that may be cut off
        
    Returns:
        JSON string with auto-closed brackets
    """
    if not json_text:
        return "{}"
    
    # Count unclosed brackets and braces
    open_braces = json_text.count('{')
    close_braces = json_text.count('}')
    open_brackets = json_text.count('[')
    close_brackets = json_text.count(']')
    
    # Auto-close if needed
    missing_braces = open_braces - close_braces
    missing_brackets = open_brackets - close_brackets
    
    # Close brackets first (inner structures)
    if missing_brackets > 0:
        json_text += ']' * missing_brackets
    
    # Then close braces (outer structures)
    if missing_braces > 0:
        json_text += '}' * missing_braces
    
    return json_text


def parse_llm_json_response(
    response_text: str,
    max_repair_attempts: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Parse LLM JSON response with strict safety guards.
    Handles token cut-offs, invalid delimiters, and bracket mismatches.
    Now specifically handles unterminated strings from token cut-offs.
    
    Args:
        response_text: Raw LLM response text
        max_repair_attempts: Maximum number of repair attempts
        
    Returns:
        Parsed JSON dictionary or None if parsing fails
    """
    if not response_text:
        return None
    
    # Step 1: Extract JSON from response
    json_text = _extract_json_from_response(response_text)
    if not json_text:
        return None
    
    # Step 2: Try direct parsing first
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        # Check if it's an unterminated string error
        error_msg = str(e)
        if "Unterminated string" in error_msg or "Expecting property name" in error_msg:
            logger.debug(f"Detected unterminated string or property name error, will attempt repair: {e}")
        else:
            logger.debug(f"JSON parse error (will attempt repair): {e}")
    
    # Step 3: Repair and retry with multiple strategies
    for attempt in range(max_repair_attempts):
        try:
            # Strategy 1: Basic repair (fixes commas, brackets, etc.)
            repaired = repair_json_text(json_text)
            
            # Strategy 2: Ensure valid structure (auto-close brackets)
            repaired = ensure_valid_json_structure(repaired)
            
            # Strategy 3: If still failing, try truncating at the error position
            try:
                result = json.loads(repaired)
                logger.info(f"Successfully parsed JSON after {attempt + 1} repair attempt(s)")
                return result
            except json.JSONDecodeError as parse_error:
                error_msg = str(parse_error)
                error_pos = getattr(parse_error, 'pos', None)
                
                # Handle specific error types with targeted fixes
                delimiter_errors = [
                    "Expecting ',' delimiter",
                    "Expecting ':' delimiter", 
                    "Expecting value",
                    "Unterminated string"
                ]
                is_delimiter_error = any(err in error_msg for err in delimiter_errors)
                
                if is_delimiter_error:
                    # JSON was cut off mid-property, mid-value, mid-key, or mid-string
                    # Try to find a safe truncation point before the error
                    if error_pos and error_pos < len(repaired):
                        # Strategy: Find the last complete property/object before the error
                        truncated = _truncate_at_safe_position(repaired, error_pos)
                        if truncated:
                            try:
                                result = json.loads(truncated)
                                logger.debug(f"Parsed JSON after truncation (JSON was cut off mid-generation, recovered successfully)")
                                return result
                            except json.JSONDecodeError as truncate_error:
                                logger.debug(f"Truncated JSON still failed to parse: {truncate_error}")
                                # Try even more aggressive truncation - remove incomplete last property
                                if is_delimiter_error:
                                    # Try removing the last incomplete property/column
                                    more_aggressive = _remove_incomplete_last_property(truncated)
                                    if more_aggressive:
                                        try:
                                            result = json.loads(more_aggressive)
                                            logger.debug(f"Parsed JSON after removing incomplete last property (recovered successfully)")
                                            return result
                                        except:
                                            pass
                                    
                                    # Try one more time with even more aggressive truncation
                                    # Find the last complete column object and remove everything after
                                    even_more_aggressive = _truncate_at_last_complete_column(repaired, error_pos)
                                    if even_more_aggressive:
                                        try:
                                            result = json.loads(even_more_aggressive)
                                            logger.debug(f"Parsed JSON after aggressive column truncation (recovered successfully)")
                                            return result
                                        except:
                                            pass
                                pass  # Try next strategy
                
                # If we're on the last attempt, try aggressive truncation
                if attempt == max_repair_attempts - 1:
                    # Try to find a safe truncation point
                    if error_pos and error_pos < len(repaired):
                        # Try truncating at the error position and closing properly
                        truncated = repaired[:error_pos]
                        # Find the last complete object/array before the error
                        # Look backwards for a closing brace or bracket
                        last_brace = truncated.rfind('}')
                        last_bracket = truncated.rfind(']')
                        truncate_at = max(last_brace, last_bracket)
                        if truncate_at > 0:
                            truncated = truncated[:truncate_at + 1]
                            # Ensure proper closing
                            truncated = ensure_valid_json_structure(truncated)
                            try:
                                result = json.loads(truncated)
                                logger.debug(f"Parsed JSON after aggressive truncation at position {truncate_at} (recovered successfully)")
                                return result
                            except:
                                pass
                
                # Continue to next attempt
                if attempt < max_repair_attempts - 1:
                    continue
                else:
                    logger.error(f"Failed to parse JSON after {max_repair_attempts} attempts: {parse_error}")
                    return None
            
        except Exception as e:
            logger.error(f"Unexpected error during JSON repair (attempt {attempt + 1}): {e}")
            if attempt == max_repair_attempts - 1:
                return None
            continue
    
    return None


def _extract_json_from_response(response_text: str) -> str:
    """
    Extract JSON from LLM response, handling markdown and extra text.
    
    Args:
        response_text: Raw response text
        
    Returns:
        Extracted JSON string
    """
    # Remove markdown code blocks
    if response_text.startswith('```json'):
        response_text = response_text.replace('```json', '').replace('```', '').strip()
    elif response_text.startswith('```'):
        response_text = response_text.replace('```', '').strip()
    
    # Try to find JSON object in response
    # Look for first { and last }
    first_brace = response_text.find('{')
    if first_brace == -1:
        return ""
    
    # Find matching closing brace (simple approach)
    brace_count = 0
    last_brace = -1
    for i in range(first_brace, len(response_text)):
        if response_text[i] == '{':
            brace_count += 1
        elif response_text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                last_brace = i + 1
                break
    
    if last_brace > first_brace:
        return response_text[first_brace:last_brace]
    
    # Fallback: return from first brace to end (will be repaired)
    return response_text[first_brace:]


def _truncate_at_safe_position(json_text: str, error_pos: int) -> Optional[str]:
    """
    Find a safe truncation point before an error position.
    Looks for complete objects, arrays, or properties.
    Handles "Expecting ',' delimiter", "Expecting ':' delimiter", and "Expecting value" errors.
    
    Args:
        json_text: JSON text to truncate
        error_pos: Position where error occurred
        
    Returns:
        Truncated JSON string or None if no safe position found
    """
    if error_pos >= len(json_text):
        error_pos = len(json_text) - 1
    
    if error_pos <= 0:
        return None
    
    # Start from error position and work backwards
    truncated = json_text[:error_pos]
    
    # Strategy 1: Find last complete property (ends with , or })
    # Look backwards from error position for a safe cut point
    # We want to find: "key": value, or "key": value} or ]
    search_start = min(len(truncated), error_pos)
    search_end = max(0, search_start - 2000)  # Search up to 2000 chars back (increased from 1000)
    
    # First, try to find complete column objects in columns array
    columns_start = truncated.find('"columns"')
    if columns_start != -1:
        bracket_start = truncated.find('[', columns_start)
        if bracket_start != -1 and error_pos > bracket_start:
            # We're in the columns array - look for complete column objects
            # Look for pattern: }, or }, " or }, \n
            for i in range(min(search_start - 1, error_pos - 1), max(search_end, bracket_start), -1):
                if i < len(truncated):
                    char = truncated[i]
                    # If we find a closing brace, check if it's a complete column object
                    if char == '}':
                        # Check what comes after
                        if i + 1 < len(truncated):
                            next_chars = truncated[i+1:min(i+20, len(truncated))].strip()
                            # If next is comma, closing bracket, newline, or whitespace, might be complete
                            if (next_chars.startswith(',') or next_chars.startswith(']') or 
                                next_chars.startswith('\n') or next_chars == '' or
                                next_chars.startswith('"name"') or next_chars.startswith('{')):
                                test_truncated = truncated[:i + 1]
                                
                                # Fix any unterminated strings first
                                test_truncated = fix_unterminated_strings(test_truncated)
                                
                                # Close columns array if needed
                                if ']' not in test_truncated[test_truncated.find('"columns"'):]:
                                    test_truncated += ']'
                                
                                # Try to close it properly
                                test_truncated = ensure_valid_json_structure(test_truncated)
                                
                                try:
                                    # Test if it parses
                                    result = json.loads(test_truncated)
                                    # If it parses, this is a safe truncation point
                                    logger.debug(f"Found safe truncation point at column object position {i} (error was at {error_pos})")
                                    return test_truncated
                                except json.JSONDecodeError:
                                    continue
    
    # Strategy 2: General search for complete properties/values
    for i in range(search_start - 1, search_end, -1):
        if i < len(truncated):
            char = truncated[i]
            # If we find a comma, closing brace, or closing bracket, try truncating there
            if char in [',', '}', ']']:
                # Check if this looks like the end of a complete property/value
                test_truncated = truncated[:i + 1]
                
                # Fix any unterminated strings first
                test_truncated = fix_unterminated_strings(test_truncated)
                
                # Try to close it properly
                test_truncated = ensure_valid_json_structure(test_truncated)
                
                try:
                    # Test if it parses
                    result = json.loads(test_truncated)
                    # If it parses, this is a safe truncation point
                    logger.debug(f"Found safe truncation point at position {i} (error was at {error_pos})")
                    return test_truncated
                except json.JSONDecodeError:
                    continue
    
    # Strategy 3: Find last complete object/array
    last_brace = truncated.rfind('}')
    last_bracket = truncated.rfind(']')
    truncate_at = max(last_brace, last_bracket)
    
    if truncate_at > 0:
        truncated = truncated[:truncate_at + 1]
        # Fix unterminated strings
        truncated = fix_unterminated_strings(truncated)
        truncated = ensure_valid_json_structure(truncated)
        try:
            json.loads(truncated)  # Test if valid
            logger.debug(f"Found safe truncation point at last brace/bracket {truncate_at}")
            return truncated
        except:
            pass
    
    return None


def _truncate_at_last_complete_column(json_text: str, error_pos: int) -> Optional[str]:
    """
    Aggressively truncate at the last complete column object.
    Used as a last resort when other truncation strategies fail.
    
    Args:
        json_text: JSON text to truncate
        error_pos: Position where error occurred
        
    Returns:
        Truncated JSON string or None if not applicable
    """
    if not json_text or error_pos <= 0:
        return None
    
    # Find the columns array
    columns_start = json_text.find('"columns"')
    if columns_start == -1:
        return None
    
    # Find the opening bracket
    bracket_start = json_text.find('[', columns_start)
    if bracket_start == -1:
        return None
    
    # Work backwards from error_pos to find complete column objects
    # Look for pattern: }, "column_name": ... or }, { "column_name"
    # We want to find the last complete } that represents a full column object
    
    truncated = json_text[:error_pos]
    
    # Find all closing braces in the columns array region
    # Look for }, patterns that indicate complete column objects
    search_start = min(len(truncated), error_pos)
    search_end = max(bracket_start, search_start - 2000)  # Search up to 2000 chars back
    
    # Try to find the last complete column object
    # Pattern: }, followed by either end of array or start of next column
    best_position = -1
    
    for i in range(search_start - 1, search_end, -1):
        if i < len(truncated) - 1:
            # Check if we have a complete column object ending
            # Look for }, or }, " or }, \n
            if truncated[i] == '}' and i + 1 < len(truncated):
                next_chars = truncated[i+1:min(i+10, len(truncated))].strip()
                # If next is comma, newline, or closing bracket, this might be a complete object
                if next_chars.startswith(',') or next_chars.startswith(']') or next_chars.startswith('\n') or next_chars == '':
                    # Check if this is inside the columns array
                    if i > bracket_start:
                        # Try truncating here
                        test_truncated = truncated[:i + 1]
                        # Close the array and object properly
                        if '"columns"' in test_truncated and '[' in test_truncated[test_truncated.find('"columns"'):]:
                            # Check if columns array is closed
                            if ']' not in test_truncated[test_truncated.find('"columns"'):]:
                                test_truncated += ']'
                        test_truncated = ensure_valid_json_structure(test_truncated)
                        test_truncated = fix_unterminated_strings(test_truncated)
                        try:
                            json.loads(test_truncated)
                            best_position = i + 1
                            break
                        except:
                            continue
    
    if best_position > 0:
        result = truncated[:best_position]
        # Ensure proper closing
        if '"columns"' in result and '[' in result[result.find('"columns"'):]:
            if ']' not in result[result.find('"columns"'):]:
                result += ']'
        result = ensure_valid_json_structure(result)
        result = fix_unterminated_strings(result)
        try:
            json.loads(result)  # Verify
            return result
        except:
            pass
    
    return None


def _remove_incomplete_last_property(json_text: str) -> Optional[str]:
    """
    Remove the last incomplete property from JSON.
    Used when JSON is cut off in the middle of a property (common with token limits).
    
    Args:
        json_text: JSON text that may have incomplete last property
        
    Returns:
        JSON with incomplete property removed, or None if not applicable
    """
    if not json_text:
        return None
    
    # Strategy: Find the last complete column object in the columns array
    # Look for pattern: }, "column_name": ... or }, { "column_name"
    
    # Find columns array
    columns_start = json_text.rfind('"columns"')
    if columns_start == -1:
        # Try to find last complete object/array anyway
        last_brace = json_text.rfind('}')
        if last_brace > 0:
            test_truncated = json_text[:last_brace + 1]
            test_truncated = ensure_valid_json_structure(test_truncated)
            test_truncated = fix_unterminated_strings(test_truncated)
            try:
                json.loads(test_truncated)
                return test_truncated
            except:
                pass
        return None
    
    # Find the opening bracket of columns array
    bracket_start = json_text.find('[', columns_start)
    if bracket_start == -1:
        return None
    
    # Find the last complete column object (ends with })
    # Work backwards from the end to find complete objects
    last_complete_brace = json_text.rfind('}')
    if last_complete_brace <= bracket_start:
        return None
    
    # Check what comes before the last brace - if it's a comma, we might have incomplete next item
    # If it's }, we have a complete object
    # Look backwards to find the start of the last complete column
    test_truncated = json_text[:last_complete_brace + 1]
    
    # Check if there's a closing bracket after this brace
    bracket_end = json_text.find(']', last_complete_brace)
    if bracket_end == -1:
        # No closing bracket - JSON was cut off in columns array
        # Close the array and parent object properly
        test_truncated = test_truncated.rstrip()
        if not test_truncated.endswith('}'):
            return None
        
        # Ensure we have proper closing: add ] for columns array, then } for table object
        # But first check if we're inside the columns array
        if '"columns"' in test_truncated and '[' in test_truncated[test_truncated.find('"columns"'):]:
            # We're in columns array - close it
            test_truncated += ']'
        
        # Fix any structure issues
        test_truncated = ensure_valid_json_structure(test_truncated)
        test_truncated = fix_unterminated_strings(test_truncated)
        
        try:
            result = json.loads(test_truncated)
            logger.debug("Successfully parsed JSON after removing incomplete last property")
            return test_truncated
        except json.JSONDecodeError:
            pass
    
    # If bracket exists, try truncating just before it if the last item looks incomplete
    # Check if the last item before ] is complete
    if bracket_end > last_complete_brace:
        # There's content between last brace and bracket - might be incomplete
        between = json_text[last_complete_brace + 1:bracket_end].strip()
        if between and not between.startswith(','):
            # Incomplete item - remove it
            test_truncated = json_text[:last_complete_brace + 1] + ']'
            # Find the closing brace for the table object
            test_truncated = ensure_valid_json_structure(test_truncated)
            test_truncated = fix_unterminated_strings(test_truncated)
            try:
                result = json.loads(test_truncated)
                return test_truncated
            except:
                pass
    
    return None


def validate_dictionary_result(result: Dict[str, Any]) -> bool:
    """
    Validate dictionary result structure.
    Supports both SINGLE_TABLE format (single object) and FULL_SNAPSHOT format (tables array).
    
    Args:
        result: Dictionary result to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Check for required top-level keys
    # SINGLE_TABLE format: has "table_name" and "columns" at top level
    # FULL_SNAPSHOT format: has "tables" array
    if "tables" in result:
        # FULL_SNAPSHOT format
        if not isinstance(result["tables"], list):
            return False
        for table in result["tables"]:
            if not isinstance(table, dict):
                return False
            if "table_name" not in table:
                return False
            if "columns" in table:
                if not isinstance(table["columns"], list):
                    return False
        return True
    elif "table_name" in result and "columns" in result:
        # SINGLE_TABLE format (single table object, not wrapped in array)
        if not isinstance(result["columns"], list):
            return False
        return True
    
    return False

