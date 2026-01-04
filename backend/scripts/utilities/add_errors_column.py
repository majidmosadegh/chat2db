#!/usr/bin/env python3
"""
Add errors column to ai_generation_jobs table
"""
import asyncio
import aiosqlite
from pathlib import Path

async def add_errors_column():
    """Add errors column to ai_generation_jobs table"""

    # Database path
    db_path = Path("storage/metadata.db")

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    async with aiosqlite.connect(str(db_path)) as conn:
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")

        # Check ai_generation_jobs table
        print("Checking ai_generation_jobs table...")
        cursor = await conn.execute("PRAGMA table_info(ai_generation_jobs)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Add errors column if missing
        if "errors" not in column_names:
            print("Adding errors column to ai_generation_jobs table")
            try:
                await conn.execute("ALTER TABLE ai_generation_jobs ADD COLUMN errors TEXT")
                await conn.commit()
                print("Successfully added errors column")
            except Exception as e:
                print(f"Error adding errors column: {e}")
        else:
            print("errors column already exists")

if __name__ == "__main__":
    asyncio.run(add_errors_column())
