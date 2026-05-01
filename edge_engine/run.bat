@echo off
title Edge Engine Daily Scan
echo ============================================================
echo  EDGE ENGINE — Stocks + Crypto + Sports/Politics Bets
echo ============================================================
echo.

REM Install deps silently
pip install -q yfinance pandas numpy requests python-dotenv robin_stocks pyotp 2>nul

REM Copy .env template if .env doesn't exist yet
if not exist .env (
    copy .env.template .env >nul
    echo [!] Created .env — open it and add your API keys before re-running.
    echo     Required: NTFY_TOPIC (phone alerts)
    echo     Optional: ODDS_API_KEY, QUIVERQUANT_KEY, RH_USERNAME/PASSWORD
    echo.
    notepad .env
    exit /b
)

echo Running daily scan...
echo.
python scan.py

echo.
echo ============================================================
echo  Done. Check your phone for alerts.
echo  Report saved to report_YYYYMMDD.txt
echo ============================================================
pause
