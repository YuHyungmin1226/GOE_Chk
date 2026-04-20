@echo off
title GOE Messenger Bridge (Gemini 1.5 Flash)
echo ====================================================
echo   GOE Messenger to Google Tasks Auto-Bridge 
echo   [Model: Gemini 1.5 Flash / Real-time Sync]
echo ====================================================
echo [INFO] Background loop started.
echo [INFO] Press Ctrl+C to stop.
echo.

cd /d "%~dp0"
python goe_bridge.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Program terminated with error code: %errorlevel%
    pause
)
