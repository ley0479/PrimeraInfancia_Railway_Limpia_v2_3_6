@echo off
chcp 65001 >nul
title Primera Infancia - Backend Flask
cd /d "C:\Users\kioskUser0\Documents\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA LISTA\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA\backend"
set "APP_ENV=development"
set "FLASK_ENV=development"
set "SERVER_MODE=LOCAL"
set "FLASK_HOST=127.0.0.1"
set "FLASK_PORT=5000"
set "PORT=5000"
set "FRONTEND_PORT=8081"
set "FRONTEND_ORIGIN=http://127.0.0.1:8081"
set "ALLOWED_ORIGINS=http://127.0.0.1:8081,http://localhost:8081,http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:8081,http://localhost:8081,http://127.0.0.1:8090,http://localhost:8090,http://127.0.0.1:9000,http://localhost:9000,http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5173,http://localhost:5173"
set "BACKEND_URL=http://127.0.0.1:5000"
set "DATABASE_PATH=database.sqlite3"
set "DATABASE_URL=sqlite:///database.sqlite3"
set "UPLOAD_FOLDER=uploads"
set "OUTPUT_FOLDER=archivos_actualizados"
set "TEMPLATES_FOLDER=templates_originales"
set "LOG_FOLDER=logs"
set "BACKUPS_FOLDER=backups"
set "SESSION_COOKIE_SECURE=false"
set "SESSION_COOKIE_SAMESITE=Lax"
set "FORCE_HTTPS=false"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
echo Backend local: http://127.0.0.1:5000
echo Frontend permitido: http://127.0.0.1:8081
"C:\Users\kioskUser0\Documents\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA LISTA\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA\backend\.venv\Scripts\python.exe" app.py
