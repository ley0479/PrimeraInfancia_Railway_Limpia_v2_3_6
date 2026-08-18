@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts_windows\migrar_completo_postgresql.ps1" -VerifyExisting
set "RC=%ERRORLEVEL%"
if not "%PI_NO_PAUSE%"=="1" pause
exit /b %RC%
