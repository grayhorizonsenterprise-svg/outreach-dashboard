@echo off
echo Stopping any running Python processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Starting pipeline...
start "Pipeline" /MIN C:\Python314\python.exe run_pipeline.py

timeout /t 5 /nobreak >nul

echo Starting dashboard...
start "Dashboard" C:\Python314\python.exe approval_dashboard.py

timeout /t 3 /nobreak >nul
echo.
echo System is running.
echo Dashboard: http://127.0.0.1:8080
echo.
start "" http://127.0.0.1:8080
