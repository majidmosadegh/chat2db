from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "server": "test-server",
        "version": "1.0.0"
    }

@app.get("/test")
def test():
    return {"message": "Simple test works!"}
