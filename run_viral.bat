@echo off
cd /d "C:\Users\curti\Downloads\First Agentic Workflows"
echo.
echo =======================================
echo  VIRAL VIDEO ENGINE - GRAY HORIZONS
echo =======================================
echo.

REM Install dependencies if needed
pip install -r requirements_viral.txt --quiet

REM Run the engine
python viral_system.py

echo.
echo Done. Check D:\viral_clips\READY_TO_UPLOAD
pause
