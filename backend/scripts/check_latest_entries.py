import asyncio
import sys
import os
import json
import io
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary, AIGenerationJob
from config.config import DATABASE_URL

async def check_latest():
    """Check the very latest entries"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Get the 5 most recent entries
        result = await session.execute(
            select(DataDictionary).where(
                DataDictionary.column_name.isnot(None),
                DataDictionary.is_ai_generated == True
            ).order_by(desc(DataDictionary.created_at)).limit(5)
        )
        entries = result.scalars().all()
        
        print("=" * 80)
        print("5 MOST RECENT AI-GENERATED COLUMN ENTRIES:")
        print("=" * 80)
        
        for entry in entries:
            synonyms = entry.synonyms
            synonyms_type = "unknown"
            
            if synonyms:
                if synonyms.strip().startswith('{') or synonyms.strip().startswith('['):
                    try:
                        parsed = json.loads(synonyms)
                        if isinstance(parsed, (dict, list)):
                            synonyms_type = "JSON (dict_needs - OLD)"
                        else:
                            synonyms_type = "real synonyms"
                    except:
                        synonyms_type = "real synonyms (invalid JSON)"
                else:
                    synonyms_type = "real synonyms (comma-separated)"
                
                preview = synonyms[:150] if len(synonyms) > 150 else synonyms
            else:
                synonyms_type = "NULL/empty"
                preview = "NULL"
            
            print(f"\nID: {entry.id}")
            print(f"  Table: {entry.table_name}, Column: {entry.column_name}")
            print(f"  Created: {entry.created_at}")
            print(f"  Synonyms Type: {synonyms_type}")
            print(f"  Synonyms Value: {preview}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(check_latest())

