#!/usr/bin/env python3
"""
Migration script to add session_metadata column to maturation_sessions table
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from api.db_models import engine


async def migrate_maturation_sessions():
    """Add session_metadata column to maturation_sessions table"""
    
    async with engine.begin() as conn:
        # Check if column exists
        drivername = engine.url.drivername
        is_sqlite = 'sqlite' in drivername.lower()
        is_postgres = 'postgresql' in drivername.lower()
        
        if is_sqlite:
            # SQLite
            result = await conn.execute(text("PRAGMA table_info(maturation_sessions)"))
            columns = result.fetchall()
            column_names = [col[1] for col in columns]
            
            # Add session_metadata column if missing
            if "session_metadata" not in column_names:
                print("Adding session_metadata column to maturation_sessions...")
                await conn.execute(text("ALTER TABLE maturation_sessions ADD COLUMN session_metadata TEXT"))
                print("[OK] Added session_metadata column")
            else:
                print("[OK] session_metadata column already exists")
        
        elif is_postgres:
            # PostgreSQL
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'maturation_sessions' 
                AND column_name = 'session_metadata'
            """))
            exists = result.fetchone() is not None
            
            if not exists:
                print("Adding session_metadata column to maturation_sessions...")
                await conn.execute(text("ALTER TABLE maturation_sessions ADD COLUMN session_metadata TEXT"))
                print("[OK] Added session_metadata column")
            else:
                print("[OK] session_metadata column already exists")
        else:
            print(f"Unsupported database type: {drivername}")
            return


if __name__ == "__main__":
    asyncio.run(migrate_maturation_sessions())



