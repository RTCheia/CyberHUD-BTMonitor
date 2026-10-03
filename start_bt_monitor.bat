@echo off
setlocal
cd /d "%~dp0"
title PC Monitor - Bluetooth Streamer

set "PYTHON_EXE=C:\ProgramData\miniconda3\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

REM Elevate directly via python.exe if not already administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -NoProfile -Command "Start-Process '%PYTHON_EXE%' -ArgumentList '\"%~dp0pc_sender\bt_monitor_sender.py\"' -WorkingDirectory '\"%~dp0\"' -Verb RunAs"
    exit /b
)

echo =================================================================
echo       PC Monitor - Bluetooth Realtime Telemetry Streamer
echo =================================================================

"%PYTHON_EXE%" "%~dp0pc_sender\bt_monitor_sender.py"
pause
