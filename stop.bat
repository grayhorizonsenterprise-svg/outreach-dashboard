@echo off
echo Stopping all Python processes...
taskkill /F /IM python.exe >nul 2>&1
echo Done. All processes stopped.
