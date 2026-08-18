# Archivos modificados — PrimeraInfancia 2.4.3

## Nuevos

```text
DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat
backend/tests/test_tunnel_cloudflare_v2_4_3.py
INFORME_CORRECCION_TUNEL_CLOUDFLARE_v2_4_3.md
GUIA_PRUEBA_TUNEL_CLOUDFLARE_v2_4_3.md
ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_4_3.md
VALIDACION_PRIMERA_INFANCIA_v2_4_3.json
PRIVACIDAD_PRIMERA_INFANCIA_v2_4_3.json
```

## Modificados

```text
.env.example
DIAGNOSTICAR_LOGIN_TUNEL.bat
INICIAR_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
MANIFEST_SHA256.txt
README_RAILWAY.md
README_SCRIPTS_LOCAL_TUNEL.md
SOURCE_ARCHIVE_SHA256.txt
VALIDACION_Y_CAMBIOS.md
backend/config.py
backend/tests/test_multitenant_release_v2_4_0.py
backend/tests/test_tunnel_login_logging_v2_4_2.py
scripts_windows/diagnosticar_login_tunel.ps1
scripts_windows/iniciar_tunel_cloudflare.ps1
tools/validate_release.py
```

## Eliminados

Ninguno.

## Alcance funcional

La lógica funcional del backend y del frontend no se reemplazó. Los cambios se concentran en el lanzador de Cloudflare, el diagnóstico, la versión declarada, la documentación y las pruebas de regresión.
