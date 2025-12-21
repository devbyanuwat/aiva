@echo off
chcp 65001 >nul
title AIVA Server

echo ==================================================
echo          AIVA Server Launcher
echo ==================================================
echo.

cd /d "%~dp0"
echo Working directory: %cd%
echo.

REM ตรวจสอบ Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

REM ติดตั้ง dependencies
echo [1] Checking dependencies...
python -c "import flask" 2>nul || (
    echo [WARN] Installing dependencies...
    pip install -r requirements.txt
)

REM รัน Server
echo [2] Starting AIVA Server on http://0.0.0.0:5002
echo.

start "" http://127.0.0.1:5002
timeout /t 3 /nobreak >nul

echo ==================================================
echo   Server: http://127.0.0.1:5002
echo   Press Ctrl+C to stop
echo ==================================================
echo.

python app.py
pause
