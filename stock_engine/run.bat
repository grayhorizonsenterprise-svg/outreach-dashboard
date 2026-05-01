@echo off
echo Installing dependencies...
pip install -q yfinance pandas pandas_ta numpy requests robin_stocks pyotp python-dotenv 2>nul

echo.
echo Loading .env...
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%A in (.env) do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)

echo Running master scan (technical + congress + social + Robinhood check)...
python master_scan.py

pause
