@echo off
setlocal
cd /d "%~dp0"
title ETF Monitor
echo ========================================
echo   Starting ETF Realtime Monitor
echo ========================================
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo An error occurred. Please check execution.log for details.
    pause
)
echo.
echo Program finished.
pause
endlocal
