@echo off
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\pythonw.exe" (
    echo No se encontro el entorno V5 en .venv\Scripts\pythonw.exe
    exit /b 2
)
if not exist "%ROOT%logs" mkdir "%ROOT%logs"
pushd "%ROOT%"
"%ROOT%.venv\Scripts\pythonw.exe" -m inspection_v5.qt_app --root "%ROOT%" --camera -1 >> "%ROOT%logs\v5_launcher.log" 2>&1
set "CODE=%ERRORLEVEL%"
popd
exit /b %CODE%
