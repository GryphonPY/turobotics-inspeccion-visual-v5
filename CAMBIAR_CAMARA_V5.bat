@echo off
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\pythonw.exe" exit /b 2
if not exist "%ROOT%logs" mkdir "%ROOT%logs"
start "" "%ROOT%.venv\Scripts\pythonw.exe" -m inspection_v5.qt_app --root "%ROOT%" --camera -1
exit /b 0
