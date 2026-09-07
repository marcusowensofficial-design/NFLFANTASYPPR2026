# Apex Fantasy Analytics - PowerShell Launcher
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ProjectRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   APEX FANTASY ANALYTICS - 2026 NFL SEASON LAUNCHER" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python virtual environment
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[INFO] Initializing Python virtual environment with uv..." -ForegroundColor Yellow
    & uv sync
}

# 2. Check frontend dependencies
$FrontendModules = Join-Path $ProjectRoot "frontend\node_modules"
if (-not (Test-Path $FrontendModules)) {
    Write-Host "[INFO] Installing frontend npm packages..." -ForegroundColor Yellow
    Push-Location (Join-Path $ProjectRoot "frontend")
    & npm install
    Pop-Location
}

# Clean up any previously orphaned processes on ports 8000 and 5173
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

# 3. Start Backend in separate window
Write-Host "[INFO] Starting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$ProjectRoot\scripts\run_backend.bat`""

# 4. Start Frontend in separate window
Write-Host "[INFO] Starting Vite Frontend on http://localhost:5173 ..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$ProjectRoot\scripts\run_frontend.bat`""

# 5. Wait for servers
Write-Host "[INFO] Initializing servers (waiting 4 seconds)..." -ForegroundColor Gray
Start-Sleep -Seconds 4

# 6. Launch browser
Write-Host "[INFO] Opening browser to http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   APEX FANTASY ANALYTICS IS RUNNING!" -ForegroundColor Green
Write-Host "   - Dashboard: http://localhost:5173"
Write-Host "   - API:       http://127.0.0.1:8000/docs"
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Press any key to close this launcher window..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
