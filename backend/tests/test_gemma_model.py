#!/usr/bin/env python3
"""
Test script for Gemma model connection
"""

import asyncio
import httpx
import os
import sys
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(__file__))

from config.config import DATABASE_URL
from api.db_models import LLMModel

async def find_gemma_model():
    """Find Gemma model in database"""
    print("Searching for Gemma model in database...")

    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # Find model named "gemma"
            result = await session.execute(
                select(LLMModel).where(LLMModel.name.ilike("%gemma%"))
            )
            model = result.scalar_one_or_none()

            if model:
                print(f"Found Gemma model: {model.name}")
                print(f"Service: {model.service_name}")
                print(f"URL: {model.base_url}")
                print(f"Model Name: {model.model_name}")
                print(f"API Key: {'Set' if model.api_key else 'Not set'}")
                print(f"Temperature: {model.temperature}")
                print(f"Max Tokens: {model.max_tokens}")
                print(f"Active: {model.is_active}")
                return model
            else:
                print("Gemma model not found in database")
                return None

    except Exception as e:
        print(f"Database error: {str(e)}")
        return None

async def test_gemma_connection(model):
    """Test connection to Gemma model"""
    print(f"\nTesting connection to {model.name}...")
    print(f"URL: {model.base_url}")
    print("-" * 40)

    timeout = httpx.Timeout(30.0)
    success = False
    error_details = []

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try OpenAI-compatible API first
            try:
                print("Trying OpenAI-compatible API (/v1/chat/completions)...")

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
                    "messages": [{"role": "user", "content": "Hello, please respond with just 'Gemma model is working' to confirm connection."}],
                    "max_tokens": 50,
                    "temperature": 0.1
                }

                print(f"Sending request to: {api_url}")
                response = await client.post(api_url, headers=headers, json=test_payload)
                print(f"Response status: {response.status_code}")

                if response.status_code == 200:
                    response_data = response.json()
                    print("Response received successfully!")

                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        content = response_data["choices"][0].get("message", {}).get("content", "")
                        print(f"Model response: {content}")
                        success = True
                        print("SUCCESS: OpenAI-compatible API works!")
                    else:
                        print(f"Unexpected response format: {response_data}")
                else:
                    error_details.append(f"HTTP {response.status_code}: {response.text[:200]}")

            except Exception as e:
                error_msg = str(e)
                print(f"OpenAI API failed: {error_msg}")
                error_details.append(f"OpenAI API: {error_msg}")

            # If OpenAI failed, try Ollama-style API
            if not success:
                try:
                    print("\nTrying Ollama-style API (/generate)...")

                    headers = {"Content-Type": "application/json"}
                    if model.api_key:
                        headers["Authorization"] = f"Bearer {model.api_key}"

                    api_url = f"{model.base_url.rstrip('/')}/generate"
                    test_payload = {
                        "model": model.model_name,
                        "prompt": "Hello, please respond with just 'Gemma model is working' to confirm connection.",
                        "temperature": 0.1,
                        "max_tokens": 50
                    }

                    print(f"Sending request to: {api_url}")
                    response = await client.post(api_url, headers=headers, json=test_payload)
                    print(f"Response status: {response.status_code}")

                    if response.status_code == 200:
                        response_data = response.json()
                        print("Response received successfully!")

                        if "response" in response_data:
                            content = response_data["response"]
                            print(f"Model response: {content}")
                            success = True
                            print("SUCCESS: Ollama-style API works!")
                        else:
                            print(f"Unexpected response format: {response_data}")
                    else:
                        error_details.append(f"HTTP {response.status_code}: {response.text[:200]}")

                except Exception as e:
                    error_msg = str(e)
                    print(f"Ollama API failed: {error_msg}")
                    error_details.append(f"Ollama API: {error_msg}")

            # Try basic connectivity
            if not success:
                try:
                    print("\nTesting basic connectivity...")
                    base_url = model.base_url.rstrip('/')
                    health_url = base_url if base_url.endswith('/v1') else f"{base_url}/v1"

                    print(f"Checking health endpoint: {health_url}")
                    response = await client.get(health_url, headers=headers if model.api_key else {})
                    print(f"Health check status: {response.status_code}")

                    if response.status_code == 200:
                        print("Basic connectivity successful!")
                        success = True
                    else:
                        error_details.append(f"Health check: HTTP {response.status_code}")

                except Exception as e:
                    error_msg = str(e)
                    print(f"Basic connectivity failed: {error_msg}")
                    error_details.append(f"Basic connectivity: {error_msg}")

    except Exception as e:
        print(f"Connection setup error: {str(e)}")
        error_details.append(f"Setup: {str(e)}")

    return success, error_details

async def main():
    """Main test function"""
    print("Gemma Model Test Script")
    print("=" * 50)

    # Find Gemma model
    gemma_model = await find_gemma_model()

    if not gemma_model:
        print("\nERROR: Gemma model not found in database!")
        print("Please make sure the model is configured in the admin panel.")
        return False

    # Test connection
    success, errors = await test_gemma_connection(gemma_model)

    print("\n" + "=" * 50)
    print("TEST RESULTS:")
    print("=" * 50)

    if success:
        print("SUCCESS: Gemma model is accessible and working!")
        print("You can use this model in your Text-to-SQL system.")
        return True
    else:
        print("FAILURE: Cannot connect to Gemma model")
        print("\nError details:")
        for i, error in enumerate(errors, 1):
            print(f"{i}. {error}")

        print("\nTroubleshooting suggestions:")
        print("1. Check if the Gemma server is running on the configured IP/port")
        print("2. Verify the model name is correct")
        print("3. Check network connectivity and firewall settings")
        print("4. Ensure API authentication is properly configured if required")
        print("5. Check server logs for more detailed error information")

        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)

