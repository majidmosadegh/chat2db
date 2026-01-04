import asyncio
import sys
import os
import json
import io
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Fix encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary
from config.config import DATABASE_URL

async def test_update():
    """Test if update logic works"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Get an old entry (EnergyExchange.Id)
        result = await session.execute(
            select(DataDictionary).where(
                DataDictionary.table_name == "EnergyExchange",
                DataDictionary.column_name == "Id"
            ).limit(1)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            print(f"Found entry ID: {entry.id}")
            print(f"Table: {entry.table_name}, Column: {entry.column_name}")
            print(f"Current synonyms: {entry.synonyms[:100] if entry.synonyms else 'None'}...")
            print(f"Is AI Generated: {entry.is_ai_generated}")
            print(f"Created: {entry.created_at}")
            print(f"Updated: {entry.updated_at}")
            print("=" * 80)
            
            # Simulate update logic
            print("\nSimulating update with new synonyms...")
            entry.description = "Updated description"
            entry.synonyms = "test_synonym1, test_synonym2, test_synonym3"
            entry.is_ai_generated = True
            from datetime import datetime, timezone
            entry.updated_at = datetime.now(timezone.utc)
            
            await session.commit()
            await session.refresh(entry)
            
            print(f"After update:")
            print(f"  Description: {entry.description}")
            print(f"  Synonyms: {entry.synonyms}")
            print(f"  Updated: {entry.updated_at}")
            
            # Rollback for testing
            await session.rollback()
            print("\n(Rolled back - no actual changes made)")
        else:
            print("Entry not found")

if __name__ == "__main__":
    asyncio.run(test_update())



