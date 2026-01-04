#!/usr/bin/env python3
from fastapi import FastAPI

app = FastAPI(title="Minimal Test Server")

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Minimal server is working"}

@app.get("/test")
def test_endpoint():
    return {"data": "This is a test endpoint"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
