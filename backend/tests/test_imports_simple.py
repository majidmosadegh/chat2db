#!/usr/bin/env python3
"""Simple test script to check imports"""

print("Testing imports...")

try:
    from services.ai_dictionary_types import TableGenerationResult
    print("ai_dictionary_types imported successfully")
except Exception as e:
    print(f"ai_dictionary_types failed: {e}")

try:
    from services.ai_dictionary_service import AIDictionaryGenerationService
    print("AIDictionaryGenerationService imported successfully")
    # Try to create instance
    service = AIDictionaryGenerationService()
    print("Service instance created successfully")
except Exception as e:
    print(f"ai_dictionary_service failed: {e}")

try:
    from api.ai_dictionary import router
    print("ai_dictionary router imported successfully")
except Exception as e:
    print(f"ai_dictionary router failed: {e}")

print("Done!")