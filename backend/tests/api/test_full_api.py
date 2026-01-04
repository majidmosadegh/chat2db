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

from api.db_models import DataDictionary, SchemaMetadata
from config.config import DATABASE_URL

async def test_full_api():
    """Test the full API response logic"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        snapshot_id = 1
        
        # Get a table that has NEW entries with real synonyms
        result = await session.execute(
            select(SchemaMetadata.schema_name, SchemaMetadata.table_name).where(
                SchemaMetadata.schema_snapshot_id == snapshot_id,
                SchemaMetadata.table_name == "GoodsExchange_Export"
            ).limit(1)
        )
        table_row = result.first()
        if not table_row:
            print("Table not found")
            return
        
        schema_name, table_name = table_row
        print(f"Testing table: {schema_name}.{table_name}")
        print("=" * 80)
        
        # Get columns
        cols_result = await session.execute(
            select(
                SchemaMetadata.column_name,
                SchemaMetadata.column_type
            ).where(
                and_(
                    SchemaMetadata.schema_snapshot_id == snapshot_id,
                    SchemaMetadata.schema_name == schema_name,
                    SchemaMetadata.table_name == table_name,
                    SchemaMetadata.column_name.isnot(None)
                )
            ).limit(5)
        )
        columns_data = cols_result.all()
        
        # Get dictionary entries
        dict_result = await session.execute(
            select(DataDictionary).where(
                DataDictionary.schema_snapshot_id == snapshot_id,
                DataDictionary.schema_name == schema_name,
                DataDictionary.table_name == table_name,
                DataDictionary.column_name.isnot(None)
            )
        )
        dict_entries = dict_result.scalars().all()
        
        # Build column_dict (same as API)
        column_dict = {}
        for entry in dict_entries:
            col_name = entry.column_name
            if not col_name:
                continue
            
            try:
                example_values = json.loads(entry.example_values or '[]')
            except Exception:
                example_values = []
            
            description = entry.description or ''
            synonyms = entry.synonyms or ''
            
            # Apply filtering
            if entry.is_ai_generated and synonyms:
                synonyms_stripped = synonyms.strip()
                if synonyms_stripped.startswith('{') or synonyms_stripped.startswith('['):
                    try:
                        parsed = json.loads(synonyms)
                        if isinstance(parsed, (dict, list)):
                            synonyms = ''
                    except:
                        pass
            
            column_dict[col_name] = {
                'description': description,
                'example_values': example_values,
                'synonyms': synonyms,
                'is_ai_generated': entry.is_ai_generated
            }
        
        # Build columns array (same as API)
        columns = []
        for col_name, col_type in columns_data:
            col_dict = column_dict.get(col_name, {})
            columns.append({
                'name': col_name,
                'type': col_type,
                'description': col_dict.get('description', ''),
                'example_values': col_dict.get('example_values', []),
                'synonyms': col_dict.get('synonyms', ''),
                'is_ai_generated': col_dict.get('is_ai_generated', False)
            })
        
        print("\nAPI Response (first 5 columns):")
        print("=" * 80)
        for col in columns[:5]:
            print(f"\nColumn: {col['name']}")
            print(f"  Description: {col['description'][:50]}...")
            print(f"  Synonyms: '{col['synonyms']}'")
            print(f"  Is AI Generated: {col['is_ai_generated']}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_full_api())



