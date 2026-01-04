#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from chat.context_loader import ContextLoader
from api.db_models import get_db_session
import asyncio

async def test_context_loading():
    try:
        async for session in get_db_session():
            loader = ContextLoader(session)

            print("Testing context loading for snapshot_id=11...")

            context = await loader.load_all_context(11)

            print("Schema info count:", len(context["schema"]))
            print("Data dictionary count:", len(context["data_dictionary"]))
            print("Relationships count:", len(context["relationships"]))
            print("Use cases count:", len(context["use_cases"]))
            print("Snapshot name:", context["snapshot_name"])

            # Show sample schema
            if context["schema"]:
                print("\nSample schema:")
                for item in context["schema"][:3]:
                    print(f"  {item.schema_name}.{item.table_name}.{item.column_name} ({item.column_type})")

            # Show sample data dictionary
            if context["data_dictionary"]:
                print("\nSample data dictionary:")
                for item in context["data_dictionary"][:2]:
                    print(f"  {item.table_name}.{item.column_name}: {item.description[:50] if item.description else 'No description'}")

            break

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_context_loading())
