@echo off
setlocal
cd /d "%~dp0"
title PC Monitor - Bluetooth Streamer

set "PYTHON_EXE=C:\ProgramData\miniconda3\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

:: 1. Request Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Requesting Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

:: 2. Ensure Autostart Task Registered with Highest Administrator Privileges
schtasks /query /tn "RTC_CyberHUD_BTMonitor" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Registering autostart scheduled task with highest administrator privileges...
    schtasks /create /tn "RTC_CyberHUD_BTMonitor" /tr "\"%~f0\"" /sc onlogon /rl highest /f >nul 2>&1
    if %errorlevel% == 0 (
        echo [OK] Autostart on boot successfully registered (RTC_CyberHUD_BTMonitor).
    )
)

echo =================================================================
echo       PC Monitor - Bluetooth Realtime Telemetry Streamer
echo =================================================================

"%PYTHON_EXE%" "%~dp0pc_sender\bt_monitor_sender.py"
pause
