# Archivos creados, modificados y eliminados — PrimeraInfancia 2.6.0

Comparación reproducible contra `PrimeraInfancia_v2_5_4_SUPERVISION_FAMILIAS_REDES.zip`.

## Nuevos

```text
ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_6_0.md
ARQUITECTURA_POSTGRES_SALUD_NUTRICION_v2_6_0.md
CONFIGURAR_POSTGRESQL_LOCAL.bat
DIAGNOSTICAR_INICIO_WINDOWS.bat
GUIA_MIGRACION_SQLITE_POSTGRES_v2_6_0.md
GUIA_PRUEBAS_SCRIPTS_SALUD_POSTGRES_v2_6_0.md
INFORME_IMPLEMENTACION_SALUD_NUTRICION_POSTGRES_v2_6_0.md
MIGRAR_SQLITE_A_POSTGRESQL.bat
PLAN_REVERSION_Y_CONTINGENCIA_v2_6_0.md
PRIVACIDAD_PRIMERA_INFANCIA_v2_6_0.json
RESPALDAR_POSTGRESQL.bat
RESTAURAR_POSTGRESQL.bat
RESULTADOS_PRUEBAS_PRIMERA_INFANCIA_v2_6_0.json
backend/modules/dbapi_compat.py
backend/modules/salud_nutricion/integral.py
backend/tests/test_migration_tool_v2_6_0.py
backend/tests/test_postgresql_compat_v2_6_0.py
backend/tests/test_salud_nutricion_integral_v2_6_0.py
backend/tests/test_windows_launchers_v2_6_0.py
backend/tools/check_database.py
backend/tools/migrate_sqlite_to_postgresql.py
scripts_windows/configurar_postgresql_local.ps1
scripts_windows/detener_plataforma.ps1
scripts_windows/diagnosticar_inicio_windows.ps1
scripts_windows/iniciar_plataforma.ps1
scripts_windows/migrar_sqlite_postgresql.ps1
scripts_windows/respaldar_postgresql.ps1
scripts_windows/restaurar_postgresql.ps1
```

## Modificados

```text
.env.example
DETENER_PLATAFORMA_LOCAL.bat
Dockerfile
INICIAR_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
README_RAILWAY.md
README_SCRIPTS_LOCAL_TUNEL.md
SOURCE_ARCHIVE_SHA256.txt
VALIDACION_Y_CAMBIOS.md
backend/app.py
backend/config.py
backend/database.py
backend/generador_formatos.py
backend/init_hosting.py
backend/modules/ajustes_ui/services.py
backend/modules/backups/services.py
backend/modules/base_maestra/repository.py
backend/modules/calendario_inteligente/repository.py
backend/modules/calidad_datos/repository.py
backend/modules/calidad_datos/services.py
backend/modules/cruce_bases/informe_estadistico.py
backend/modules/familias_redes/repository.py
backend/modules/gestion_coordinador/repository.py
backend/modules/gestion_integral_uca/integrations.py
backend/modules/gestion_integral_uca/repository.py
backend/modules/gestion_pedagogica/repository.py
backend/modules/institucional_normativo.py
backend/modules/motor_gestion_proyecto/repository.py
backend/modules/motor_plantillas/repository.py
backend/modules/motor_plantillas/services.py
backend/modules/paquete_mensual/services.py
backend/modules/planeacion_pedagogica/repository.py
backend/modules/plantillas_oficiales.py
backend/modules/reportes_gerenciales/services.py
backend/modules/salud_nutricion/routes.py
backend/modules/salud_nutricion/schema.py
backend/modules/seguridad/routes.py
backend/modules/seguridad/services.py
backend/modules/sqlalchemy_compat.py
backend/modules/supervision_calidad/repository.py
backend/modules/theme_manager/services.py
backend/motor_alertas.py
backend/requirements-production.txt
backend/requirements.txt
backend/services/rpp_minutas_service.py
backend/services/uds_catalog.py
backend/tests/test_multitenant_release_v2_4_0.py
backend/tests/test_tunnel_admin_recovery_v2_4_1.py
backend/tests/test_tunnel_cloudflare_v2_4_3.py
backend/tests/test_tunnel_login_logging_v2_4_2.py
frontend/css/salud-nutricion.css
frontend/index.html
frontend/js/modules/salud-nutricion.js
scripts_windows/diagnosticar_login_tunel.ps1
scripts_windows/iniciar_tunel_cloudflare.ps1
start_hosting.sh
tools/validate_release.py
```

## Eliminados

Ninguno.

**Resumen:** 28 nuevos, 57 modificados y 0 eliminados.
