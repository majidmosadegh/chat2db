#!/usr/bin/env python3
import asyncio
from api.database import get_db_session
from sqlalchemy import select
from api.db_models import LLMModel

async def check_models():
    session = await get_db_session().__aenter__()
    try:
        result = await session.execute(select(LLMModel))
        models = result.scalars().all()
        print(f'Found {len(models)} LLM models:')
        for model in models:
            print(f'- {model.name}: {model.service_name}, active={model.is_active}, base_url={model.base_url}')
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(check_models())
