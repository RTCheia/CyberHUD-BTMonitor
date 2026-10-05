@echo off
setlocal
title Disable CyberHUD BT Monitor Autostart

:: Request Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Requesting Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo =================================================================
echo   Disabling CyberHUD Bluetooth Monitor Autostart
echo =================================================================
echo.

schtasks /delete /tn "RTC_CyberHUD_BTMonitor" /f
echo.

if %errorlevel% == 0 (
    echo [OK] Autostart task 'RTC_CyberHUD_BTMonitor' has been deleted.
) else (
    echo [INFO] Task not found or already deleted.
)

echo.
pause
