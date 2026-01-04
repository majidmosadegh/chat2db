#!/usr/bin/env python3
"""
Test script to check AI model connection to IP 172.16.47.12
Tests both database connectivity and AI model API accessibility
"""

import asyncio
import httpx
import os
import sys
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(__file__))

from config.config import DATABASE_URL
from api.db_models import LLMModel
from api.database import decrypt_password

async def test_database_connection():
    """Test connection to the metadata database"""
    logger.info("Testing database connection...")

    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # Try to query LLM models
            result = await session.execute(select(LLMModel).order_by(LLMModel.created_at.desc()))
            models = result.scalars().all()

            logger.success("Database connection successful!")
            logger.info(f"Found {len(models)} AI models in database:")

            for model in models:
                logger.info(f"   • {model.name}: {model.base_url} ({model.model_name})")
                if model.base_url.startswith("http://172.16.47.12"):
                    logger.info(f"     Found target IP model!")

            return models

    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return None

async def test_ai_model_connection(model):
    """Test connection to a specific AI model"""
    logger.info(f"Testing connection to model: {model.name}")
    logger.info(f"   📍 URL: {model.base_url}")
    logger.info(f"   🧠 Model: {model.model_name}")

    # Test different API formats
    timeout = httpx.Timeout(30.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        success = False
        last_error = None

        # 1. Try OpenAI-compatible API
        try:
            logger.debug("   🔄 Testing OpenAI-compatible API (/v1/chat/completions)...")

            headers = {"Content-Type": "application/json"}
            if model.api_key:
                headers["Authorization"] = f"Bearer {model.api_key}"

            # Determine the correct endpoint
            base_url = model.base_url.rstrip('/')
            if base_url.endswith('/v1'):
                api_url = f"{base_url}/chat/completions"
            else:
                api_url = f"{base_url}/v1/chat/completions"

            test_payload = {
                "model": model.model_name,
                "messages": [{"role": "user", "content": "Hello, this is a test connection. Please respond with 'Connection successful'."}],
                "max_tokens": 50,
                "temperature": 0.1
            }

            response = await client.post(api_url, headers=headers, json=test_payload)
            response.raise_for_status()

            response_data = response.json()
            if "choices" in response_data and len(response_data["choices"]) > 0:
                content = response_data["choices"][0].get("message", {}).get("content", "")
                logger.success("   ✅ OpenAI API successful!")
                logger.debug(f"   📝 Response: {content[:100]}...")
                success = True
            else:
                logger.warning(f"   ⚠️  Unexpected response format: {response_data}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"   ❌ OpenAI API failed: {error_msg}")
            last_error = error_msg

        # 2. If OpenAI failed, try Ollama-style API
        if not success:
            try:
                print("   🔄 Testing Ollama-style API (/generate)...")

                headers = {"Content-Type": "application/json"}
                if model.api_key:
                    headers["Authorization"] = f"Bearer {model.api_key}"

                api_url = f"{model.base_url.rstrip('/')}/generate"
                test_payload = {
                    "model": model.model_name,
                    "prompt": "Hello, this is a test connection. Please respond with 'Connection successful'.",
                    "temperature": 0.1,
                    "max_tokens": 50
                }

                response = await client.post(api_url, headers=headers, json=test_payload)
                response.raise_for_status()

                response_data = response.json()
                if "response" in response_data:
                    content = response_data["response"]
                    print(f"   ✅ Ollama API successful!")
                    print(f"   📝 Response: {content[:100]}...")
                    success = True
                else:
                    print(f"   ⚠️  Unexpected response format: {response_data}")

            except Exception as e:
                error_msg = str(e)
                print(f"   ❌ Ollama API failed: {error_msg}")
                last_error = error_msg

        # 3. Try basic connectivity test
        if not success:
            try:
                print("   🔄 Testing basic connectivity...")

                base_url = model.base_url.rstrip('/')
                if base_url.endswith('/v1'):
                    health_url = base_url
                else:
                    health_url = f"{base_url}/v1"

                response = await client.get(health_url, headers=headers if model.api_key else {})
                if response.status_code == 200:
                    print(f"   ✅ Basic connectivity successful! (Status: {response.status_code})")
                    success = True
                else:
                    print(f"   ⚠️  Basic connectivity returned status: {response.status_code}")

            except Exception as e:
                error_msg = str(e)
                print(f"   ❌ Basic connectivity failed: {error_msg}")

        return success, last_error

async def create_test_model_if_needed(models, target_ip="172.16.47.12"):
    """Create a test model for the target IP if it doesn't exist"""
    target_url = f"http://{target_ip}"

    # Check if model already exists
    for model in models:
        if model.base_url.startswith(target_url):
            print(f"📋 Found existing model for {target_ip}: {model.name}")
            return model

    print(f"🆕 No model found for {target_ip}, creating test model...")

    # Create a new test model
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create test model
        test_model = LLMModel(
            name=f"Test Model {target_ip}",
            service_name="vLLM",
            base_url=target_url,
            api_key=None,  # Assuming no auth required for local models
            model_name="test-model",
            max_tokens=2048,
            temperature=0.7,
            top_p=1.0,
            is_active=False
        )

        session.add(test_model)
        await session.commit()
        await session.refresh(test_model)

        print(f"✅ Created test model: {test_model.name} (ID: {test_model.id})")
        return test_model

async def main():
    """Main test function"""
    logger.info("🚀 Starting AI Model Connection Test for IP 172.16.47.12")
    logger.info("=" * 60)

    # Test database connection first
    models = await test_database_connection()
    if models is None:
        print("\n❌ Cannot proceed without database connection!")
        return

    # Find or create model for target IP
    target_model = await create_test_model_if_needed(models, "172.16.47.12")

    if target_model:
        # Test AI model connection
        success, error = await test_ai_model_connection(target_model)

        logger.info("\n" + "=" * 60)
        if success:
            logger.success("🎉 SUCCESS: Connection to AI model is working!")
            logger.success("✅ You have access to the AI model on 172.16.47.12")
        else:
            logger.error("❌ FAILURE: Cannot connect to AI model")
            logger.error(f"🔍 Last error: {error}")
            logger.info("\n🔧 Possible issues:")
            logger.info("   • AI model server is not running")
            logger.info("   • Wrong IP address or port")
            logger.info("   • Firewall blocking connection")
            logger.info("   • API authentication required")
            logger.info("   • Network connectivity issues")
    else:
        logger.error("❌ Could not create or find test model")

if __name__ == "__main__":
    asyncio.run(main())


