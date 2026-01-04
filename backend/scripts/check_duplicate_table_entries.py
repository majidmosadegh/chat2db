import asyncio
import sys
import os
import io
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Fix encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary
from config.config import DATABASE_URL

async def check_duplicates():
    """Check for duplicate table-level entries"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Find tables with multiple table-level entries
        result = await session.execute(
            select(
                DataDictionary.schema_snapshot_id,
                DataDictionary.schema_name,
                DataDictionary.table_name,
                func.count(DataDictionary.id).label('count')
            ).where(
                DataDictionary.column_name.is_(None)
            ).group_by(
                DataDictionary.schema_snapshot_id,
                DataDictionary.schema_name,
                DataDictionary.table_name
            ).having(func.count(DataDictionary.id) > 1)
        )
        
        duplicates = result.all()
        
        if duplicates:
            print(f"Found {len(duplicates)} tables with duplicate table-level entries:")
            print("=" * 80)
            for dup in duplicates:
                print(f"\nSnapshot: {dup[0]}, Schema: {dup[1]}, Table: {dup[2]}, Count: {dup[3]}")
                
                # Get all entries
                entries_result = await session.execute(
                    select(DataDictionary).where(
                        DataDictionary.schema_snapshot_id == dup[0],
                        DataDictionary.schema_name == dup[1],
                        DataDictionary.table_name == dup[2],
                        DataDictionary.column_name.is_(None)
                    ).order_by(DataDictionary.created_at)
                )
                entries = entries_result.scalars().all()
                
                for i, entry in enumerate(entries):
                    print(f"  Entry {i+1}: ID={entry.id}, Created={entry.created_at}, Description={entry.description[:50] if entry.description else 'None'}...")
        else:
            print("No duplicate table-level entries found")

if __name__ == "__main__":
    asyncio.run(check_duplicates())




