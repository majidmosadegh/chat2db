from typing import Dict, Optional, Literal
from pydantic import BaseModel

class TableGenerationResult(BaseModel):
    """Strict result contract for table generation"""
    status: Literal["SUCCESS", "FAILED"]
    table_description: Optional[str] = None
    column_descriptions: Dict[str, str] = {}
    error_reason: Optional[str] = None
    attempts_used: int = 0

print("Simple class created successfully")
result = TableGenerationResult(status="SUCCESS", attempts_used=1)
print(f"Instance created: {result}")
