@echo off
setlocal
cd /d "%~dp0"
title PC Monitor Server (Admin)

set "PYTHON_EXE=C:\ProgramData\miniconda3\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

:: Request Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Requesting Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo [OK] Administrator privilege confirmed. Starting server...
"%PYTHON_EXE%" "%~dp0pc_demo_server.py"
pause
