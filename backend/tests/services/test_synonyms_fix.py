import asyncio
import sys
import os
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary
from config.config import DATABASE_URL

async def test_synonyms():
    """Test that synonyms filtering works correctly"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Simulate what the API endpoint does
        result = await session.execute(
            select(DataDictionary).where(
                DataDictionary.column_name == "Id",
                DataDictionary.table_name == "EnergyExchange"
            ).limit(1)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            print("Before filtering:")
            print(f"  Synonyms: {entry.synonyms[:100] if entry.synonyms else 'None'}")
            print(f"  Is AI Generated: {entry.is_ai_generated}")
            
            # Apply the same filtering logic as in the API
            synonyms = entry.synonyms or ''
            if entry.is_ai_generated and synonyms:
                synonyms_stripped = synonyms.strip()
                if synonyms_stripped.startswith('{') or synonyms_stripped.startswith('['):
                    import json
                    try:
                        parsed = json.loads(synonyms)
                        if isinstance(parsed, (dict, list)):
                            synonyms = ''  # It's dict_needs, not real synonyms
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
            
            print("\nAfter filtering:")
            print(f"  Synonyms: '{synonyms}'")
            print(f"  Is empty: {synonyms == ''}")
            
            # Now let's add a real synonym and check
            print("\n--- Testing with real synonym ---")
            # Create a test entry with real synonym
            test_entry = DataDictionary(
                schema_snapshot_id=entry.schema_snapshot_id,
                schema_name=entry.schema_name,
                table_name=entry.table_name,
                column_name="TestColumn",
                description="Test",
                synonyms="alias1, alias2, alias3",  # Real synonyms (comma-separated)
                is_ai_generated=False,
                is_sensitive=False
            )
            session.add(test_entry)
            await session.commit()
            
            # Check the test entry
            result2 = await session.execute(
                select(DataDictionary).where(DataDictionary.column_name == "TestColumn")
            )
            test_entry_loaded = result2.scalar_one_or_none()
            
            if test_entry_loaded:
                print(f"Test entry synonyms: '{test_entry_loaded.synonyms}'")
                print(f"Is AI Generated: {test_entry_loaded.is_ai_generated}")
                
                # Apply filtering
                test_synonyms = test_entry_loaded.synonyms or ''
                if test_entry_loaded.is_ai_generated and test_synonyms:
                    test_synonyms_stripped = test_synonyms.strip()
                    if test_synonyms_stripped.startswith('{') or test_synonyms_stripped.startswith('['):
                        import json
                        try:
                            parsed = json.loads(test_synonyms)
                            if isinstance(parsed, (dict, list)):
                                test_synonyms = ''
                        except:
                            pass
                
                print(f"After filtering: '{test_synonyms}'")
                print(f"Should keep original: {test_synonyms == 'alias1, alias2, alias3'}")
            
            # Cleanup
            await session.delete(test_entry)
            await session.commit()

if __name__ == "__main__":
    asyncio.run(test_synonyms())

