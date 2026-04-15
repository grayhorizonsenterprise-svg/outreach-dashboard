@echo off
title Grant Agent System
cd /d "%~dp0"

echo.
echo  ================================================
echo   GRANT AGENT SYSTEM — Starting
echo  ================================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo  [!] .env file missing. Copy .env.example to .env and fill in your keys.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Start with watchdog (auto-restart on crash)
python watchdog.py

pause
