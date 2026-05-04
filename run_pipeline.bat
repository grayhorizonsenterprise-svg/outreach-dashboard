@echo off
cd /d "%~dp0"

echo STEP 1: DOWNLOAD + FILTER CLIPS
python viral_system.py

echo STEP 2: OPTIONAL CLEANUP (filter again if needed)
python metadata_engine.py

echo STEP 3: RENDER CLIPS
call auto_render.bat

echo DONE
pause
