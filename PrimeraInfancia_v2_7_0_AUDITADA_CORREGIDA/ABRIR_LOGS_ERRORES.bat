@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ROOT=%~dp0"
if not exist "%ROOT%backend\" if exist "%~dp0..\backend\" set "ROOT=%~dp0..\"
for %%I in ("%ROOT%.") do set "ROOT=%%~fI\"
set "LOG_DIR=%ROOT%data\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

echo Los errores reales de ejecucion se guardan en:
echo %LOG_DIR%
echo.
echo backend\logs no es la carpeta operativa.
start "" explorer.exe "%LOG_DIR%"
endlocal
