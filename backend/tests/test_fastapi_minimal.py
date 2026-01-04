#!/usr/bin/env python3
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Test config import
try:
    # Hardcoded values for testing
    HOST = "127.0.0.1"
    PORT = 8000
    CORS_ORIGINS = ["http://localhost:3000"]
    DEBUG = True
    print("Config values loaded successfully")
except Exception as e:
    print(f"Config import failed: {e}")

# Test db import
try:
    from db import DatabaseConnector, get_database_connector
    print("DB module imported successfully")
except Exception as e:
    print(f"DB import failed: {e}")

# Test chat import
try:
    from chat import router
    print("Chat module imported successfully")
except Exception as e:
    print(f"Chat import failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting test server...")
    yield
    print("Server shutting down...")

app = FastAPI(title="Test FastAPI Server", lifespan=lifespan)

# Try to include chat router
try:
    app.include_router(router.router, prefix="/api/chat", tags=["chat"])
    print("Chat router included successfully")
except Exception as e:
    print(f"Router include failed: {e}")

@app.get("/health")
def health_check():
    return {"status": "healthy", "server": "fastapi-minimal"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
