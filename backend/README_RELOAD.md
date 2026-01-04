# Backend Reload Configuration

## Problem Solved
The backend was constantly restarting due to uvicorn's file watching detecting changes in:
- Log files (*.log)
- Compiled Python bytecode (*.pyc) - 1553+ files
- Cache directories (__pycache__)

## Current Configuration
```python
uvicorn.run(
    "main:app",
    host=HOST,
    port=PORT,
    reload=False,  # Disabled to prevent constant restarts
    log_level="info"
)
```

## For Development with Reload
If you need hot reload during development, use this configuration:

```python
uvicorn.run(
    "main:app",
    host=HOST,
    port=PORT,
    reload=True,
    reload_dirs=["api", "core", "services", "chat", "db", "utils"],  # Only code dirs
    reload_excludes=["*.log", "*.pyc", "__pycache__", "*.tmp", "*.temp"],
    log_level="info"
)
```

## Manual Restart
When reload is disabled, restart the server manually after code changes:
```bash
# Kill existing process
taskkill /IM python.exe /F /T

# Start server
cd backend
python main.py
```
