#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('storage/metadata.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables in database:')
for table in tables:
    print(f'- {table[0]}')

# Check LLM models if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_models'")
if cursor.fetchone():
    cursor.execute('SELECT id, name, service_name, is_active FROM llm_models')
    models = cursor.fetchall()
    print(f'\nFound {len(models)} LLM models:')
    for model in models:
        print(f'- ID: {model[0]}, Name: {model[1]}, Service: {model[2]}, Active: {model[3]}')
else:
    print('\nNo llm_models table found')

# Check data dictionary entries for EnergyExchange
cursor.execute("SELECT id, table_name, column_name, description, example_values, is_ai_generated FROM data_dictionary WHERE table_name='EnergyExchange' AND (column_name IS NULL OR column_name = '') ORDER BY id DESC LIMIT 5")
table_entries = cursor.fetchall()
print(f'\nTable-level data dictionary entries for EnergyExchange:')
for entry in table_entries:
    print(f'- ID: {entry[0]}, Table: {entry[1]}, Column: {entry[2]}, AI Generated: {entry[5]}')
    print(f'  Description: {entry[3][:100]}...' if entry[3] else '  Description: None')
    print(f'  Example values: {repr(entry[4])}')

cursor.execute("SELECT COUNT(*) FROM data_dictionary WHERE table_name='EnergyExchange'")
count = cursor.fetchone()[0]
print(f'\nTotal data dictionary entries for EnergyExchange: {count}')

# Check for invalid JSON in example_values
cursor.execute("SELECT id, example_values FROM data_dictionary WHERE example_values IS NOT NULL AND example_values != '' LIMIT 20")
examples = cursor.fetchall()
print(f'\nChecking example_values JSON validity:')
import json
for entry_id, example_val in examples:
    try:
        json.loads(example_val)
        print(f'ID {entry_id}: VALID')
    except json.JSONDecodeError as e:
        print(f'ID {entry_id}: INVALID - {e} - Value: {repr(example_val)}')

conn.close()
