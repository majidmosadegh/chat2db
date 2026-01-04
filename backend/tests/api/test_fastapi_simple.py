#!/usr/bin/env python3

from fastapi import FastAPI

app = FastAPI()

@app.get("/test")
def test_endpoint():
    return {"message": "FastAPI simple test works"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)










