@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
REM Compatibilidad: el flujo histórico ahora delega al corte completo verificable.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts_windows\migrar_completo_postgresql.ps1"
set "RC=%ERRORLEVEL%"
if not "%PI_NO_PAUSE%"=="1" pause
exit /b %RC%
