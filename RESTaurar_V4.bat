@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%ABRIR_DEMO.bat" (
    echo No se encontro el launcher V4 en "%ROOT%ABRIR_DEMO.bat".
    exit /b 1
)
call "%ROOT%ABRIR_DEMO.bat"
exit /b %errorlevel%
