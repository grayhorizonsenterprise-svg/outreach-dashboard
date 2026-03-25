@echo off
echo Stopping any running Python processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Starting Gray Horizons Outreach System...
start "" /MIN C:\Python314\python.exe "c:\Users\curti\Downloads\First Agentic Workflows\approval_dashboard.py"

timeout /t 4 /nobreak >nul
echo System is running.
echo Dashboard: http://127.0.0.1:8080
start "" http://127.0.0.1:8080
