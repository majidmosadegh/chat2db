import asyncio
import sys
import os
import json
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.db_models import DataDictionary, AIGenerationJob
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
        # Get total count
        count_result = await session.execute(
            select(func.count(DataDictionary.id)).where(
                DataDictionary.column_name.isnot(None),
                DataDictionary.is_ai_generated == True
            )
        )
        total_count = count_result.scalar()
        
        print(f"Total AI-generated column entries: {total_count}")
        print("=" * 80)
        
        # Get recent entries (last 20)
        result = await session.execute(
            select(
                DataDictionary.id,
                DataDictionary.column_name,
                DataDictionary.synonyms,
                DataDictionary.is_ai_generated,
                DataDictionary.table_name,
                DataDictionary.created_at
            ).where(
                DataDictionary.column_name.isnot(None),
                DataDictionary.is_ai_generated == True
            ).order_by(
                DataDictionary.created_at.desc()
            ).limit(20)
        )
        rows = result.all()
        
        print(f"\nLast {len(rows)} entries (most recent first):")
        print("=" * 80)
        
        json_count = 0
        empty_count = 0
        real_synonyms_count = 0
        
        for row in rows:
            entry_id = row[0]
            col_name = row[1]
            synonyms = row[2]
            is_ai = row[3]
            table_name = row[4]
            created_at = row[5]
            
            synonyms_preview = ""
            synonyms_type = "unknown"
            
            if synonyms:
                if len(synonyms) > 100:
                    synonyms_preview = synonyms[:100] + "..."
                else:
                    synonyms_preview = synonyms
                
                # Check if it's JSON (dict_needs)
                if synonyms.strip().startswith('{') or synonyms.strip().startswith('['):
                    try:
                        parsed = json.loads(synonyms)
                        if isinstance(parsed, (dict, list)):
                            synonyms_type = "JSON (dict_needs)"
                            json_count += 1
                    except:
                        synonyms_type = "real synonyms (looks like JSON but invalid)"
                        real_synonyms_count += 1
                else:
                    synonyms_type = "real synonyms (comma-separated)"
                    real_synonyms_count += 1
            else:
                synonyms_preview = "NULL or empty"
                synonyms_type = "empty"
                empty_count += 1
            
            print(f"\nID: {entry_id}, Table: {table_name}, Column: {col_name}")
            print(f"  Created: {created_at}")
            print(f"  Type: {synonyms_type}")
            print(f"  Value: {synonyms_preview}")
            print("-" * 80)
        
        print("\n" + "=" * 80)
        print("Summary:")
        print(f"  JSON (dict_needs): {json_count}")
        print(f"  Real synonyms: {real_synonyms_count}")
        print(f"  Empty: {empty_count}")
        print("=" * 80)
        
        # Check latest AI job
        job_result = await session.execute(
            select(AIGenerationJob).order_by(AIGenerationJob.created_at.desc()).limit(1)
        )
        latest_job = job_result.scalar_one_or_none()
        
        if latest_job:
            print(f"\nLatest AI Job:")
            print(f"  Job ID: {latest_job.job_id}")
            print(f"  Status: {latest_job.status}")
            print(f"  Created: {latest_job.created_at}")
            print(f"  Total tables: {latest_job.total_tables}")
            print(f"  Completed tables: {latest_job.completed_tables}")

if __name__ == "__main__":
    asyncio.run(check_synonyms())

