@echo off
title Apex Fantasy Analytics Launcher
cd /d "%~dp0"

echo ======================================================================
echo    APEX FANTASY ANALYTICS - 2026 NFL SEASON LAUNCHER
echo ======================================================================
echo.

REM 1. Verify virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Python virtual environment not found. Setting up with uv...
    call uv sync
    if errorlevel 1 (
        echo [ERROR] Failed to set up Python environment with uv.
        pause
        exit /b 1
    )
)

REM 2. Verify frontend dependencies
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend packages...
    pushd frontend
    call npm install
    popd
)

REM Clean up any previously orphaned processes on ports 8000 and 5173
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM 3. Launch Backend in new window
echo [INFO] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "Apex Fantasy - Backend API (Port 8000)" cmd /c "scripts\run_backend.bat"

REM 4. Launch Frontend in new window
echo [INFO] Starting Vite Frontend on http://localhost:5173 ...
start "Apex Fantasy - Frontend UI (Port 5173)" cmd /c "scripts\run_frontend.bat"

REM 5. Wait for servers to initialize
echo [INFO] Waiting for servers to start...
ping 127.0.0.1 -n 5 >nul

REM 6. Open Browser
echo [INFO] Opening default browser to http://localhost:5173 ...
start "" "http://localhost:5173"

echo.
echo ======================================================================
echo    APEX FANTASY ANALYTICS IS RUNNING!
echo.
echo    - Web Dashboard:  http://localhost:5173
echo    - Backend API:    http://127.0.0.1:8000
echo    - API Docs:       http://127.0.0.1:8000/docs
echo.
echo    Two background windows have opened for the backend and frontend.
echo    Keep them open while using the app. Close them to stop the servers.
echo ======================================================================
echo.
pause
