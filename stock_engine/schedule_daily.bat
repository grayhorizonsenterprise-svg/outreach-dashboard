@echo off
REM Run this once to register the daily scan in Windows Task Scheduler.
REM It will run master_scan.py every day at 9:00 AM (market open).

set SCRIPT_DIR=%~dp0
set PYTHON_PATH=python

echo Registering daily stock scan in Task Scheduler...

schtasks /create /tn "StockEngineDailyScan" ^
  /tr "%PYTHON_PATH% \"%SCRIPT_DIR%master_scan.py\"" ^
  /sc daily /st 09:00 ^
  /f

echo.
echo Done. Scan will run every day at 9:00 AM.
echo To view: Task Scheduler > Task Scheduler Library > StockEngineDailyScan
echo To remove: schtasks /delete /tn "StockEngineDailyScan" /f
pause
