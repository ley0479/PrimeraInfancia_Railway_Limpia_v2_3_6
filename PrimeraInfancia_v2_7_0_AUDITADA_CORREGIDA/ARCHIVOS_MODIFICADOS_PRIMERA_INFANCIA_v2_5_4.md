# Archivos creados y modificados — PrimeraInfancia 2.5.4

**Base comparada:** PrimeraInfancia 2.5.3 — Biblioteca Oficial ICBF y Motor de Gestión

## Nuevos

```text
ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_5_4.md
ARQUITECTURA_SUPERVISION_FAMILIAS_REDES_v2_5_4.md
GUIA_PRUEBA_SUPERVISION_FAMILIAS_REDES_v2_5_4.md
INFORME_IMPLEMENTACION_SUPERVISION_FAMILIAS_REDES_v2_5_4.md
PRIVACIDAD_PRIMERA_INFANCIA_v2_5_4.json
RESULTADOS_SUPERVISION_FAMILIAS_REDES_v2_5_4.json
backend/modules/familias_redes/__init__.py
backend/modules/familias_redes/repository.py
backend/modules/familias_redes/routes.py
backend/modules/familias_redes/schema.py
backend/modules/familias_redes/services.py
backend/modules/supervision_calidad/__init__.py
backend/modules/supervision_calidad/repository.py
backend/modules/supervision_calidad/routes.py
backend/modules/supervision_calidad/schema.py
backend/modules/supervision_calidad/services.py
backend/tests/test_supervision_familias_redes_v2_5_4.py
frontend/css/familias-redes.css
frontend/css/supervision-calidad.css
frontend/js/modules/familias-redes.js
frontend/js/modules/supervision-calidad.js
```

## Modificados

```text
.env.example
INICIAR_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
MANIFEST_SHA256.txt
README_RAILWAY.md
README_SCRIPTS_LOCAL_TUNEL.md
SOURCE_ARCHIVE_SHA256.txt
VALIDACION_Y_CAMBIOS.md
backend/app.py
backend/config.py
backend/modules/gestion_integral_uca/integrations.py
backend/modules/motor_gestion_proyecto/repository.py
backend/modules/seguridad/services.py
backend/tests/test_auth_concurrency_v2_5_1.py
backend/tests/test_expediente_uca_central_v2_5_2.py
backend/tests/test_multitenant_release_v2_4_0.py
backend/tests/test_tunnel_cloudflare_v2_4_3.py
backend/tests/test_tunnel_login_logging_v2_4_2.py
frontend/index.html
frontend/js/app.js
scripts_windows/diagnosticar_login_tunel.ps1
scripts_windows/iniciar_tunel_cloudflare.ps1
tools/validate_release.py
```

## Eliminados

Ninguno.

## Resumen

- Archivos nuevos: **21**
- Archivos modificados: **23**
- Archivos eliminados: **0**

## Alcance

- Backend y frontend del Centro de Supervisión, Auditoría y Calidad.
- Backend y frontend de Gestión Integral de Familias, Comunidad y Redes.
- Integración con Expediente UCA y Motor de Gestión.
- Roles, menús, pruebas de regresión, documentación, scripts y versión declarada.

Los datos operativos, bases SQLite, secretos, logs y carpetas runtime no forman parte del paquete distribuible.
