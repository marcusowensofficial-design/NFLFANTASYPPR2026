@echo off
title FanDuel Live Showdown Tracker - SF @ LAR 2026
color 0B
cls
echo ======================================================================
echo    STARTING LIVE FANDUEL SHOWDOWN TRACKER (SF @ LAR)
echo    Connecting to ESPN live telemetry feed...
echo ======================================================================
echo.
cd /d "%~dp0"
python scripts\monitor_live_slate.py --watch
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Tracker exited with an error.
    pause
)
