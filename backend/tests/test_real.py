import requests
import json
import sys
import io

# Set console encoding to handle Persian text
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

url = 'http://localhost:8000/api/data-dictionary/ai-generate'
data = {
    'snapshot_id': 1,
    'business_domain': 'Stock Market',
    'database_description': 'Database for energy and commodity trading',
    'target_user': 'Financial analysts',
    'language': 'english',
    'additional_notes': 'Trading data for energy and commodities'
}

print('Sending request to generate AI dictionary...')
print('URL:', url)
json_data = json.dumps(data, ensure_ascii=False)
print('JSON data:', json_data)
try:
    response = requests.post(url, data=json_data, headers={'Content-Type': 'application/json'}, timeout=60)
    print('Status Code:', response.status_code)
    print('Response headers:', dict(response.headers))
    if response.status_code == 200:
        result = response.json()
        print('Success! Job ID:', result.get('job_id'))
    else:
        print('Error:', response.text)
        print('Response content:', response.content)
except requests.exceptions.RequestException as e:
    print('Request failed:', str(e))
except Exception as e:
    print('Other error:', str(e))
