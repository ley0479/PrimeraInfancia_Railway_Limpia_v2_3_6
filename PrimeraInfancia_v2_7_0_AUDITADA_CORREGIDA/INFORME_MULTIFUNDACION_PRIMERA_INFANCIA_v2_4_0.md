# Informe técnico — PrimeraInfancia 2.4.0 piloto multi-fundación

**Fecha:** 3 de agosto de 2026  
**Estado:** candidato para pruebas controladas con dos fundaciones y datos ficticios.  
**No autorizado aún:** tratamiento de información personal real o apertura comercial general.

## 1. Objetivo

Habilitar varias fundaciones dentro de una misma instalación de PrimeraInfancia sin depender del plan de Railway y sin retirar la seguridad conseguida en la versión limpia operativa. La creación de fundaciones queda reservada al rol `SUPERADMIN`; usuarios, registros y archivos deben permanecer aislados por `fundacion_id`.

## 2. Base y procedencia

La base funcional fue `PrimeraInfancia_v2_3_7_RAILWAY_LIMPIA_OPERATIVA.zip`. Del archivo local aportado `PrimeraInfancia_v2_3_6_SAAS_FASE1_ESTABILIZACION_BASELINE_SCRIPTS_LOCAL_TUNEL(1).zip` se conservaron los scripts Windows/local/túnel y su documentación. El archivo aportado no fue modificado.

No se incorporaron bases SQLite, archivos `.env`, beneficiarios, usuarios históricos, cargas, resultados, respaldos, logs ni documentos diligenciados.

## 3. Arquitectura de aislamiento

### 3.1 Contexto autenticado

`backend/modules/seguridad/tenant_context.py` obtiene la fundación desde el usuario autenticado en `g.current_user`. No confía en `fundacion_id` enviado por formularios para operaciones normales. El mismo contexto se propaga a trabajos en segundo plano.

### 3.2 Cortafuegos SQL

`backend/modules/seguridad/tenant_sql_guard.py` protege conexiones SQLite heredadas y la compatibilidad SQLAlchemy Core:

- agrega el filtro de fundación a `SELECT`, `UPDATE` y `DELETE` simples;
- agrega `fundacion_id` a `INSERT` cuando falta;
- rechaza escrituras explícitas hacia otra fundación;
- rechaza `JOIN` o subconsultas sin alcance verificable;
- valida que parámetros explícitos de consultas complejas coincidan con el tenant autenticado;
- bloquea DML dentro de `executescript` durante operaciones multi-fundación;
- permite catálogos compartidos y tablas centrales únicamente bajo reglas explícitas.

### 3.3 Esquema v3

`backend/migrations/migrate_multitenant_phase3.py`:

- añade `fundacion_id` a tablas operativas heredadas;
- asigna registros históricos sin tenant a la fundación inicial durante la migración controlada;
- crea índices de consulta por tenant;
- reemplaza restricciones globales por restricciones compuestas, por ejemplo `(fundacion_id, documento, unidad)`;
- registra la versión de esquema multi-fundación 3;
- puede ejecutarse repetidamente sin duplicar la migración.

### 3.4 Archivos separados

Los archivos operativos se resuelven bajo:

```text
/data/tenants/<fundacion_id>/uploads
/data/tenants/<fundacion_id>/archivos_actualizados
/data/tenants/<fundacion_id>/documentos_institucionales
/data/tenants/<fundacion_id>/cuentas_cobro_plantillas
/data/tenants/<fundacion_id>/backups
/data/tenants/<fundacion_id>/logs
/data/tenants/<fundacion_id>/storage
```

Las semillas oficiales sanitizadas permanecen compartidas; las cargas, evidencias, resultados y personalizaciones quedan separadas.

## 4. Administración de fundaciones y usuarios

Al crear una fundación se inicializan de forma independiente:

- directorios persistentes;
- suscripción inicial de piloto;
- corporación operativa;
- catálogo de 32 UDS;
- reglas de cumplimiento;
- minuta RPP sanitizada.

Si la inicialización falla, la fundación queda en `CONFIGURACION_PENDIENTE` y no se presenta como lista para operar.

Controles administrativos añadidos:

