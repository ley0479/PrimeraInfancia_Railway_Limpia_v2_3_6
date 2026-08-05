@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

title Primera Infancia - Detener local y tunel

echo ============================================================
echo   DETENER PRIMERA INFANCIA - LOCAL + TUNEL
echo ============================================================
echo.

set "ROOT=%~dp0"
if not exist "%ROOT%backend\" if exist "%~dp0..\backend\" set "ROOT=%~dp0..\"
for %%I in ("%ROOT%.") do set "ROOT=%%~fI\"

set "PID_FILE=%ROOT%.runtime_windows\cloudflared_tunnel.pid"
if exist "%PID_FILE%" (
  set /p TUNNEL_PID=<"%PID_FILE%"
  if defined TUNNEL_PID (
    tasklist /FI "PID eq !TUNNEL_PID!" /FI "IMAGENAME eq cloudflared.exe" 2>nul | findstr /C:"!TUNNEL_PID!" >nul
    if not errorlevel 1 (
      echo Cerrando tunel de este proyecto - PID !TUNNEL_PID!
      taskkill /PID !TUNNEL_PID! /F >nul 2>&1
    )
  )
  del /Q "%PID_FILE%" >nul 2>&1
)

set "PORTS=5000"
echo Cerrando backend local de la plataforma...
for %%P in (%PORTS%) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    echo Cerrando puerto %%P - PID %%A
    taskkill /PID %%A /F >nul 2>&1
  )
)

if exist "%ROOT%.runtime_windows\_run_backend_unificado.cmd" del /Q "%ROOT%.runtime_windows\_run_backend_unificado.cmd" >nul 2>&1

echo.
echo Listo. No se cerraron otros tuneles cloudflared ajenos a este proyecto.
pause
endlocal
