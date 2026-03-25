@echo off
echo Stopping any running Python processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Starting GHE Outreach System...
start "" /MIN C:\Python314\python.exe "c:\Users\curti\Downloads\First Agentic Workflows\approval_dashboard.py"

timeout /t 5 /nobreak >nul

echo Starting Watchdog...
start "" /MIN C:\Python314\python.exe "c:\Users\curti\Downloads\First Agentic Workflows\watchdog.py"

timeout /t 3 /nobreak >nul
echo.
echo System running. Opening dashboard...
start "" http://127.0.0.1:8080
