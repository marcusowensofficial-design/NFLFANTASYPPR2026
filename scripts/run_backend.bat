@echo off
title Apex Fantasy Backend (Port 8000)
cd /d "%~dp0.."

echo ======================================================================
echo    APEX FANTASY BACKEND (FASTAPI)
echo ======================================================================
echo Directory: %CD%
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found in .venv!
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
REM Free port 8000 if occupied by an orphaned uvicorn process
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [INFO] Python active. Launching Uvicorn server on http://127.0.0.1:8000 ...
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

echo.
echo [INFO] Server stopped.
pause
