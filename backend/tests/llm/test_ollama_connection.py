"""
Test script to check connectivity to Ollama server
Tests the connection to http://37.255.205.140:11435
"""

import asyncio
import httpx
import json
import socket
from typing import Dict, Any


OLLAMA_BASE_URL = "http://37.255.205.140:11435"
TIMEOUT = 60.0


def test_port_connectivity(host: str, port: int) -> bool:
    """Test if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"   Socket test error: {str(e)}")
        return False


async def test_ollama_connection():
    """Test basic connectivity to Ollama server."""
    print("=" * 60)
    print("Testing Ollama Connection")
    print("=" * 60)
    print(f"Server URL: {OLLAMA_BASE_URL}")
    print()
    
    # Extract host and port
    from urllib.parse import urlparse
    parsed = urlparse(OLLAMA_BASE_URL)
    host = parsed.hostname
    port = parsed.port or 11434
    
    # Test port connectivity (informational only, don't fail if it doesn't work)
    print("Test -1: Testing port connectivity...")
    if test_port_connectivity(host, port):
        print(f"[OK] Port {port} is open on {host}")
    else:
        print(f"[WARNING] Port {port} socket test failed (will try HTTP anyway)")
        print("   Note: Some firewalls block socket tests but allow HTTP")
    print()
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Test 0: Basic connectivity test
        print("Test 0: Basic connectivity test...")
        try:
            # Try to connect to root endpoint first
            response = await client.get(f"{OLLAMA_BASE_URL}/", follow_redirects=True, timeout=10)
            print(f"   Root endpoint status: {response.status_code}")
            if response.status_code != 200:
                print(f"   Response: {response.text[:200] if response.text else '(empty)'}")
        except httpx.TimeoutException:
            print("   [ERROR] Timeout connecting to server")
        except httpx.ConnectError as e:
            print(f"   [ERROR] Connection error: {str(e)}")
            print("   This usually means the server is unreachable or firewall is blocking")
        except Exception as e:
            print(f"   [ERROR] Error: {str(e)}")
        print()
        
        # Test 1: Check if server is reachable
        print("Test 1: Checking server connectivity...")
        try:
            # Try with longer timeout and verify SSL
            response = await client.get(
                f"{OLLAMA_BASE_URL}/api/tags",
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True
            )
            print(f"   Status code: {response.status_code}")
            print(f"   Response headers: {dict(response.headers)}")
            if response.status_code == 200:
                print("[OK] Server is reachable!")
                models_data = response.json()
                models = models_data.get("models", [])
                print(f"   Found {len(models)} available models:")
                for model in models:
                    model_name = model.get("name", "Unknown")
                    model_size = model.get("size", 0)
                    size_gb = model_size / (1024**3) if model_size > 0 else 0
                    print(f"   - {model_name} ({size_gb:.2f} GB)")
                print()
            else:
                print(f"[ERROR] Server returned status code: {response.status_code}")
                print(f"   Response text: {response.text[:500] if response.text else '(empty)'}")
                print(f"   Response headers: {dict(response.headers)}")
                # Try to get more info
                try:
                    error_json = response.json()
                    print(f"   Error JSON: {error_json}")
                except:
                    pass
                return False
        except httpx.TimeoutException:
            print("[ERROR] Connection timeout - server is not responding")
            return False
        except httpx.RequestError as e:
            print(f"[ERROR] Connection failed: {str(e)}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error: {str(e)}")
            return False
        
        # Test 2: Try to list models using /api/tags
        print("Test 2: Listing available models...")
        try:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                if models:
                    print(f"[OK] Found {len(models)} model(s):")
                    for model in models:
                        print(f"   - {model.get('name', 'Unknown')}")
                else:
                    print("[WARNING] No models found on the server")
                print()
            else:
                print(f"[ERROR] Failed to list models: {response.status_code}")
                print()
        except Exception as e:
            print(f"[ERROR] Error listing models: {str(e)}")
            print()
        
        # Test 3: Try a simple generation request (if models are available)
        if models:
            test_model = models[0].get("name")
            print(f"Test 3: Testing generation with model '{test_model}'...")
            try:
                payload = {
                    "model": test_model,
                    "prompt": "Say hello in one sentence.",
                    "stream": False
                }
                
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json=payload,
                    timeout=TIMEOUT
                )
                
                if response.status_code == 200:
                    result = response.json()
                    generated_text = result.get("response", "")
                    print("[OK] Generation successful!")
                    print(f"   Response: {generated_text[:200]}...")
                    print()
                    return True
                else:
                    print(f"[ERROR] Generation failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    print()
                    return False
            except httpx.TimeoutException:
                print("[ERROR] Generation request timed out")
                print()
                return False
            except Exception as e:
                print(f"[ERROR] Generation error: {str(e)}")
                print()
                return False
        else:
            print("Test 3: Skipped (no models available)")
            print()
            return True
    
    return True


async def main():
    """Main test function."""
    try:
        success = await test_ollama_connection()
        print("=" * 60)
        if success:
            print("[OK] All tests completed!")
        else:
            print("[ERROR] Some tests failed")
        print("=" * 60)
    except Exception as e:
        print(f"[ERROR] Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

