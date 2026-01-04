@echo off
REM ===========================================
REM Cleanup Old Loguru Logs
REM Finds and removes old loguru logs from C: drive
REM ===========================================

echo.
echo ===========================================
echo    Cleanup Old Loguru Logs
echo ===========================================
echo.

cd backend

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python first.
    pause
    exit /b 1
)

echo Running cleanup script...
echo.
python scripts/cleanup_old_logs.py --delete

echo.
echo ===========================================
echo Cleanup complete!
echo ===========================================
echo.
pause




