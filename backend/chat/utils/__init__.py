"""
Chat utilities module
"""
from .json_safety import (
    safe_json_parse,
    safe_json_loads_with_fallback,
    validate_json_structure,
    JSONParseError
)

__all__ = [
    "safe_json_parse",
    "safe_json_loads_with_fallback",
    "validate_json_structure",
    "JSONParseError"
]

