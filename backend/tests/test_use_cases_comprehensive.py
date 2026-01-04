#!/usr/bin/env python3

import asyncio
import json
from fastapi.testclient import TestClient
from main import app
from api.db_models import create_tables, get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

async def test_use_cases_workflow():
    """Comprehensive test for the use cases module"""
    print('Running comprehensive use cases workflow test...')

    # Create test client
    client = TestClient(app)

    # Create tables
    print('Setting up database...')
    await create_tables()

    try:
        # Test 1: Health check
        print('\n1. Testing health check...')
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
        print('[OK] Health check passed')

        # Test 2: Get use cases (should be empty initially)
        print('\n2. Testing get use cases (initially empty)...')
        response = client.get("/api/use-cases/")
        assert response.status_code == 200
        assert response.json() == []
        print('[OK] Get use cases returned empty list as expected')

        # Test 3: Create a use case
        print('\n3. Testing create use case...')
        use_case_data = {
            "name": "Sales Performance Analysis",
            "business_goal": "Analyze sales performance across different products and time periods",
            "example_questions": ["What are the top selling products?", "How much revenue did we generate last month?"],
            "output_style": "analytical",
            "is_ai_generated": False,
            "business_context": "Retail sales management",
            "primary_audience": ["manager", "analyst"],
            "typical_questions_wizard": ["numeric_stats", "comparative"],
            "output_preference": "summary_table"
        }

        response = client.post("/api/use-cases/", json=use_case_data)
        assert response.status_code == 200
        created_use_case = response.json()
        assert created_use_case["name"] == use_case_data["name"]
        assert created_use_case["business_goal"] == use_case_data["business_goal"]
        assert created_use_case["output_style"] == use_case_data["output_style"]
        print('[OK] Use case created successfully')

        use_case_id = created_use_case["id"]

        # Test 4: Get specific use case
        print('\n4. Testing get specific use case...')
        response = client.get(f"/api/use-cases/{use_case_id}")
        assert response.status_code == 200
        retrieved_use_case = response.json()
        assert retrieved_use_case["id"] == use_case_id
        assert retrieved_use_case["name"] == use_case_data["name"]
        print('[OK] Get specific use case worked')

        # Test 5: Get all use cases (should have one now)
        print('\n5. Testing get all use cases...')
        response = client.get("/api/use-cases/")
        assert response.status_code == 200
        use_cases = response.json()
        assert len(use_cases) == 1
        assert use_cases[0]["id"] == use_case_id
        print('[OK] Get all use cases returned the created use case')

        # Test 6: Update use case
        print('\n6. Testing update use case...')
        updated_data = use_case_data.copy()
        updated_data["name"] = "Updated Sales Performance Analysis"
        updated_data["business_goal"] = "Updated business goal"

        response = client.put(f"/api/use-cases/{use_case_id}", json=updated_data)
        assert response.status_code == 200
        updated_use_case = response.json()
        assert updated_use_case["name"] == "Updated Sales Performance Analysis"
        assert updated_use_case["business_goal"] == "Updated business goal"
        print('[OK] Use case updated successfully')

        # Test 7: Test validation - duplicate name
        print('\n7. Testing validation - duplicate name...')
        duplicate_data = use_case_data.copy()
        duplicate_data["name"] = "Updated Sales Performance Analysis"  # Same name as updated

        response = client.post("/api/use-cases/", json=duplicate_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
        print('[OK] Duplicate name validation worked')

        # Test 8: Test validation - invalid output style
        print('\n8. Testing validation - invalid output style...')
        invalid_data = use_case_data.copy()
        invalid_data["name"] = "Another Use Case"
        invalid_data["output_style"] = "invalid_style"

        response = client.post("/api/use-cases/", json=invalid_data)
        assert response.status_code == 400
        assert "Invalid output style" in response.json()["detail"]
        print('[OK] Invalid output style validation worked')

        # Test 9: Delete use case
        print('\n9. Testing delete use case...')
        response = client.delete(f"/api/use-cases/{use_case_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Use case deleted successfully"
        print('[OK] Use case deleted successfully')

        # Test 10: Verify deletion
        print('\n10. Testing verify deletion...')
        response = client.get(f"/api/use-cases/{use_case_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        print('[OK] Use case properly deleted')

        # Test 11: Get all use cases (should be empty again)
        print('\n11. Testing get all use cases after deletion...')
        response = client.get("/api/use-cases/")
        assert response.status_code == 200
        assert response.json() == []
        print('[OK] Use cases list is empty after deletion')

        # Clean up test data
        print('\nCleaning up test data...')
        async for session in get_db_session():
            try:
                await session.execute(delete(await session.get_bind().table('use_cases')))
                await session.commit()
                print('[OK] Test data cleaned up')
                break
            except Exception as e:
                print(f'[WARNING] Could not clean up test data: {e}')
                break

        print('\n[OK] All use case workflow tests passed!')
        return True

    except Exception as e:
        print(f'\n[ERROR] Test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_use_cases_workflow())
    if success:
        print('\n🎉 All comprehensive tests passed!')
    else:
        print('\n❌ Some tests failed!')
        exit(1)