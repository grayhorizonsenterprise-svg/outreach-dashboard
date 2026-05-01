@echo off
REM Run once to register auto-daily scan at 9:00 AM
set DIR=%~dp0
schtasks /create /tn "EdgeEngineDailyScan" ^
  /tr "cmd /c cd /d \"%DIR%\" && python scan.py >> scan_log.txt 2>&1" ^
  /sc daily /st 09:00 /f
echo Registered. Scan runs daily at 9:00 AM automatically.
pause
