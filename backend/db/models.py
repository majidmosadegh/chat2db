"""
Database models for the new DB module.
These are simplified versions of the main models for better decoupling.
"""

from pydantic import BaseModel
from typing import Optional


class DatabaseConnection(BaseModel):
    """Simplified database connection model"""
    id: int
    db_type: str  # postgresql, mysql, sqlserver
    host: str
    port: int
    username: str
    encrypted_password: str
    database_name: str
    is_active: bool = True


class Snapshot(BaseModel):
    """Simplified snapshot model"""
    id: int
    name: str
    database_connection_id: int
    is_active: bool = False
