# Archivos modificados — PrimeraInfancia 2.5.1

**Base comparada:** PrimeraInfancia 2.5.0 Gestión Integral UCA  
**Alcance:** autenticación, concurrencia SQLite, sesiones simultáneas y recuperación del formulario de login.

## Archivos nuevos

```text
ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_5_1.md
GUIA_PRUEBAS_AUTENTICACION_v2_5_1.md
INFORME_AUDITORIA_AUTENTICACION_v2_5_1.md
PRIVACIDAD_PRIMERA_INFANCIA_v2_5_1.json
RESULTADOS_AUTH_CONCURRENCIA_v2_5_1.json
VALIDACION_PRIMERA_INFANCIA_v2_5_1.json
backend/tests/test_auth_concurrency_v2_5_1.py
```

## Archivos modificados

```text
.env.example
DIAGNOSTICAR_LOGIN_TUNEL.bat
DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat
INICIAR_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
MANIFEST_SHA256.txt
README_RAILWAY.md
README_SCRIPTS_LOCAL_TUNEL.md
SOURCE_ARCHIVE_SHA256.txt
VALIDACION_Y_CAMBIOS.md
backend/config.py
backend/database.py
backend/modules/facturacion_suscripcion/services.py
backend/modules/seguridad/routes.py
backend/modules/seguridad/services.py
backend/modules/sqlalchemy_compat.py
backend/tests/test_multitenant_release_v2_4_0.py
backend/tests/test_tunnel_cloudflare_v2_4_3.py
backend/tests/test_tunnel_login_logging_v2_4_2.py
frontend/index.html
frontend/js/app.js
scripts_windows/diagnosticar_login_tunel.ps1
scripts_windows/iniciar_tunel_cloudflare.ps1
tools/validate_release.py
```

## Archivos eliminados

```text
Ninguno.
```

## Resumen funcional

- Se mantuvo el esquema de base de datos.
- Se mantuvieron roles y permisos.
- Se redujeron las ventanas de escritura durante login.
- Se añadieron reintentos SQLite internos acotados.
- Se preservan sesiones activas en varios dispositivos.
- Se eliminó mantenimiento de facturación dentro del flujo crítico.
- Se evitó renegociar WAL en cada conexión.
- Se agregó timeout, reintento único y recuperación del botón en el frontend.
- Se añadieron pruebas de concurrencia y falsos bloqueos.
