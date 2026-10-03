@echo off
setlocal
cd /d "%~dp0"
title PC Monitor Server (Admin)

set "PYTHON_EXE=C:\ProgramData\miniconda3\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Administrator privilege confirmed. Starting server...
    "%PYTHON_EXE%" "%~dp0pc_demo_server.py"
) else (
    echo [INFO] Requesting Administrator elevation...
    powershell -NoProfile -Command "Start-Process '%PYTHON_EXE%' -ArgumentList '\"%~dp0pc_demo_server.py\"' -WorkingDirectory '\"%~dp0\"' -Verb RunAs"
)
