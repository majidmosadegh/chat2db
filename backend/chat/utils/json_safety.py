"""
Safe JSON Parsing Utilities
Handles malformed JSON from LLM with retry logic and safe truncation
"""
import json
import re
import logging
from typing import Any, Optional, Dict, List

logger = logging.getLogger(__name__)


class JSONParseError(Exception):
    """Exception raised when JSON parsing fails after all retries"""
    pass


def safe_json_parse(
    text: str,
    max_retries: int = 3,
    truncate_at_safe_boundary: bool = True
) -> Dict[str, Any]:
    """
    Safely parse JSON from LLM response with retry logic.
    
    Args:
        text: Raw text from LLM (may contain markdown, extra text, etc.)
        max_retries: Maximum number of parsing attempts
        truncate_at_safe_boundary: Whether to truncate at safe JSON boundaries
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        JSONParseError: If parsing fails after all retries
    """
    if not text or not text.strip():
        raise JSONParseError("Empty text provided")
    
    # Clean text: remove markdown code blocks
    cleaned = _remove_markdown(text)
    
    # Try parsing with different strategies
    for attempt in range(max_retries):
        try:
            # Strategy 1: Direct parse
            if attempt == 0:
                return json.loads(cleaned)
            
            # Strategy 2: Extract JSON object
            elif attempt == 1:
                json_text = _extract_json_object(cleaned)
                if json_text:
                    return json.loads(json_text)
            
            # Strategy 3: Extract JSON array
            elif attempt == 2:
                json_text = _extract_json_array(cleaned)
                if json_text:
                    return json.loads(json_text)
            
            # Strategy 4: Truncate at safe boundary
            elif attempt == 3 and truncate_at_safe_boundary:
                truncated = _truncate_at_safe_boundary(cleaned)
                if truncated:
                    return json.loads(truncated)
        
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Last attempt failed
                raise JSONParseError(f"Failed to parse JSON after {max_retries} attempts: {e}")
            continue
    
    raise JSONParseError(f"Failed to parse JSON after {max_retries} attempts")


def _remove_markdown(text: str) -> str:
    """Remove markdown code blocks from text"""
    # Remove ```json ... ```
    text = re.sub(r'```json\s*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*\n?', '', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def _extract_json_object(text: str) -> Optional[str]:
    """Extract JSON object from text"""
    # Find first { and last }
    start = text.find('{')
    if start == -1:
        return None
    
    # Find matching closing brace
    brace_count = 0
    end = start
    
    for i in range(start, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    
    if brace_count == 0:
        return text[start:end]
    
    return None


def _extract_json_array(text: str) -> Optional[str]:
    """Extract JSON array from text"""
    # Find first [ and last ]
    start = text.find('[')
    if start == -1:
        return None
    
    # Find matching closing bracket
    bracket_count = 0
    end = start
    
    for i in range(start, len(text)):
        if text[i] == '[':
            bracket_count += 1
        elif text[i] == ']':
            bracket_count -= 1
            if bracket_count == 0:
                end = i + 1
                break
    
    if bracket_count == 0:
        return text[start:end]
    
    return None


def _truncate_at_safe_boundary(text: str) -> Optional[str]:
    """
    Truncate text at a safe JSON boundary (complete object/array).
    Only truncates if we can find a complete JSON structure.
    """
    # Try to find complete JSON object
    json_obj = _extract_json_object(text)
    if json_obj:
        return json_obj
    
    # Try to find complete JSON array
    json_arr = _extract_json_array(text)
    if json_arr:
        return json_arr
    
    # Last resort: find last complete key-value pair or array element
    # This is more complex, so we'll just return None to avoid partial JSON
    return None


def validate_json_structure(
    data: Dict[str, Any],
    required_keys: Optional[List[str]] = None,
    required_types: Optional[Dict[str, type]] = None
) -> bool:
    """
    Validate JSON structure has required keys and types.
    
    Args:
        data: Parsed JSON data
        required_keys: List of required keys
        required_types: Dict of key -> expected type
        
    Returns:
        True if valid, False otherwise
    """
    if required_keys:
        for key in required_keys:
            if key not in data:
                logger.warning(f"Missing required key: {key}")
                return False
    
    if required_types:
        for key, expected_type in required_types.items():
            if key in data:
                if not isinstance(data[key], expected_type):
                    logger.warning(f"Key {key} has wrong type: expected {expected_type}, got {type(data[key])}")
                    return False
    
    return True


def safe_json_loads_with_fallback(
    text: str,
    fallback_value: Any = None,
    log_errors: bool = True
) -> Any:
    """
    Safely parse JSON with fallback value on error.
    Never raises exceptions, always returns a value.
    
    Args:
        text: Text to parse
        fallback_value: Value to return on error
        log_errors: Whether to log errors
        
    Returns:
        Parsed JSON or fallback value
    """
    try:
        return safe_json_parse(text)
    except (JSONParseError, json.JSONDecodeError) as e:
        if log_errors:
            logger.error(f"JSON parse failed, using fallback: {e}")
        return fallback_value
    except Exception as e:
        if log_errors:
            logger.error(f"Unexpected error parsing JSON, using fallback: {e}")
        return fallback_value

