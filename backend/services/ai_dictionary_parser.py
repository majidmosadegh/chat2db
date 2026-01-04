"""
AI Dictionary Response Parser
Two-phase parsing strategy: strict JSON → best-effort plain text
"""
import json
import re
from typing import Dict, Optional, Tuple
from .ai_dictionary_types import TableGenerationResult


class DictionaryResponseParser:
    """Parser for AI dictionary generation responses"""

    @staticmethod
    def parse_response(response_text: str) -> TableGenerationResult:
        """Parse LLM response using two-phase strategy

        Phase 1: Strict JSON parsing
        Phase 2: Best-effort plain text parsing (if JSON fails)

        Args:
            response_text: Raw LLM response text

        Returns:
            TableGenerationResult with parsed data or failure status
        """
        if not response_text or not response_text.strip():
            return TableGenerationResult(
                status="FAILED",
                error_reason="Empty response from LLM"
            )

        # Phase 1: Strict JSON parsing
        json_result = DictionaryResponseParser._parse_strict_json(response_text)
        if json_result:
            return json_result

        # Phase 2: Best-effort plain text parsing
        text_result = DictionaryResponseParser._parse_best_effort_text(response_text)
        if text_result:
            return text_result

        # Both phases failed
        return TableGenerationResult(
            status="FAILED",
            error_reason="Could not parse response as JSON or extract meaningful text"
        )

    @staticmethod
    def _parse_strict_json(response_text: str) -> Optional[TableGenerationResult]:
        """Phase 1: Strict JSON parsing"""
        try:
            # Clean the response text
            cleaned_text = response_text.strip()

            # Try to parse as JSON
            data = json.loads(cleaned_text)

            # Validate required structure
            if not isinstance(data, dict):
                return None

            table_description = data.get('table_description', '').strip()
            column_descriptions = data.get('column_descriptions', {})

            # Validate types and content
            if not isinstance(column_descriptions, dict):
                return None

            # Ensure table description is present and non-empty
            if not table_description:
                return None

            # Ensure all column descriptions are non-empty strings
            valid_columns = {}
            for col_name, col_desc in column_descriptions.items():
                if isinstance(col_desc, str) and col_desc.strip():
                    valid_columns[col_name] = col_desc.strip()

            return TableGenerationResult(
                status="SUCCESS",
                table_description=table_description,
                column_descriptions=valid_columns
            )

        except (json.JSONDecodeError, TypeError, AttributeError):
            return None

    @staticmethod
    def _parse_best_effort_text(response_text: str) -> Optional[TableGenerationResult]:
        """Phase 2: Best-effort plain text parsing"""
        try:
            text = response_text.strip()
            table_description = None
            column_descriptions = {}

            # Look for table description patterns
            table_patterns = [
                r'table[_-]description["\s:]+([^"\n]+)',
                r'Table Description["\s:]+([^"\n]+)',
                r'جدول["\s:]+([^"\n]+)',
                r'شرح جدول["\s:]+([^"\n]+)'
            ]

            for pattern in table_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
                if match:
                    table_description = match.group(1).strip()
                    break

            # Look for column descriptions
            # Try different formats: key: value, key - value, etc.
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Skip lines that look like section headers
                if re.match(r'^(column[_-]descriptions?|شرح ستون|ستون)', line, re.IGNORECASE | re.UNICODE):
                    continue

                # Try to extract key-value pairs
                col_match = re.match(r'^["\s]*([^:]+)[:\s]+(.+?)["\s]*$', line)
                if col_match:
                    col_name = col_match.group(1).strip()
                    col_desc = col_match.group(2).strip()

                    # Clean up common artifacts
                    col_name = re.sub(r'^["\s]*-|["\s]*$', '', col_name)
                    col_desc = re.sub(r'["\s]*$', '', col_desc)

                    if col_name and col_desc and len(col_desc) > 3:  # Minimum meaningful length
                        column_descriptions[col_name] = col_desc

            # Require at least a table description or some column descriptions
            if table_description or column_descriptions:
                return TableGenerationResult(
                    status="SUCCESS",
                    table_description=table_description,
                    column_descriptions=column_descriptions
                )

            return None

        except Exception:
            return None








