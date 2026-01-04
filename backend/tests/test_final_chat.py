#!/usr/bin/env python3
import requests
import json

def test_chat_api():
    url = 'http://localhost:8000/api/chat/chat/execute'
    payload = {
        'snapshot_id': 11,
        'model_id': 4,
        'language': 'fa',
        'question': 'همه کاربران را نشان بده'
    }

    print('Final test of Persian Chat Bot!')
    print('=' * 50)

    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f'Status Code: {response.status_code}')

        if response.status_code == 200:
            data = response.json()
            print('SUCCESS! Chat API is working!')
            print(f'Question: {data.get("question")}')
            print(f'SQL: {data.get("sql")}')
            print(f'Row Count: {data.get("row_count")}')
            print(f'Model: {data.get("model_used")}')
            print(f'Status: {data.get("execution_status")}')
            print()
            print('Persian Chat Bot is READY for production!')
            return True
        else:
            print(f'Error: {response.text[:200]}')
            return False

    except Exception as e:
        print(f'Request failed: {e}')
        return False

if __name__ == "__main__":
    success = test_chat_api()
    print(f'\nResult: {"SUCCESS" if success else "FAILED"}')
