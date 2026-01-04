#!/usr/bin/env python3
"""
Migration script to fix database schema issues:
- Add column_order to schema_metadata table
- Ensure relationships table has proper structure
"""

import asyncio
import aiosqlite
from pathlib import Path

async def migrate_database_schema():
    """Fix database schema issues"""

    # Database path
    db_path = Path(__file__).parent / "storage" / "metadata.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    async with aiosqlite.connect(str(db_path)) as conn:
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")

        # Check and fix schema_metadata table
        print("Checking schema_metadata table...")
        cursor = await conn.execute("PRAGMA table_info(schema_metadata)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Add column_order if missing
        if "column_order" not in column_names:
            print("Adding column_order to schema_metadata table")
            try:
                await conn.execute("ALTER TABLE schema_metadata ADD COLUMN column_order INTEGER DEFAULT NULL")
            except Exception as e:
                print(f"Error adding column_order: {e}")
        else:
            print("column_order already exists in schema_metadata")

        # Check and fix relationships table
        print("Checking relationships table...")
        cursor = await conn.execute("PRAGMA table_info(relationships)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Add missing columns to relationships table
        missing_columns = [
            ("strength_score", "REAL"),
            ("semantic_similarity", "REAL"),
            ("user_accepted", "INTEGER NOT NULL DEFAULT 0"),
            ("agent_approved", "INTEGER NOT NULL DEFAULT 0")
        ]

        for column_name, column_def in missing_columns:
            if column_name not in column_names:
                print(f"Adding column: {column_name} to relationships table")
                try:
                    await conn.execute(f"ALTER TABLE relationships ADD COLUMN {column_name} {column_def}")
                except Exception as e:
                    print(f"Error adding column {column_name}: {e}")
            else:
                print(f"Column {column_name} already exists in relationships")

        # Check and fix fine_tuning_sessions table
        print("Checking fine_tuning_sessions table...")
        cursor = await conn.execute("PRAGMA table_info(fine_tuning_sessions)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Add language column if missing
        if "language" not in column_names:
            print("Adding language column to fine_tuning_sessions table")
            try:
                await conn.execute("ALTER TABLE fine_tuning_sessions ADD COLUMN language TEXT NOT NULL DEFAULT 'english'")
            except Exception as e:
                print(f"Error adding language column: {e}")
        else:
            print("language column already exists in fine_tuning_sessions")

        await conn.commit()
        print("Migration completed successfully")

if __name__ == "__main__":
    asyncio.run(migrate_database_schema())






