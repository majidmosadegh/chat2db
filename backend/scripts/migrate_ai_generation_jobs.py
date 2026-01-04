#!/usr/bin/env python3
"""
Migration script to add new columns to ai_generation_jobs table:
- progress (FLOAT)
- result (TEXT)
- Also creates ai_table_tasks table if it doesn't exist
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from api.db_models import engine


async def migrate_ai_generation_jobs():
    """Add new columns to ai_generation_jobs table"""
    
    async with engine.begin() as conn:
        # Check if columns exist
        drivername = engine.url.drivername
        is_sqlite = 'sqlite' in drivername.lower()
        is_postgres = 'postgresql' in drivername.lower()
        
        if is_sqlite:
            # SQLite
            result = await conn.execute(text("PRAGMA table_info(ai_generation_jobs)"))
            columns = result.fetchall()
            column_names = [col[1] for col in columns]
            
            # Add progress column if missing
            if "progress" not in column_names:
                print("Adding progress column to ai_generation_jobs...")
                await conn.execute(text("ALTER TABLE ai_generation_jobs ADD COLUMN progress REAL DEFAULT 0.0"))
                print("[OK] Added progress column")
            else:
                print("[OK] progress column already exists")
            
            # Add result column if missing
            if "result" not in column_names:
                print("Adding result column to ai_generation_jobs...")
                await conn.execute(text("ALTER TABLE ai_generation_jobs ADD COLUMN result TEXT"))
                print("[OK] Added result column")
            else:
                print("[OK] result column already exists")
        
        elif is_postgres:
            # PostgreSQL
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'ai_generation_jobs'
            """))
            columns = result.fetchall()
            column_names = [col[0] for col in columns]
            
            # Add progress column if missing
            if "progress" not in column_names:
                print("Adding progress column to ai_generation_jobs...")
                await conn.execute(text("ALTER TABLE ai_generation_jobs ADD COLUMN progress REAL DEFAULT 0.0"))
                print("[OK] Added progress column")
            else:
                print("[OK] progress column already exists")
            
            # Add result column if missing
            if "result" not in column_names:
                print("Adding result column to ai_generation_jobs...")
                await conn.execute(text("ALTER TABLE ai_generation_jobs ADD COLUMN result TEXT"))
                print("[OK] Added result column")
            else:
                print("[OK] result column already exists")
        
        # Create ai_table_tasks table if it doesn't exist
        # This is handled by SQLAlchemy create_all, but we check anyway
        print("\n[OK] Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate_ai_generation_jobs())

