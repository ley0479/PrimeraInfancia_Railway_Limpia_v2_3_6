@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts_windows\reparacion_segura.ps1" %*
exit /b %ERRORLEVEL%
