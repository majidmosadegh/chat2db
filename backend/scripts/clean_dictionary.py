"""
Clean all AI dictionary jobs and entries
Script to clean test data
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete

from config.config import DATABASE_URL
from api.db_models import AIGenerationJob, DataDictionary, AITableTask, Base

async def clean_all():
    """Clean all AI jobs and dictionary entries"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Cancel all active jobs first (if service is running)
            try:
                from services.ai_dictionary_generator import ai_dictionary_generator
                for job_id in list(ai_dictionary_generator._jobs.keys()):
                    try:
                        await ai_dictionary_generator.cancel_job(job_id)
                    except:
                        pass
            except:
                pass  # Service might not be initialized
            
            # Delete all dictionary entries
            dict_result = await session.execute(delete(DataDictionary))
            dict_deleted = dict_result.rowcount
            
            # Delete all AI jobs (table tasks will be deleted by cascade)
            jobs_result = await session.execute(delete(AIGenerationJob))
            jobs_deleted = jobs_result.rowcount
            
            await session.commit()
            
            print("Cleaned successfully:")
            print(f"   - {jobs_deleted} AI job(s) deleted")
            print(f"   - {dict_deleted} dictionary entry/entries deleted")
            
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(clean_all())

