@echo off
REM ============================================================
REM  Grant Agent — Windows Auto-Start via Task Scheduler
REM  Run this ONCE as Administrator to register the startup task
REM ============================================================

echo.
echo  Registering Grant Agent as a Windows startup task...
echo.

set TASK_NAME=GrantAgentSystem
set SCRIPT_PATH=%~dp0start.bat
set PYTHON_PATH=python

REM Delete old task if exists
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Create new task: runs at logon, in background
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%SCRIPT_PATH%\"" ^
  /sc ONLOGON ^
  /rl HIGHEST ^
  /f

if %errorlevel% == 0 (
    echo.
    echo  [OK] Grant Agent will now start automatically at login.
    echo  Task name: %TASK_NAME%
    echo.
    echo  To remove auto-start: schtasks /delete /tn %TASK_NAME% /f
) else (
    echo.
    echo  [!] Failed to create task. Try running this as Administrator.
)

pause
