#!/usr/bin/env python3
from fastapi import FastAPI

app = FastAPI()

@app.post("/test")
def test_endpoint():
    return {"message": "Simple endpoint works!"}

@app.post("/api/chat/chat/execute")
def chat_execute():
    return {
        "success": True,
        "question": "Test",
        "sql": "SELECT TOP 5 * FROM EnergyExchange",
        "rows": [{"id": 1, "name": "Test User"}],
        "row_count": 1,
        "snapshot_id": 11,
        "model_used": "model_4",
        "execution_status": "success"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
