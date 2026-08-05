# Archivos modificados — PrimeraInfancia 2.4.2

## Creados

```text
ABRIR_LOGS_ERRORES.bat
DIAGNOSTICAR_LOGIN_TUNEL.bat
ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_4_2.md
GUIA_PRUEBA_LOGIN_TUNEL_v2_4_2.md
INFORME_CORRECCION_LOGIN_TUNEL_Y_LOGS_v2_4_2.md
PRIVACIDAD_PRIMERA_INFANCIA_v2_4_2.json
VALIDACION_PRIMERA_INFANCIA_v2_4_2.json
backend/modules/seguridad/runtime_diagnostics.py
backend/tests/test_tunnel_login_logging_v2_4_2.py
scripts_windows/diagnosticar_login_tunel.ps1
```

## Modificados

```text
.env.example
INICIAR_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
README_RAILWAY.md
README_SCRIPTS_LOCAL_TUNEL.md
VALIDACION_Y_CAMBIOS.md
backend/app.py
backend/config.py
backend/modules/seguridad/routes.py
backend/modules/seguridad/services.py
backend/tests/test_multitenant_release_v2_4_0.py
frontend/js/app.js
scripts_windows/iniciar_tunel_cloudflare.ps1
tools/validate_release.py
MANIFEST_SHA256.txt
```

## Eliminados

No se eliminó ningún archivo funcional.

## Alcance

Los cambios se limitan al arranque local/túnel, identificación de instancia,
login, concurrencia SQLite, captura de errores, diagnóstico, documentación y
pruebas. No se modificaron los motores RPP, RAM, Bienestarina ni los datos de
fundaciones.
