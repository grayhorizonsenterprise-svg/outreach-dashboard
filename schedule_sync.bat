@echo off
REM schedule_sync.bat — runs sync_to_railway.py daily
REM To install: run this file once as Administrator
REM After that, your machine auto-syncs leads to Railway every morning at 6am

set SCRIPT_DIR=%~dp0
set PYTHON=C:\Python314\python.exe
set SCRIPT=%SCRIPT_DIR%sync_to_railway.py

REM Create the scheduled task
schtasks /create /tn "GHE Daily Sync" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc daily /st 06:00 /f

echo.
echo Scheduled task created: GHE Daily Sync
echo Runs every morning at 6:00 AM
echo Your leads will sync to Railway automatically.
echo.
pause
