@echo off
setlocal
cd /d "%~dp0"
echo ======================================================================
echo           COPILOT MULTI-ACCOUNT FLEET LAUNCHER
echo ======================================================================
echo.

python tools\copilot_fleet.py status

echo.
echo Select action:
echo   [1] Show Fleet Status
echo   [2] Run Canary Test on All Ready Accounts
echo   [3] Launch FastAPI Fleet Coordinator Server
echo   [4] Launch Client Worker Fleet Supervisor Daemon
echo   [Q] Quit
echo.

set /p CHOICE="Enter choice [1-4 or Q]: "
if /i "%CHOICE%"=="1" (
    python tools\copilot_fleet.py status
    goto end
)
if /i "%CHOICE%"=="2" (
    python tools\copilot_fleet.py canary
    goto end
)
if /i "%CHOICE%"=="3" (
    echo Starting FastAPI Coordinator on http://127.0.0.1:8000 ...
    uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
    goto end
)
if /i "%CHOICE%"=="4" (
    echo Starting Fleet Supervisor ...
    python client\fleet_supervisor.py
    goto end
)

:end
pause
