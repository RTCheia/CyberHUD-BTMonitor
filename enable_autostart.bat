@echo off
setlocal
title Enable CyberHUD BT Monitor Autostart

:: Request Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Requesting Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo =================================================================
echo   Registering CyberHUD Bluetooth Monitor Autostart on Boot
echo =================================================================
echo.
echo [*] Task Name : RTC_CyberHUD_BTMonitor
echo [*] Target    : "%~dp0start_bt_monitor.bat"
echo [*] Privileges: Highest Available (Administrator)
echo.

schtasks /create /tn "RTC_CyberHUD_BTMonitor" /tr "\"%~dp0start_bt_monitor.bat\"" /sc onlogon /rl highest /f
echo.

if %errorlevel% == 0 (
    echo =================================================================
    echo  [SUCCESS] Autostart on Windows Logon has been enabled!
    echo  - On every boot / logon, the monitor will automatically start
    echo    with Administrator privileges (zero UAC prompts).
    echo =================================================================
) else (
    echo [FAIL] Failed to register scheduled task.
)

echo.
pause
