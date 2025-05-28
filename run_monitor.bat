@echo off
REM SPA News Monitor - Windows Batch Script
REM This script runs the SPA News Monitor on Windows

echo SPA News Monitor
echo ==================

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher from https://python.org
    pause
    exit /b 1
)

REM Check if config file exists
if not exist "config.json" (
    echo Error: config.json not found
    echo Please run setup.py first to configure the monitor
    pause
    exit /b 1
)

REM Check if dependencies are installed
python -c "import requests, bs4, openai, apscheduler" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo Starting SPA News Monitor...
echo Press Ctrl+C to stop the monitor
echo.

REM Run the monitor
python main.py

echo.
echo Monitor stopped.
pause