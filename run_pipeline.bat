@echo off
cd /d "%~dp0"

mkdir clips\raw    2>nul
mkdir clips\output 2>nul
mkdir clips\posted 2>nul
mkdir clips\audio  2>nul

echo STEP 1: DOWNLOAD + FILTER CLIPS
python viral_system.py

echo STEP 2: GENERATE METADATA
python metadata_engine.py

echo STEP 3: RENDER CLIPS
call auto_render.bat

echo DONE
pause
