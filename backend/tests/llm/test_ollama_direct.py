"""
Direct test using requests library
"""

import requests
import json

url = "http://37.255.205.140:11435"

print("=" * 60)
print("Direct Ollama Connection Test")
print("=" * 60)
print(f"URL: {url}")
print()

# Test 1: Simple GET request
print("Test 1: GET /api/tags")
try:
    response = requests.get(
        f"{url}/api/tags",
        timeout=30,
        headers={"User-Agent": "Python-Test"},
        proxies={"http": None, "https": None}  # Disable proxy
    )
    print(f"   Status Code: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        models = data.get("models", [])
        print(f"   [SUCCESS] Found {len(models)} models:")
        for m in models:
            name = m.get("name", "Unknown")
            size = m.get("size", 0)
            size_gb = size / (1024**3) if size > 0 else 0
            print(f"      - {name} ({size_gb:.2f} GB)")
        print()
        
        # Test 2: Try generation
        if models:
            test_model = models[0].get("name")
            print(f"Test 2: POST /api/generate with model '{test_model}'")
            try:
                payload = {
                    "model": test_model,
                    "prompt": "Say hello in Persian.",
                    "stream": False
                }
                gen_response = requests.post(
                    f"{url}/api/generate",
                    json=payload,
                    timeout=60,
                    headers={"Content-Type": "application/json"},
                    proxies={"http": None, "https": None}  # Disable proxy
                )
                print(f"   Status Code: {gen_response.status_code}")
                if gen_response.status_code == 200:
                    result = gen_response.json()
                    text = result.get("response", "")
                    print(f"   [SUCCESS] Generated text: {text[:200]}...")
                    print()
                    print("=" * 60)
                    print("[SUCCESS] All tests passed!")
                    print("=" * 60)
                else:
                    print(f"   [ERROR] Response: {gen_response.text[:500]}")
            except Exception as e:
                print(f"   [ERROR] {type(e).__name__}: {e}")
    else:
        print(f"   [ERROR] Response body: {response.text[:500]}")
        print(f"   [ERROR] Full response: {response.content[:200]}")
        
except requests.exceptions.ConnectionError as e:
    print(f"   [ERROR] Connection Error: {e}")
    print("   This usually means the server is unreachable")
except requests.exceptions.Timeout:
    print(f"   [ERROR] Request timed out")
except requests.exceptions.RequestException as e:
    print(f"   [ERROR] Request Exception: {type(e).__name__}: {e}")
except Exception as e:
    print(f"   [ERROR] Unexpected error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print()

