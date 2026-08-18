@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts_windows\detener_plataforma.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [AVISO] El cierre termino con codigo %RC%.
if not "%PI_NO_PAUSE%"=="1" pause
exit /b %RC%
