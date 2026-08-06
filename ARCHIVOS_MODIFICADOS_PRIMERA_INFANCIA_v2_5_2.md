# Archivos modificados — PrimeraInfancia 2.5.2

## Nuevos

```text
ARQUITECTURA_EXPEDIENTE_UCA_CENTRAL_v2_5_2.md
GUIA_PRUEBA_EXPEDIENTE_UCA_CENTRAL_v2_5_2.md
INFORME_IMPLEMENTACION_EXPEDIENTE_UCA_CENTRAL_v2_5_2.md
PRIVACIDAD_PRIMERA_INFANCIA_v2_5_2.json
RESULTADOS_EXPEDIENTE_UCA_CENTRAL_v2_5_2.json
VALIDACION_PRIMERA_INFANCIA_v2_5_2.json
VALIDACION_ZIP_EXTRAIDO_PRIMERA_INFANCIA_v2_5_2.json
backend/modules/gestion_integral_uca/integrations.py
backend/tests/test_expediente_uca_central_v2_5_2.py
```

## Modificados

```text
.env.example
DIAGNOSTICAR_LOGIN_TUNEL.bat
DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat
INICIAR_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
README_RAILWAY.md
README_SCRIPTS_LOCAL_TUNEL.md
SOURCE_ARCHIVE_SHA256.txt
VALIDACION_Y_CAMBIOS.md
backend/config.py
backend/modules/gestion_integral_uca/repository.py
backend/modules/gestion_integral_uca/routes.py
backend/modules/gestion_integral_uca/schema.py
backend/modules/gestion_integral_uca/services.py
backend/tests/test_auth_concurrency_v2_5_1.py
backend/tests/test_multitenant_release_v2_4_0.py
backend/tests/test_tunnel_cloudflare_v2_4_3.py
backend/tests/test_tunnel_login_logging_v2_4_2.py
frontend/css/gestion-integral-uca.css
frontend/index.html
frontend/js/modules/gestion-integral-uca.js
scripts_windows/diagnosticar_login_tunel.ps1
scripts_windows/iniciar_tunel_cloudflare.ps1
tools/validate_release.py
```

## Eliminados

Ninguno.

## Alcance

Los cambios funcionales se concentran en la vista central del Expediente por UCA, la integración de solo lectura, el índice documental referencial, los indicadores, alertas, cronograma y el paquete de supervisión ampliado. Los cambios de versión en scripts y pruebas conservan las correcciones heredadas de túnel y autenticación.
