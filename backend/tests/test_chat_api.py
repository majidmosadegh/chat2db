#!/usr/bin/env python3
import requests
import json

def test_chat_api():
    url = "http://localhost:8000/api/chat/chat/execute"

    # Test data
    payload = {
        "snapshot_id": 11,
        "model_id": 4,
        "language": "en",
        "question": "Show me all users"
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        print("Sending request to:", url)
        print("Payload:", json.dumps(payload, indent=2))

        response = requests.post(url, json=payload, headers=headers)

        print("Status Code:", response.status_code)
        print("Response:", response.text)

        if response.status_code == 200:
            data = response.json()
            print("Success! Response data:")
            print(json.dumps(data, indent=2))
        else:
            print("Error response")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chat_api()
