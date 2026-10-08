@echo off
setlocal
cd /d "%~dp0"
title Copilot Queue Worker - File-Based Task Runner
echo ======================================================================
echo    COPILOT QUEUE WORKER (Zero-GUI Background Task Runner)
echo ======================================================================
echo Watching orchestrator-state\tasks for pending code tasks...
echo Press Ctrl+C to stop.
echo.

python "..\Fleet-Orchestrator\tools\copilot_queue_worker.py" --state-dir "%~dp0orchestrator-state"
if errorlevel 1 (
    echo.
    echo [!] Worker exited with code %errorlevel%.
    pause
)
