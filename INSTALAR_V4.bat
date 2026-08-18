@echo off
setlocal
cd /d "%~dp0"
title Instalacion - Inspeccion Visual V4

echo ============================================
echo   INSTALACION DE INSPECCION VISUAL V4
echo ============================================
echo.
echo Esta operacion se hace una sola vez en esta laptop.
echo Puede tardar unos minutos porque prepara Python y las librerias.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
set "exitCode=%ERRORLEVEL%"

echo.
if not "%exitCode%"=="0" (
    echo La instalacion no termino correctamente. Codigo: %exitCode%
    echo Revisa el mensaje anterior y presiona una tecla para cerrar.
    pause >nul
    exit /b %exitCode%
)

echo Instalacion terminada. Ya puedes abrir ABRIR_DEMO.bat.
pause
exit /b 0
