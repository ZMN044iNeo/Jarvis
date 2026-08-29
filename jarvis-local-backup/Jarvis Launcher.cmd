@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title J.A.R.V.I.S. Mark LXXXV Tactical HUD ^& AI Voice System
cls
echo ========================================================================
echo        J.A.R.V.I.S. MARK LXXXV // TACTICAL HUD ^& AI VOICE SYSTEM
echo              3D Hologram Matrix ^| PowerShell Box ^| Neural Chat
echo ========================================================================
echo.

:: 1. Verify Ollama Service Status
echo [1/2] Checking Local Ollama Server...
curl -s http://localhost:11434 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [NOTICE] Starting local Ollama server in background...
    start /min "" ollama serve
    ping 127.0.0.1 -n 3 >nul
) else (
    echo [OK] Ollama server is active and responding.
)

:: 2. Launch Tactical HUD GUI
echo [2/2] Launching J.A.R.V.I.S. Tactical HUD...
if exist "%~dp0.venv\Scripts\python.exe" (
    start "" "%~dp0.venv\Scripts\python.exe" "%~dp0jarvis_gui.py"
) else if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0jarvis_gui.py"
) else (
    start "" py -3 "%~dp0jarvis_gui.py"
)

echo [READY] J.A.R.V.I.S. initialization sequence complete.
ping 127.0.0.1 -n 2 >nul
endlocal
