# Archivos modificados — PrimeraInfancia 2.4.1

**Base comparada:** PrimeraInfancia 2.4.0 Multi-fundación Piloto Seguro  
**Entrega:** PrimeraInfancia 2.4.1 Operativa — túnel, administración y recuperación

- **Creados:** 7
- **Modificados:** 22
- **Eliminados:** 0

## Archivos creados

- `ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_4_1.md` — Inventario de archivos creados, modificados y eliminados.
- `GUIA_PRUEBAS_TUNEL_USUARIOS_RECUPERACION_v2_4_1.md` — Matriz de aceptación local, túnel, usuarios y recuperación.
- `INFORME_AUDITORIA_Y_AJUSTES_PRIMERA_INFANCIA_v2_4_1.md` — Informe técnico de auditoría y ajustes.
- `PLAN_MEJORAS_PRIMERA_INFANCIA_v2_4_1.md` — Plan posterior de producción y seguridad.
- `PRIVACIDAD_PRIMERA_INFANCIA_v2_4_1.json` — Control estructural de privacidad y secretos.
- `VALIDACION_PRIMERA_INFANCIA_v2_4_1.json` — Resultados reproducibles del validador.
- `backend/tests/test_tunnel_admin_recovery_v2_4_1.py` — Pruebas SQLite de aislamiento, administración y recuperación.

## Archivos modificados

- `.dockerignore` — Exclusión de artefactos locales, túnel y runtime en Docker.
- `.env.example` — Variables 2.4.1 para recuperación, túnel y controles multi-fundación.
- `.gitignore` — Exclusión de credenciales/runtime, logs y binario cloudflared.
- `DETENER_PLATAFORMA_LOCAL.bat` — Cierre selectivo del backend y del túnel de este proyecto.
- `INICIAR_PLATAFORMA_LOCAL.bat` — Arranque por /api/health, secretos aleatorios y credenciales iniciales seguras.
- `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat` — Lanzador del túnel actualizado.
- `MANIFEST_SHA256.txt` — Manifiesto integral de la nueva entrega.
- `README_RAILWAY.md` — Configuración y operación 2.4.1 en Railway.
- `README_SCRIPTS_LOCAL_TUNEL.md` — Uso local/túnel, credenciales aleatorias y diagnóstico.
- `SOURCE_ARCHIVE_SHA256.txt` — Proveniencia del ZIP fuente aportado.
- `VALIDACION_Y_CAMBIOS.md` — Historial técnico de la versión.
- `backend/app.py` — Healthcheck enriquecido, URL pública y Acceso Compartido.
- `backend/config.py` — Variables y validaciones de recuperación/túnel/producción.
- `backend/modules/seguridad/routes.py` — Login, recuperación y CRUD seguro de usuarios/fundaciones.
- `backend/modules/seguridad/schema.py` — Campos y tablas aditivas para eliminación lógica y recuperación.
- `backend/modules/seguridad/services.py` — Migraciones, correo y URL de recuperación consciente del túnel.
- `backend/tests/test_multitenant_release_v2_4_0.py` — Regresión de versión y seguridad multi-fundación.
- `frontend/index.html` — Formularios de administración y recuperación.
- `frontend/js/app.js` — Flujos UI de usuarios, fundaciones y contraseña.
- `frontend/js/modules/acceso-compartido.js` — Estado del túnel y enlace público verificado.
- `scripts_windows/iniciar_tunel_cloudflare.ps1` — Quick Tunnel robusto, logs, URL, PID y verificación pública.
- `tools/validate_release.py` — Controles reproducibles 2.4.1.

## Archivos eliminados

- Ninguno.

## Criterio de compatibilidad

Los cambios de base de datos son aditivos e idempotentes. La eliminación de usuarios y fundaciones es lógica; no se borran en cascada los registros históricos. La entrega conserva los activos operativos y las protecciones multi-fundación de 2.4.0.
