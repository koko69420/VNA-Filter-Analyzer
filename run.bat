@echo off
rem ==============================================================================
rem Rohde & Schwarz VNA Filter Analyzer - Windows Launcher
rem ==============================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo Please install Python 3.10 or newer from https://www.python.org/
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [INFO] First time setup: creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [INFO] Installing required dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo [INFO] Launching Rohde ^& Schwarz VNA Filter Analyzer...
python main.py %*
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Application exited with an error.
    pause
)
