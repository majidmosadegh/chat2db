@echo off
REM ===========================================
REM Find Old Loguru Logs
REM Shows where old loguru logs are located (dry run)
REM ===========================================

echo.
echo ===========================================
echo    Finding Old Loguru Logs
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

echo Running find script (dry run - no files will be deleted)...
echo.
python scripts/cleanup_old_logs.py

echo.
pause




