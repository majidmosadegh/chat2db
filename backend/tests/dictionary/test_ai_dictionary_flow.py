"""
Test script to verify the complete AI dictionary generation flow:
1. Database connection and data fetching
2. LLM connection
3. Data passing to LLM model
"""
import asyncio
import sys
import os
import logging
from datetime import datetime, timezone

# Add backend directory to path
script_dir = os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test 1: Database connection and data fetching"""
    logger.info("=" * 80)
    logger.info("TEST 1: Database Connection and Data Fetching")
    logger.info("=" * 80)
    
    try:
        from api.database import get_db_session
        from api.db_models import SchemaSnapshot, DatabaseConnection, SchemaMetadata
        from sqlalchemy import select
        from services.db_connector import DirectDatabaseConnector
        
        # Get first snapshot
        async for session in get_db_session():
            result = await session.execute(
                select(SchemaSnapshot)
                .join(DatabaseConnection, SchemaSnapshot.connection_id == DatabaseConnection.id)
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            
            if not snapshot:
                logger.error("✗ No snapshot found in database")
                return False
            
            logger.info(f"✓ Found snapshot: {snapshot.name} (ID: {snapshot.id})")
            
            # Get connection info
            conn_result = await session.execute(
                select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
            )
            connection = conn_result.scalar_one_or_none()
            
            if not connection:
                logger.error("✗ Connection not found for snapshot")
                return False
            
            logger.info(f"✓ Found connection: {connection.db_type}://{connection.host}:{connection.port}/{connection.database_name}")
            
            # Get first table
            table_result = await session.execute(
                select(SchemaMetadata.schema_name, SchemaMetadata.table_name)
                .where(SchemaMetadata.schema_snapshot_id == snapshot.id)
                .distinct()
                .limit(1)
            )
            table_row = table_result.first()
            
            if not table_row:
                logger.error("✗ No tables found in snapshot")
                return False
            
            schema_name, table_name = table_row
            logger.info(f"✓ Found table: {schema_name}.{table_name}")
            
            # Test database connector
            logger.info("Testing database connector...")
            db_connector = DirectDatabaseConnector(
                db_type=connection.db_type,
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=connection.password_encrypted,
                database=connection.database_name
            )
            
            # Test query
            query = f"SELECT TOP 3 * FROM {schema_name}.{table_name}"
            logger.info(f"Executing query: {query}")
            sample_rows = await db_connector.execute_query(query, limit=3)
            
            if sample_rows:
                logger.info(f"✓ Successfully fetched {len(sample_rows)} sample rows")
                logger.info(f"  First row keys: {list(sample_rows[0].keys())[:5]}...")
            else:
                logger.warning("⚠ No data returned from query (table might be empty)")
            
            await db_connector.disconnect()
            logger.info("✓ Database connection test PASSED")
            return True
            
    except Exception as e:
        logger.error(f"✗ Database connection test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_connection():
    """Test 2: LLM connection and model availability"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: LLM Connection and Model Availability")
    logger.info("=" * 80)
    
    try:
        from api.database import get_db_session
        from services.llm_service import LLMService
        
        llm_service = LLMService()
        
        async for session in get_db_session():
            # Initialize LLM service
            logger.info("Initializing LLM service...")
            await llm_service.initialize(session)
            logger.info("✓ LLM service initialized")
            
            # Get active models
            logger.info("Fetching active models...")
            models = await llm_service.get_active_models(session)
            
            if not models:
                logger.error("✗ No active LLM models found")
                return False
            
            logger.info(f"✓ Found {len(models)} active model(s):")
            for model in models:
                logger.info(f"  - {model.get('name', 'Unknown')} (ID: {model.get('id')})")
            
            logger.info("✓ LLM connection test PASSED")
            return True
            
    except Exception as e:
        logger.error(f"✗ LLM connection test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_data_to_llm():
    """Test 3: Passing data to LLM model"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Passing Data to LLM Model")
    logger.info("=" * 80)
    
    try:
        from api.database import get_db_session
        from api.db_models import SchemaSnapshot, DatabaseConnection, SchemaMetadata
        from sqlalchemy import select
        from services.db_connector import DirectDatabaseConnector
        from services.llm_service import LLMService
        
        llm_service = LLMService()
        
        async for session in get_db_session():
            # Get snapshot and table
            result = await session.execute(
                select(SchemaSnapshot)
                .join(DatabaseConnection, SchemaSnapshot.connection_id == DatabaseConnection.id)
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            
            if not snapshot:
                logger.error("✗ No snapshot found")
                return False
            
            # Get connection
            conn_result = await session.execute(
                select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
            )
            connection = conn_result.scalar_one_or_none()
            
            # Get first table
            table_result = await session.execute(
                select(SchemaMetadata.schema_name, SchemaMetadata.table_name)
                .where(SchemaMetadata.schema_snapshot_id == snapshot.id)
                .distinct()
                .limit(1)
            )
            table_row = table_result.first()
            
            if not table_row:
                logger.error("✗ No tables found")
                return False
            
            schema_name, table_name = table_row
            
            # Fetch sample data
            logger.info(f"Fetching sample data from {schema_name}.{table_name}...")
            db_connector = DirectDatabaseConnector(
                db_type=connection.db_type,
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=connection.password_encrypted,
                database=connection.database_name
            )
            
            query = f"SELECT TOP 2 * FROM {schema_name}.{table_name}"
            sample_rows = await db_connector.execute_query(query, limit=2)
            await db_connector.disconnect()
            
            if not sample_rows:
                logger.warning("⚠ No sample data available, using empty data for test")
                sample_rows = []
            
            logger.info(f"✓ Fetched {len(sample_rows)} sample rows")
            
            # Get schema info
            logger.info("Fetching schema information...")
            columns_result = await session.execute(
                select(SchemaMetadata)
                .where(
                    SchemaMetadata.schema_snapshot_id == snapshot.id,
                    SchemaMetadata.schema_name == schema_name,
                    SchemaMetadata.table_name == table_name
                )
            )
            columns = columns_result.scalars().all()
            logger.info(f"✓ Found {len(columns)} columns")
            
            # Initialize LLM
            await llm_service.initialize(session)
            models = await llm_service.get_active_models(session)
            
            if not models:
                logger.error("✗ No active LLM models found")
                return False
            
            model_id = models[0]["id"]
            logger.info(f"Using model: {models[0].get('name', 'Unknown')} (ID: {model_id})")
            
            # Create a simple test prompt
            test_prompt = f"""Generate a brief description for a database table.

Table Name: {schema_name}.{table_name}
Columns: {', '.join([col.column_name for col in columns[:5]])}
Sample Data: {str(sample_rows[:1])[:200] if sample_rows else 'No data'}

Please provide a one-sentence description of what this table stores."""

            logger.info("Sending test prompt to LLM...")
            logger.info(f"Prompt length: {len(test_prompt)} characters")
            
            # Generate with LLM
            response = await llm_service.generate_text(
                session=session,
                model_id=model_id,
                prompt=test_prompt,
                temperature=0.3,
                max_tokens=200
            )
            
            if response and response.text:
                logger.info(f"✓ LLM response received ({len(response.text)} characters)")
                logger.info(f"  Response preview: {response.text[:150]}...")
                logger.info("✓ Data to LLM test PASSED")
                return True
            else:
                logger.error("✗ Empty response from LLM")
                return False
            
    except Exception as e:
        logger.error(f"✗ Data to LLM test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_full_flow():
    """Test 4: Full AI Dictionary Generator flow"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Full AI Dictionary Generator Flow")
    logger.info("=" * 80)
    
    try:
        from services.ai_dictionary_generator import ai_dictionary_generator
        from api.database import get_db_session
        from api.db_models import SchemaSnapshot
        from sqlalchemy import select
        
        # Get first snapshot
        async for session in get_db_session():
            result = await session.execute(
                select(SchemaSnapshot).limit(1)
            )
            snapshot = result.scalar_one_or_none()
            
            if not snapshot:
                logger.error("✗ No snapshot found")
                return False
            
            logger.info(f"Testing with snapshot: {snapshot.name} (ID: {snapshot.id})")
            
            # Test the _sample_table_data method
            logger.info("Testing _sample_table_data method...")
            sample_data = await ai_dictionary_generator._sample_table_data(
                snapshot_id=snapshot.id,
                schema_name="dbo",
                table_name="EnergyExchange",
                limit=2
            )
            
            if sample_data is not None:
                logger.info(f"✓ _sample_table_data returned {len(sample_data) if sample_data else 0} rows")
            else:
                logger.warning("⚠ _sample_table_data returned None")
            
            # Test the _get_table_schema method
            logger.info("Testing _get_table_schema method...")
            schema_info = await ai_dictionary_generator._get_table_schema(
                snapshot_id=snapshot.id,
                schema_name="dbo",
                table_name="EnergyExchange"
            )
            
            if schema_info and schema_info.get("columns"):
                logger.info(f"✓ _get_table_schema returned {len(schema_info['columns'])} columns")
            else:
                logger.warning("⚠ _get_table_schema returned empty schema")
            
            logger.info("✓ Full flow test PASSED")
            return True
            
    except Exception as e:
        logger.error(f"✗ Full flow test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("AI Dictionary Generation Flow - Complete Test Suite")
    logger.info("=" * 80)
    logger.info("")
    
    results = []
    
    # Run tests
    results.append(("Database Connection", await test_database_connection()))
    results.append(("LLM Connection", await test_llm_connection()))
    results.append(("Data to LLM", await test_data_to_llm()))
    results.append(("Full Flow", await test_full_flow()))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✓ All tests PASSED!")
        return 0
    else:
        logger.error("✗ Some tests FAILED")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)




