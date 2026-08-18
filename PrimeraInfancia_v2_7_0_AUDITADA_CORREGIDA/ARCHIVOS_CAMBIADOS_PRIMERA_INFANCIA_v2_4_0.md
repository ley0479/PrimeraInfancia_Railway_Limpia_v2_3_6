# Archivos modificados — PrimeraInfancia 2.4.0 multi-fundación

Comparación contra la versión 2.3.7 Railway limpia operativa.

- Añadidos: **12**
- Modificados: **47**
- Eliminados: **0**

## Archivos añadidos

- `DETENER_PLATAFORMA_LOCAL.bat`
- `GUIA_PRUEBAS_MULTIFUNDACION_RAILWAY_v2_4_0.md`
- `INFORME_MULTIFUNDACION_PRIMERA_INFANCIA_v2_4_0.md`
- `INICIAR_PLATAFORMA_LOCAL.bat`
- `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat`
- `README_SCRIPTS_LOCAL_TUNEL.md`
- `backend/migrations/migrate_multitenant_phase3.py`
- `backend/modules/seguridad/tenant_context.py`
- `backend/modules/seguridad/tenant_sql_guard.py`
- `backend/tests/test_multitenant_phase3.py`
- `backend/tests/test_multitenant_release_v2_4_0.py`
- `scripts_windows/iniciar_tunel_cloudflare.ps1`

## Archivos modificados

- `.env.example`
- `README_RAILWAY.md`
- `REFERENCE_ARCHIVE_SHA256.txt`
- `SOURCE_ARCHIVE_SHA256.txt`
- `VALIDACION_Y_CAMBIOS.md`
- `backend/app.py`
- `backend/config.py`
- `backend/generador_formatos.py`
- `backend/init_hosting.py`
- `backend/modules/base_maestra/repository.py`
- `backend/modules/base_maestra/routes.py`
- `backend/modules/calendario_inteligente/routes.py`
- `backend/modules/calidad_datos/routes.py`
- `backend/modules/calidad_datos/services.py`
- `backend/modules/cruce_bases/repository.py`
- `backend/modules/cruce_bases/routes.py`
- `backend/modules/facturacion_suscripcion/repository.py`
- `backend/modules/facturacion_suscripcion/routes.py`
- `backend/modules/facturacion_suscripcion/services.py`
- `backend/modules/gerencia_general/services.py`
- `backend/modules/gestion_coordinador/repository.py`
- `backend/modules/gestion_coordinador/routes.py`
- `backend/modules/gestion_pedagogica/repository.py`
- `backend/modules/gestion_pedagogica/routes.py`
- `backend/modules/gestion_pedagogica/services.py`
- `backend/modules/institucional_normativo.py`
- `backend/modules/motor_plantillas/routes.py`
- `backend/modules/motor_plantillas/schema.py`
- `backend/modules/operational_jobs.py`
- `backend/modules/panel_comercial/schema.py`
- `backend/modules/panel_comercial/services.py`
- `backend/modules/paquete_mensual/services.py`
- `backend/modules/planeacion_pedagogica/repository.py`
- `backend/modules/planeacion_pedagogica/routes.py`
- `backend/modules/reportes_gerenciales/services.py`
- `backend/modules/salud_nutricion/entregables.py`
- `backend/modules/salud_nutricion/repository.py`
- `backend/modules/salud_nutricion/routes.py`
- `backend/modules/seguridad/routes.py`
- `backend/modules/seguridad/services.py`
- `backend/modules/sqlalchemy_compat.py`
- `backend/modules/talento_humano/services.py`
- `backend/motor_alertas.py`
- `backend/services/rpp_minutas_service.py`
- `backend/services/uds_catalog.py`
- `frontend/js/modules/institucional-normativo.js`
- `tools/validate_release.py`

## Archivos eliminados

- Ninguno.

## Criterio

Los cambios se concentran en contexto tenant, migración de esquema, protección SQL, almacenamiento por fundación, administración, facturación, plantillas versionadas, archivos institucionales, trabajos en segundo plano, pruebas y documentación. No se incorporaron datos operativos.
