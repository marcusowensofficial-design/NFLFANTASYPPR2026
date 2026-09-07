@echo off
title ESPN Fantasy Connection Test
cd /d "%~dp0"

echo ======================================================================
echo    ESPN FANTASY FOOTBALL 2026 - CONNECTION TEST
echo ======================================================================
echo.

if not exist ".env" (
    echo [WARNING] No .env file found!
    echo Running with --mock sample league fixture...
    echo.
    .venv\Scripts\python scripts\test_espn_connection.py --mock
) else (
    echo Running connection test using your .env configuration...
    echo.
    .venv\Scripts\python scripts\test_espn_connection.py %*
)

echo.
echo ======================================================================
pause
