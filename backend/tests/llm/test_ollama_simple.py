"""
Simple direct test for Ollama connection
"""

import asyncio
import httpx


async def test():
    url = "http://37.255.205.140:11435"
    
    print(f"Testing: {url}")
    print("-" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Direct API call
        print("\n1. Testing /api/tags endpoint...")
        try:
            response = await client.get(f"{url}/api/tags")
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                print(f"   [SUCCESS] Found {len(models)} models:")
                for m in models:
                    print(f"      - {m.get('name')}")
                return True
            else:
                print(f"   [ERROR] Response: {response.text[:200]}")
        except httpx.ConnectError as e:
            print(f"   [ERROR] Connection failed: {e}")
        except httpx.TimeoutException:
            print(f"   [ERROR] Timeout")
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {e}")
        
        # Test 2: Try /api/version
        print("\n2. Testing /api/version endpoint...")
        try:
            response = await client.get(f"{url}/api/version")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   [SUCCESS] Version: {response.text}")
            else:
                print(f"   [ERROR] Response: {response.text[:200]}")
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {e}")
        
        # Test 3: Try generation with a model (if we know one exists)
        print("\n3. Testing /api/generate endpoint...")
        try:
            payload = {
                "model": "gemma3:4b",  # From your server
                "prompt": "Hello",
                "stream": False
            }
            response = await client.post(
                f"{url}/api/generate",
                json=payload,
                timeout=60.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"   [SUCCESS] Generated: {result.get('response', '')[:100]}...")
                return True
            else:
                print(f"   [ERROR] Response: {response.text[:200]}")
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {e}")
    
    return False


if __name__ == "__main__":
    result = asyncio.run(test())
    print("\n" + "=" * 60)
    if result:
        print("[SUCCESS] Connection test passed!")
    else:
        print("[FAILED] Connection test failed!")
    print("=" * 60)