- solo `SUPERADMIN` crea o administra fundaciones;
- un administrador de fundación no puede crear otro `SUPERADMIN`;
- no se puede desactivar la propia sesión administrativa;
- debe permanecer al menos un `SUPERADMIN` activo;
- cambiar rol, fundación, contraseña o estado invalida sesiones anteriores;
- suspender una fundación invalida sus sesiones activas;
- no se puede suspender la fundación de la sesión actual.

## 5. Activos operativos preservados

Se conserva la funcionalidad de la versión 2.3.7:

- catálogo central de 32 UDS y alias;
- RPP sanitizado: 4 grupos, 49 productos y 17 equivalencias;
- RAM V2 histórica hasta julio de 2026;
- RAM V3 desde agosto de 2026;
- sincronización de plantillas por hash con respaldo;
- diagnóstico previo de formatos;
- diagnóstico del volumen `/data`;
- Acceso Compartido con URL pública de Railway.

Las plantillas oficiales versionadas y sus mapeos pasan a tener alcance por fundación cuando son personalizadas. Las semillas sanitizadas siguen siendo la fuente inicial común.

## 6. Variables obligatorias

Para activar el piloto de forma segura deben existir conjuntamente:

```env
SINGLE_TENANT_MODE=false
ALLOW_EXPERIMENTAL_MULTI_TENANT=true
MULTI_TENANT_STRICT=true
TENANT_STORAGE_ISOLATION=true
MULTI_TENANT_SCHEMA_VERSION=3
```

Producción rechaza el arranque si se desactiva alguna protección. Para regresar temporalmente al modo seguro de una sola fundación, use `SINGLE_TENANT_MODE=true`; no elimine columnas ni datos de tenant.

## 7. Validaciones realizadas

Se incluyeron pruebas puras con una base temporal y dos fundaciones ficticias para verificar:

- migración e integridad SQLite;
- documentos iguales permitidos entre fundaciones y bloqueados dentro de la misma;
- filtros automáticos en SQLite y SQLAlchemy Core;
- `INSERT`, `UPDATE` y `DELETE` limitados al tenant actual;
- rechazo de escritura cruzada;
- rechazo de `JOIN` sin alcance;
- rechazo de parámetros explícitos apuntando a otro tenant;
- directorios físicos diferentes;
- UDS, reglas y plantillas operativas separadas;
- catálogos globales intencionales preservados;
- configuración productiva fail-closed.

También se ejecutan las pruebas operativas heredadas de UDS, RPP, RAM y sincronización de plantillas.

## 8. Riesgos y límites pendientes

Esta entrega no equivale a una certificación definitiva. Falta validar en Railway:

1. ejecución completa con Flask, Gunicorn y Docker;
2. creación real de dos fundaciones desde la interfaz;
3. aislamiento de cada módulo usando usuarios distintos;
4. persistencia tras redeploy;
5. respaldo y restauración del volumen;
6. suspensión e invalidación inmediata de sesiones;
7. descargas, trabajos en segundo plano y archivos por tenant;
8. rendimiento de SQLite con carga concurrente;
9. revisión legal y organizativa de protección de datos.

Mientras SQLite siga siendo la base, mantenga una sola réplica y un solo worker Gunicorn.

## 9. Dictamen

La restricción visible de una sola fundación no dependía de comprar un plan de Railway: estaba controlada por configuración de la aplicación. Esta versión habilita la capacidad multi-fundación con defensas de aislamiento y una ruta de pruebas reproducible. Debe desplegarse primero en ensayo, con respaldo del volumen y datos completamente ficticios.

## 10. Resultado reproducible final

El validador incluido `tools/validate_release.py` finalizó con:

```text
17 PASS / 0 FAIL / 0 SKIP
```

Controles destacados:

- 146 archivos Python con sintaxis válida;
- 32 archivos JavaScript con sintaxis válida;
- 2 scripts Bash válidos;
- 8 archivos JSON válidos;
- 315 rutas API cubiertas por 55 familias de autorización;
- 9 plantillas sanitizadas verificadas por SHA-256;
- 7 archivos Office íntegros y sin relaciones externas;
- pruebas de migración, SQLite, SQLAlchemy Core, JOIN, parámetros cruzados, storage y flags aprobadas;
- directorios runtime vacíos y ausencia de bases, `.env`, logs y respaldos operativos.

El JSON reproducible se entrega como `VALIDACION_MULTIFUNDACION_v2_4_0.json`.
