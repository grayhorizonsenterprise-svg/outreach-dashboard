@echo off

REM Ensure correct directory
cd /d "C:\Users\curti\Downloads\First Agentic Workflows"

REM Activate environment if needed (optional)
REM call venv\Scripts\activate

REM Run full pipeline
python run_pipeline.py

REM Optional: log output (recommended)
echo %date% %time% - Pipeline executed >> run_log.txt

REM Exit cleanly
exit