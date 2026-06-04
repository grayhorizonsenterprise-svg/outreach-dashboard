@echo off

REM Ensure correct directory
cd /d "C:\Users\curti\Downloads\First Agentic Workflows"

REM Run full pipeline
python run_all_engines.py >> run_log.txt 2>&1

REM Log completion
echo %date% %time% - Pipeline executed >> run_log.txt

REM Exit cleanly
exit
