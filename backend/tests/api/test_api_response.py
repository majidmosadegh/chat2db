import asyncio
import sys
import os
import json
import io
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary
from config.config import DATABASE_URL

async def test_api_logic():
    """Test the API filtering logic"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Get the most recent entry with real synonyms (ID 379)
        result = await session.execute(
            select(DataDictionary).where(
                DataDictionary.id == 379
            ).limit(1)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            print(f"Entry ID: {entry.id}")
            print(f"Column: {entry.column_name}")
            print(f"Is AI Generated: {entry.is_ai_generated}")
            print(f"Raw Synonyms: {entry.synonyms}")
            print(f"Raw Synonyms Type: {type(entry.synonyms)}")
            
            # Apply the same logic as in API
            synonyms = entry.synonyms or ''
            print(f"\nAfter 'or ''': {synonyms}")
            
            if entry.is_ai_generated and synonyms:
                print("Condition: is_ai_generated and synonyms - TRUE")
                synonyms_stripped = synonyms.strip()
                print(f"Stripped: {synonyms_stripped}")
                print(f"Starts with {{: {synonyms_stripped.startswith('{')}")
                print(f"Starts with [: {synonyms_stripped.startswith('[')}")
                
                if synonyms_stripped.startswith('{') or synonyms_stripped.startswith('['):
                    print("Starts with { or [ - TRUE, trying to parse JSON...")
                    try:
                        parsed = json.loads(synonyms)
                        print(f"Parsed successfully: {type(parsed)}")
                        if isinstance(parsed, (dict, list)):
                            print("Is dict or list - TRUE, setting to empty string")
                            synonyms = ''
                        else:
                            print("Is dict or list - FALSE, keeping synonyms")
                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        print(f"JSON parse failed: {e}")
                        print("Keeping synonyms as-is")
                else:
                    print("Does NOT start with { or [, keeping synonyms as-is")
            else:
                print("Condition: is_ai_generated and synonyms - FALSE")
            
            print(f"\nFinal Synonyms: '{synonyms}'")
        else:
            print("Entry not found")

if __name__ == "__main__":
    asyncio.run(test_api_logic())

