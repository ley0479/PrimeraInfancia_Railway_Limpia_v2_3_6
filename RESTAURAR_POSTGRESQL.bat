@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts_windows\restaurar_postgresql.ps1"
set "RC=%ERRORLEVEL%"
if not "%PI_NO_PAUSE%"=="1" pause
exit /b %RC%
