@echo off
chcp 65001 >nul
title Primera Infancia - Frontend local
cd /d "C:\Users\kioskUser0\Documents\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA LISTA\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA\frontend"
echo Frontend local: http://127.0.0.1:8081
echo Backend configurado: http://127.0.0.1:5000
"C:\Users\kioskUser0\Documents\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA LISTA\PrimeraInfancia_v2_7_0_AUDITADA_CORREGIDA\backend\.venv\Scripts\python.exe" -m http.server 8081 --bind 127.0.0.1
