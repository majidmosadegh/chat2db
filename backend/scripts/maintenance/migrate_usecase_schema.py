#!/usr/bin/env python3
"""
Migration script to add new fields to the use_cases table for Smart Use Case Builder support.
"""

import asyncio
import aiosqlite
from pathlib import Path

async def migrate_use_cases_table():
    """Add new columns to the use_cases table"""

    # Database path - adjust if needed
    db_path = Path(__file__).parent / "storage" / "metadata.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    async with aiosqlite.connect(str(db_path)) as conn:
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")

        # Check if columns already exist
        cursor = await conn.execute("PRAGMA table_info(use_cases)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        new_columns = [
            ("is_ai_generated", "BOOLEAN NOT NULL DEFAULT 0"),
            ("generation_log_id", "INTEGER REFERENCES ai_generation_logs(id)"),
            ("generation_version", "INTEGER"),
            ("business_context", "TEXT"),
            ("primary_audience", "TEXT"),
            ("typical_questions", "TEXT"),
            ("output_preference", "TEXT"),
            ("dictionary_version", "INTEGER"),
            ("relationships_version", "INTEGER")
        ]

        for column_name, column_def in new_columns:
            if column_name not in column_names:
                print(f"Adding column: {column_name}")
                try:
                    await conn.execute(f"ALTER TABLE use_cases ADD COLUMN {column_name} {column_def}")
                except Exception as e:
                    print(f"Error adding column {column_name}: {e}")
            else:
                print(f"Column {column_name} already exists")

        await conn.commit()
        print("Migration completed successfully")

if __name__ == "__main__":
    asyncio.run(migrate_use_cases_table())