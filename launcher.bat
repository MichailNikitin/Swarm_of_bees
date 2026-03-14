@echo off
title Bee Swarm Simulator

echo ============================================
echo  Bee Swarm Simulator - Launcher
echo ============================================
echo.

REM Prefer py -3.10 (Python Launcher); fall back to plain python
set PYTHON_CMD=
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.10
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=python
    ) else (
        echo [ERROR] Python not found. Please install Python 3.10+
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%v in ('%PYTHON_CMD% --version 2^>^&1') do echo [INFO] Using %%v
echo.

REM Install dependencies using the same Python's pip (proxy bypass)
echo [INFO] Checking / installing dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt --proxy "" --quiet
if errorlevel 1 (
    echo [WARN] pip install failed - attempting without proxy flag...
    %PYTHON_CMD% -m pip install -r requirements.txt --quiet
)

echo [INFO] Starting server at http://localhost:8000
echo [INFO] Press Ctrl+C to stop.
echo.

REM Open browser after a short delay
start "" /b cmd /c "timeout /t 2 >nul && start http://localhost:8000"

REM Run uvicorn from backend directory
cd backend
%PYTHON_CMD% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
