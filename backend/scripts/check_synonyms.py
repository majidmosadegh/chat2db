import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary
from config.config import DATABASE_URL

async def check_synonyms():
    """Check synonyms field in DataDictionary table"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Get first 10 column-level entries
        result = await session.execute(
            select(
                DataDictionary.column_name,
                DataDictionary.synonyms,
                DataDictionary.is_ai_generated,
                DataDictionary.table_name
            ).where(
                DataDictionary.column_name.isnot(None)
            ).limit(10)
        )
        rows = result.all()
        
        print(f"Found {len(rows)} column entries")
        print("=" * 80)
        
        for row in rows:
            col_name = row[0]
            synonyms = row[1]
            is_ai = row[2]
            table_name = row[3]
            
            synonyms_preview = ""
            if synonyms:
                if len(synonyms) > 100:
                    synonyms_preview = synonyms[:100] + "..."
                else:
                    synonyms_preview = synonyms
            else:
                synonyms_preview = "NULL"
            
            print(f"Table: {table_name}, Column: {col_name}")
            print(f"  AI Generated: {is_ai}")
            print(f"  Synonyms: {synonyms_preview}")
            print(f"  Starts with {{: {synonyms.strip().startswith('{') if synonyms else False}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(check_synonyms())

