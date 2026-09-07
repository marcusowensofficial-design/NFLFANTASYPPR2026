@echo off
title Apex Fantasy Frontend (Port 5173)
cd /d "%~dp0..\frontend"

echo ======================================================================
echo    APEX FANTASY FRONTEND (VITE + REACT)
echo ======================================================================
echo Directory: %CD%
echo.

if not exist "node_modules" (
    echo [INFO] Installing node_modules...
    call npm install
)

echo [INFO] Starting Vite dev server on http://localhost:5173 ...
call npm run dev

echo.
echo [INFO] Frontend server stopped.
pause
