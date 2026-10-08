@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "tools\fleet_gui.py"
) else (
    start "" pythonw "tools\fleet_gui.py"
)
