#!/usr/bin/env python3

# Test Pydantic serialization
from api.chat_orchestrator.router import ChatResponse

# Test the exact response from our test
response_data = {
    'session_id': 'test_session_full',
    'response': 'No active database snapshot found. Please configure a database connection first.',
    'intent_type': 'error',
    'execution_result': None,
    'context_info': {
        'session_id': 'test_session_full',
        'active_snapshot_id': None,
        'active_use_case_id': None,
        'conversation_memory': [
            {
                'type': 'user',
                'content': 'Hello',
                'metadata': {},
                'timestamp': '2025-12-19T19:24:32.277556'
            },
            {
                'type': 'assistant',
                'content': 'No active database snapshot found. Please configure a database connection first.',
                'metadata': {},
                'timestamp': '2025-12-19T19:24:32.316081'
            }
        ],
        'execution_history': [],
        'feedback_history': []
    },
    'suggestions': None
}

try:
    print("Testing Pydantic serialization...")
    response = ChatResponse(**response_data)
    print("SUCCESS: Pydantic model created")

    # Test JSON serialization
    json_str = response.model_dump_json()
    print("SUCCESS: JSON serialization works")
    print(f"Length: {len(json_str)}")

    print("SUCCESS: All Pydantic tests passed")

except Exception as e:
    print(f"ERROR: Pydantic failed: {e}")
    import traceback
    traceback.print_exc()