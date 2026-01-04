#!/usr/bin/env python3

try:
    from fastapi import FastAPI
    print('✓ FastAPI imported successfully')

    app = FastAPI()
    print('✓ FastAPI app created successfully')

    @app.get('/test')
    def test():
        return {'message': 'test'}

    print('✓ Route added successfully')
    print('SUCCESS: FastAPI works fine')

except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()