@echo off
REM ===========================================
REM SQL PT - Unified Startup Script
REM ===========================================

echo.
echo ===========================================
echo    SQL PT - Starting Services
echo ===========================================
echo.

REM Kill existing processes on ports 8000 and 3000
echo [1/5] Cleaning up existing processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    if not "%%a"=="0" (
        taskkill /PID %%a /F >nul 2>&1
    )
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    if not "%%a"=="0" (
        taskkill /PID %%a /F >nul 2>&1
    )
)
echo    ✓ Ports cleared

REM Setup Backend
echo [2/5] Setting up Backend...
cd backend
if not exist venv (
    echo    Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
echo    Installing/updating dependencies...
pip install -q -r requirements.txt
echo    ✓ Backend ready

REM Start Backend
echo [3/5] Starting Backend Server (port 8000)...
start "SQL PT Backend" cmd /k "cd /d %cd% && venv\Scripts\activate && python main.py"
cd ..
timeout /t 3 /nobreak >nul
echo    ✓ Backend starting

REM Setup Frontend
echo [4/5] Setting up Frontend...
cd frontend
if not exist node_modules (
    echo    Installing dependencies...
    call npm install
)
echo    ✓ Frontend ready

REM Start Frontend
echo [5/5] Starting Frontend Server (port 3000)...
start "SQL PT Frontend" cmd /k "cd /d %cd% && npm run dev"
cd ..
echo    ✓ Frontend starting

REM Wait for services to start
echo.
echo ===========================================
echo    Waiting for services to start...
echo ===========================================
timeout /t 8 /nobreak >nul

REM Check service status
echo.
echo ===========================================
echo    Service Status
echo ===========================================
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
    echo    ✅ Backend:  RUNNING on http://localhost:8000
) else (
    echo    ⚠ Backend:  Starting... (check window)
)

netstat -ano | findstr :3000 >nul
if %errorlevel% equ 0 (
    echo    ✅ Frontend: RUNNING on http://localhost:3000
) else (
    echo    ⚠ Frontend: Starting... (check window)
)

echo.
echo ===========================================
echo    Service URLs
echo ===========================================
echo    📡 Backend API:  http://localhost:8000
echo    🌐 Frontend App: http://localhost:3000
echo    📚 API Docs:     http://localhost:8000/docs
echo ===========================================
echo.
echo    Services are running in separate windows.
echo    Close those windows to stop the services.
echo.
pause

