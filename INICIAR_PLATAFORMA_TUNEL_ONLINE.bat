@echo off
setlocal EnableExtensions
chcp 65001 >nul

title Primera Infancia v2.4.2 - Tunel Cloudflare verificado

set "ROOT=%~dp0"
if not exist "%ROOT%backend\" if exist "%~dp0..\backend\" set "ROOT=%~dp0..\"
for %%I in ("%ROOT%.") do set "ROOT=%%~fI\"

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts_windows\iniciar_tunel_cloudflare.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] El tunel no pudo iniciar. Revisa el mensaje anterior.
  pause
  exit /b 1
)
endlocal
