@echo off
setlocal EnableExtensions
chcp 65001 >nul

title Primera Infancia v2.5.2 - Diagnostico login y tunel
set "ROOT=%~dp0"
if not exist "%ROOT%backend\" if exist "%~dp0..\backend\" set "ROOT=%~dp0..\"
for %%I in ("%ROOT%.") do set "ROOT=%%~fI\"

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts_windows\diagnosticar_login_tunel.ps1"
echo.
pause
endlocal
