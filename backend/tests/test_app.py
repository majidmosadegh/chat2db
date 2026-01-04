#!/usr/bin/env python3

from main import app
import asyncio

async def test_app():
    print('FastAPI app created successfully')
    print(f'Total routes registered: {len(app.routes)}')

    use_case_routes = [route for route in app.routes if hasattr(route, "path") and "use-cases" in route.path]
    print(f'Use case routes: {len(use_case_routes)}')
    for route in use_case_routes:
        print(f'  - {route.path} ({route.methods})')

    smart_routes = [route for route in app.routes if hasattr(route, "path") and "smart-use-case-builder" in route.path]
    print(f'Smart use case builder routes: {len(smart_routes)}')
    for route in smart_routes:
        print(f'  - {route.path} ({route.methods})')

    print('\nTesting health endpoint...')
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.get("/health")
    print(f'Health check status: {response.status_code}')
    print(f'Health check response: {response.json()}')

if __name__ == "__main__":
    asyncio.run(test_app())