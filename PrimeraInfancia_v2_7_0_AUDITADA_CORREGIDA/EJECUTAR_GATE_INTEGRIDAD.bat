@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts_windows\ejecutar_gate_integridad.ps1" %*
exit /b %ERRORLEVEL%
