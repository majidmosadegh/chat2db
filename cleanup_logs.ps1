# ===========================================
# Cleanup Old Loguru Logs (PowerShell)
# Finds and removes old loguru logs from C: drive
# ===========================================

Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "   Cleanup Old Loguru Logs" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location -Path "backend"

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found! Please install Python first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Running cleanup script..." -ForegroundColor Yellow
Write-Host ""

python scripts/cleanup_old_logs.py --delete

Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "Cleanup complete!" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press Enter to exit"




