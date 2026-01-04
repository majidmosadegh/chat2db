#!/usr/bin/env python3
import requests
import json

# Test the chat endpoint (sync version for testing)
url = "http://127.0.0.1:8000/api/chat-orchestrator/chat"
headers = {"Content-Type": "application/json"}
data = {
    "message": "Hello, show me all tables",
    "session_id": "test_session",
    "snapshot_id": 1
}

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response: {response.text}")

    if response.status_code >= 400:
        print("\nError Details:")
        try:
            error_data = response.json()
            print(json.dumps(error_data, indent=2))
        except:
            print("Could not parse error response")

except Exception as e:
    print(f"Error: {e}")

# Also test health endpoint
try:
    health_response = requests.get("http://127.0.0.1:8000/health")
    print(f"\nHealth Check - Status: {health_response.status_code}, Response: {health_response.text}")
except Exception as e:
    print(f"Health check error: {e}")