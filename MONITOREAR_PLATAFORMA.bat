@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts_windows\monitorear_plataforma.ps1" %*
exit /b %ERRORLEVEL%
