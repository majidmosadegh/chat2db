#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('storage/metadata.db')
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables in database:')
for table in tables:
    print(f'  {table[0]}')

# Check LLM models
try:
    cursor.execute('SELECT COUNT(*) FROM llm_models')
    count = cursor.fetchone()[0]
    print(f'LLM models count: {count}')

    # Show some models
    cursor.execute('SELECT id, name, service_name, model_name, is_active FROM llm_models LIMIT 5')
    models = cursor.fetchall()
    print('Sample models:')
    for model in models:
        print(f'  {model}')
except Exception as e:
    print(f'Error querying llm_models: {e}')

conn.close()