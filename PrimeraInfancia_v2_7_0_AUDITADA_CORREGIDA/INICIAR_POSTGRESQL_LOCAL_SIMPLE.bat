@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts_windows\iniciar_postgresql_simple.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [ERROR] No se pudo iniciar la plataforma. Codigo: %RC%
  pause
)
exit /b %RC%
