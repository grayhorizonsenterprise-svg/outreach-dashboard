@echo off
title Edge Engine Dashboard
color 0A
cls

echo.
echo  ============================================================
echo   GRAY HORIZONS -- EDGE ENGINE DASHBOARD
echo  ============================================================
echo.
echo  Starting server...
echo  Browser will open automatically in 5 seconds.
echo  If it does not open, go to: http://localhost:5050
echo.
echo  Press Ctrl+C to stop the server.
echo  ============================================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python not found.
    echo  Install Python from python.org and check "Add to PATH"
    echo.
    pause
    exit /b 1
)

start "" "http://localhost:5050"

python dashboard.py

if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Dashboard failed to start. See message above.
    echo.
)
pause
