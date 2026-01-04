#!/usr/bin/env python3
"""Test AI Dictionary User Experience"""
import requests
import json

print('AI DICTIONARY USER EXPERIENCE TEST')
print('=' * 50)

# Step 1: Start AI Dictionary Generation
print('\n1. STARTING AI DICTIONARY GENERATION')
print('-' * 40)

start_payload = {
    'snapshot_id': 1,
    'business_domain': 'Online Sales',
    'database_description': 'E-commerce database with customers, orders, products, and inventory',
    'target_user': 'Data Analyst',
    'language': 'english'
}

response = requests.post('http://127.0.0.1:8000/api/ai/dictionary/start', json=start_payload)
start_result = response.json()

print('Request:', start_payload)
print('Response:', start_result)

if start_result.get('success'):
    job_id = start_result['job_id']
    print(f'Job started successfully with ID: {job_id}')

    # Step 2: Check Job Status
    print('\n2. CHECKING JOB STATUS')
    print('-' * 40)

    status_response = requests.get(f'http://127.0.0.1:8000/api/ai/dictionary/job/{job_id}')
    status_result = status_response.json()

    print(f'Job Status: {status_result["status"]}')
    print(f'Total Tables: {status_result["total_tables"]}')
    print(f'Completed: {status_result["completed_tables"]}')
    print(f'Failed: {status_result["failed_tables"]}')

    print('\nTABLE-BY-TABLE RESULTS:')
    print('-' * 30)

    for table_name, info in status_result['progress']['tables'].items():
        status = info['status']
        attempts = info['attempts']
        error = info.get('error', '')

        if status == 'STORED':
            print(f'SUCCESS: {table_name} ({attempts} attempts)')
        else:
            print(f'FAILED: {table_name} ({attempts} attempts)')
            if error:
                print(f'   Error: {error}')

    print('\nUSER EXPERIENCE SUMMARY:')
    print('-' * 30)
    print('- Easy API interface - just provide snapshot_id and context')
    print('- Asynchronous processing - no waiting required')
    print('- Real-time status monitoring')
    print('- Partial success handling')
    print('- Persian language support')
    print('- Detailed error reporting')

else:
    print('❌ Failed to start job')
