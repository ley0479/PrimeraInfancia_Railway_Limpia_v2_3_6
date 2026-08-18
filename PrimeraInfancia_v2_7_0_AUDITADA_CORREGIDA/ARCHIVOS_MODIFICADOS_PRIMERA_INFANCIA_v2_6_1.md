# Archivos modificados — PrimeraInfancia 2.6.1

**Base:** 2.6.0  
**Fecha:** 6 de agosto de 2026

## Nuevos (39)

```text
.github/workflows/integrity-ci.yml
ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_6_1.md
ARQUITECTURA_MOTOR_INTEGRIDAD_v2_6_1.md
EJECUTAR_GATE_INTEGRIDAD.bat
GUIA_CI_OBSERVABILIDAD_POSTGRES_v2_6_1.md
GUIA_MIGRACION_COMPLETA_POSTGRES_v2_6_1.md
INFORME_MIGRACION_POSTGRES_INTEGRIDAD_v2_6_1.md
MIGRAR_COMPLETO_A_POSTGRESQL.bat
MONITOREAR_PLATAFORMA.bat
PLAN_ROLLBACK_POSTGRES_v2_6_1.md
PRIVACIDAD_PRIMERA_INFANCIA_v2_6_1.json
REPARACION_SEGURA.bat
RESULTADOS_PRUEBAS_PRIMERA_INFANCIA_v2_6_1.json
VALIDACION_PRIMERA_INFANCIA_v2_6_1.json
VALIDACION_ZIP_EXTRAIDO_PRIMERA_INFANCIA_v2_6_1.json
VERIFICAR_MIGRACION_POSTGRESQL.bat
backend/modules/integrity_stability/__init__.py
backend/modules/integrity_stability/routes.py
backend/modules/integrity_stability/service.py
backend/services/observability.py
backend/tests/test_integrity_postgresql_v2_6_1.py
backend/tools/__init__.py
backend/tools/capture_integrity_baseline.py
backend/tools/integrity_gate.py
backend/tools/postgresql_cutover.py
backend/tools/postgresql_preflight.py
backend/tools/postgresql_runtime_audit.py
backend/tools/runtime_monitor.py
backend/tools/safe_repair.py
backend/tools/verify_sqlite_postgresql.py
frontend/css/integrity-stability.css
frontend/js/modules/integrity-stability.js
integrity/baseline_v2_6_0.json
integrity/critical_tests.json
integrity/safe_autofix_policy.json
scripts_windows/ejecutar_gate_integridad.ps1
scripts_windows/migrar_completo_postgresql.ps1
scripts_windows/monitorear_plataforma.ps1
scripts_windows/reparacion_segura.ps1
```

## Modificados (30)

```text
.env.example
MANIFEST_SHA256.txt
MIGRAR_SQLITE_A_POSTGRESQL.bat
README_RAILWAY.md
README_SCRIPTS_LOCAL_TUNEL.md
SOURCE_ARCHIVE_SHA256.txt
VALIDACION_Y_CAMBIOS.md
backend/app.py
backend/config.py
backend/database.py
backend/modules/backups/services.py
backend/modules/dbapi_compat.py
backend/modules/seguridad/services.py
backend/tests/test_migration_tool_v2_6_0.py
backend/tests/test_multitenant_release_v2_4_0.py
backend/tests/test_postgresql_compat_v2_6_0.py
backend/tests/test_tunnel_cloudflare_v2_4_3.py
backend/tests/test_tunnel_login_logging_v2_4_2.py
backend/tools/migrate_sqlite_to_postgresql.py
frontend/index.html
frontend/js/app.js
railway.json
scripts_windows/detener_plataforma.ps1
scripts_windows/diagnosticar_inicio_windows.ps1
scripts_windows/diagnosticar_login_tunel.ps1
scripts_windows/iniciar_plataforma.ps1
scripts_windows/iniciar_tunel_cloudflare.ps1
scripts_windows/migrar_sqlite_postgresql.ps1
start_hosting.sh
tools/validate_release.py
```

## Eliminados

Ninguno.

## Resumen técnico

- PostgreSQL obligatorio en producción y SQLite reservado para recuperación local y pruebas controladas.
- Corte verificable SQLite → PostgreSQL con preflight, snapshot consistente, conteos, huellas SHA-256, secuencias y validación de claves foráneas.
- Motor de Integridad con línea base estable, pruebas críticas, bloqueo del despliegue y reparación segura limitada a recursos temporales.
- GitHub Actions con PostgreSQL 16, migración real de fixture, verificación, validador del paquete, evidencias y job final `Deployment Gate`.
- Observabilidad con readiness, métricas, tiempos de respuesta, identificadores de solicitud y alertas estructuradas sin cuerpos ni secretos.
- Herramientas Windows para migración, verificación, gate, monitor y reparación segura.
- Sin eliminación de módulos, roles, formatos oficiales ni reglas funcionales.
