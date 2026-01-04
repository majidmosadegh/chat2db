#!/usr/bin/env python3

import requests
import json

def test_chat():
    url = 'http://127.0.0.1:8001/api/chat-orchestrator/chat'
    headers = {'Content-Type': 'application/json'}
    data = {
        'message': 'Hello, can you help me with a simple SQL query?',
        'session_id': 'test_session_001',
        'snapshot_id': 1
    }

    print('Sending chat request...')
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        print(f'Status Code: {response.status_code}')
        if response.status_code == 200:
            result = response.json()
            print(f'Response: {result["response"]}')
            print(f'Intent: {result["intent_type"]}')
            print('SUCCESS: Chat functionality works!')
        else:
            print(f'Error response: {response.text}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    test_chat()












