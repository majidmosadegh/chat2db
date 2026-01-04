#!/usr/bin/env python3
"""
Test script for database relationship sync
"""

import requests
import time

def test_sync():
    # Test the sync endpoint
    try:
        print("Calling sync endpoint...")
        response = requests.post('http://127.0.0.1:8000/api/relationships/sync-database-relationships/11', timeout=30)
        print(f'Status Code: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            print('Response:')
            print(f'  Message: {data.get("message")}')
            print(f'  Created relationships: {len(data.get("created_relationships", []))}')
            print(f'  Skipped relationships: {len(data.get("skipped_relationships", []))}')
            print(f'  Total foreign keys found: {data.get("total_foreign_keys_found", 0)}')

            if data.get('created_relationships'):
                print('Created relationships:')
                for rel in data['created_relationships']:
                    print(f'  - {rel["source_table"]}.{rel["source_column"]} -> {rel["target_table"]}.{rel["target_column"]}')

            if data.get('skipped_relationships'):
                print('Skipped relationships (already exist):')
                for rel in data['skipped_relationships']:
                    print(f'  - {rel}')
        else:
            print(f'Error response: {response.text}')
    except requests.exceptions.Timeout:
        print("Request timed out")
    except requests.exceptions.ConnectionError:
        print("Connection error")
    except Exception as e:
        print(f'Error calling API: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sync()


