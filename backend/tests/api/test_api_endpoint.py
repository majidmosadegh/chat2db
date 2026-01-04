import asyncio
import sys
import os
import json
import io
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Fix encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary, SchemaMetadata
from config.config import DATABASE_URL

async def test_api_logic():
    """Test the exact API logic"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Get a snapshot_id (assuming 1)
        snapshot_id = 1
        
        # Get a table
        table_result = await session.execute(
            select(SchemaMetadata.schema_name, SchemaMetadata.table_name).where(
                SchemaMetadata.schema_snapshot_id == snapshot_id
            ).limit(1)
        )
        table_row = table_result.first()
        if not table_row:
            print("No tables found")
            return
        
        schema_name, table_name = table_row
        
        print(f"Testing for: {schema_name}.{table_name}")
        print("=" * 80)
        
        # Get dictionary entries for this table
        dict_result = await session.execute(
            select(DataDictionary).where(
                DataDictionary.schema_snapshot_id == snapshot_id,
                DataDictionary.schema_name == schema_name,
                DataDictionary.table_name == table_name,
                DataDictionary.column_name.isnot(None)
            ).limit(5)
        )
        entries = dict_result.scalars().all()
        
        print(f"Found {len(entries)} column entries")
        print("=" * 80)
        
        # Simulate API logic
        column_dict = {}
        for entry in entries:
            col_name = entry.column_name
            if not col_name:
                continue
            
            try:
                example_values = json.loads(entry.example_values or '[]')
            except Exception:
                example_values = []
            
            description = entry.description or ''
            synonyms = entry.synonyms or ''
            
            # Apply the same filtering logic as API
            if entry.is_ai_generated and synonyms:
                synonyms_stripped = synonyms.strip()
                if synonyms_stripped.startswith('{') or synonyms_stripped.startswith('['):
                    try:
                        parsed = json.loads(synonyms)
                        if isinstance(parsed, (dict, list)):
                            synonyms = ''  # It's dict_needs (legacy), not real synonyms
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
            
            column_dict[col_name] = {
                'description': description,
                'example_values': example_values,
                'synonyms': synonyms,
                'is_ai_generated': entry.is_ai_generated
            }
            
            print(f"\nColumn: {col_name}")
            print(f"  Raw DB Synonyms: {entry.synonyms[:100] if entry.synonyms else 'None'}...")
            print(f"  After API Filter: '{synonyms}'")
            print(f"  Is AI Generated: {entry.is_ai_generated}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_api_logic())



