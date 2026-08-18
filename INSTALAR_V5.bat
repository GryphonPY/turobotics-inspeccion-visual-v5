@echo off
setlocal
cd /d "%~dp0"
title Instalacion - Inspeccion Visual V5

echo ============================================
echo   INSTALACION DE INSPECCION VISUAL V5
echo ============================================
echo.
echo Esta operacion prepara el entorno virtual de Python y descarga
echo todas las librerias necesarias (PySide6, OpenCV, ONNXRuntime, etc.).
echo Solo se requiere conexion a internet y Python 3.11 o superior.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
set "exitCode=%ERRORLEVEL%"

echo.
if not "%exitCode%"=="0" (
    echo [ERROR] La instalacion no termino correctamente. Codigo: %exitCode%
    echo Revisa el mensaje anterior y presiona una tecla para cerrar.
    pause >nul
    exit /b %exitCode%
)

echo ============================================
echo   INSTALACION COMPLETADA CON EXITO
echo ============================================
echo Ya puedes ejecutar el sistema usando:
echo   - ABRIR_DEMO_V5.bat (o ABRIR_DEMO_V5.vbs)
echo.
pause
exit /b 0
