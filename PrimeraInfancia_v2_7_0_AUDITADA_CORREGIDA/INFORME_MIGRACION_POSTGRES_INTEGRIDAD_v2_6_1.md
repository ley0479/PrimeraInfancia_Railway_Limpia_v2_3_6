# Informe de migración PostgreSQL e integridad — PrimeraInfancia 2.6.1

**Fecha:** 6 de agosto de 2026  
**Versión base estable:** 2.6.0 — Salud y Nutrición Integral, compatibilidad PostgreSQL y scripts corregidos  
**Versión candidata:** 2.6.1 — PostgreSQL, Integridad, Supervisión y Estabilidad

## 1. Alcance ejecutado

Se continuó desde el estado técnico de la versión 2.6.0. No se reinició el desarrollo ni se reemplazaron los módulos existentes. El trabajo pendiente se concentró en dos frentes:

1. Completar el proceso técnico y verificable de transición desde SQLite hacia PostgreSQL.
2. Incorporar un Motor Inteligente de Integridad, Supervisión y Estabilidad que compare cada cambio contra la línea base estable, ejecute regresión y bloquee el despliegue cuando se pierda una capacidad crítica.

La entrega preserva Base Maestra, autenticación, multi-fundación, Expediente UCA, Biblioteca Oficial, Motor de Gestión, Supervisión, Familias y Redes, Salud y Nutrición, Pedagogía, Talento Humano, RAM, RAN, RPP, Bienestarina, listados de asistencia y reportes.

## 2. Estado real de la migración

La aplicación y las herramientas quedaron preparadas para realizar una migración completa y verificable. Sin embargo, **no se migró una base productiva real**, porque durante la preparación no se proporcionaron:

- la URL o credenciales de un servidor PostgreSQL real;
- acceso al volumen productivo que contiene el SQLite vigente;
- autorización para ejecutar un corte de servicio;
- una ventana de mantenimiento y plan de aprobación institucional.

Por tanto, el resultado es un paquete de corte controlado, no una afirmación falsa de que los datos de producción ya fueron transferidos.

## 3. Diagnóstico de dependencias SQLite

La auditoría estática examinó los literales SQL del backend operativo y verificó:

- ausencia de importaciones directas de `sqlite3` fuera de las capas expresamente autorizadas;
- detección de construcciones históricas SQLite;
- contrato de traducción para `PRAGMA`, `sqlite_master`, `AUTOINCREMENT`, `INSERT OR IGNORE`, `IFNULL`, `GROUP_CONCAT`, `strftime`, `julianday`, `printf`, `last_insert_rowid`, `COLLATE NOCASE` y fechas `now`;
- bloqueo de construcciones no soportadas como `INSERT OR REPLACE`, `GLOB`, funciones JSON SQLite, `VACUUM INTO`, `WITHOUT ROWID` y variantes de `LIMIT` no portables.

La auditoría actual encontró las construcciones heredadas cubiertas por la capa de compatibilidad y no detectó construcciones no soportadas dentro del runtime analizado.

## 4. Herramienta de migración completa

La migración usa un proceso no destructivo:

```text
SQLite operativo
    ↓ snapshot consistente mediante SQLite backup API
Respaldo con SHA-256
    ↓
Preflight PostgreSQL
    ↓
Creación/reflexión del esquema
    ↓
Copia por lotes conservando identificadores
    ↓
Restablecimiento de secuencias
    ↓
Verificación de conteos y huellas por tabla
    ↓
Validación de claves foráneas
    ↓
Gate de integridad y regresión
    ↓
Activación explícita de DATABASE_URL
```

### Garantías

- El SQLite original nunca se elimina.
- El snapshot se crea de forma consistente incluso cuando la base usa WAL.
- Se calcula SHA-256 del origen y del snapshot.
- El destino debe estar vacío, salvo que el operador habilite conscientemente otro modo.
- Si el destino estaba vacío y la migración falla, las tablas recién creadas pueden limpiarse sin tocar el origen.
- La activación de PostgreSQL solo ocurre después de que todos los pasos terminen en `PASS`.
- La URL se enmascara en reportes.

## 5. Motor de Integridad, Supervisión y Estabilidad

El motor incorpora una línea base versionada de la versión 2.6.0. La línea base protege:

- archivos y módulos críticos;
- rutas API críticas;
- roles estables;
- capacidades RAM, RAN, RPP, Bienestarina y listados de asistencia;
- plantillas oficiales y sus huellas SHA-256;
- contrato multi-fundación y esquema mínimo;
- backend productivo PostgreSQL.

### Gate de despliegue

El gate ejecuta:

1. Contrato de archivos, módulos, rutas, roles y formatos.
2. Sintaxis Python.
3. Sintaxis JavaScript cuando Node está disponible.
4. Auditoría de SQL runtime para PostgreSQL.
5. Pruebas críticas heredadas.
6. Validación del manifiesto en el paquete final.

Un fallo bloqueante produce estado:

```text
BLOCKED
```

El proceso termina con código distinto de cero, de modo que CI pueda impedir la promoción del cambio.

## 6. Autorreparación segura

La reparación automática está limitada a:

- borrar bytecode y cachés Python;
- retirar archivos temporales antiguos;
- rotar logs sobredimensionados;
- retirar artefactos runtime seguros;
- revertir transacciones fallidas mediante el manejo transaccional normal.

Está prohibido:

- cambiar reglas de negocio;
- modificar roles o permisos;
- eliminar participantes;
- alterar formatos oficiales;
- cerrar hallazgos o alertas;
- reescribir históricos;
- aplicar migraciones productivas automáticamente.

Por defecto la herramienta solo produce un plan. Requiere `--apply` o una confirmación equivalente para ejecutar las acciones permitidas.

## 7. Observabilidad incorporada

La plataforma agrega:

- correlación mediante `X-Request-ID`;
- tiempos mediante `Server-Timing`;
- métricas agregadas de solicitudes, errores y latencia;
- estado y uso del pool de conexiones;
- alertas estructuradas para respuestas 5xx y solicitudes lentas;
- endpoint de readiness que verifica base y latencia;
- métricas Prometheus protegidas por cabecera o rol autorizado.

No se registran cuerpos, cookies, contraseñas, tokens ni datos de participantes.

## 8. Endpoints operativos

```text
GET  /api/ready
GET  /api/integrity/health
GET  /api/integrity/status
GET  /api/integrity/architecture
POST /api/integrity/run
POST /api/integrity/safe-repair
GET  /api/integrity/metrics
```

Las operaciones de ejecución requieren roles de coordinación. La aplicación de reparación segura queda limitada a `SUPERADMIN`.

## 9. CI con GitHub Actions

Se incorporó `.github/workflows/integrity-ci.yml` con:

- Python 3.12;
- Node 22;
- servicio PostgreSQL 16;
- preflight real contra PostgreSQL;
- construcción de un SQLite limpio;
- migración a PostgreSQL;
- verificación de datos;
- smoke test del backend usando PostgreSQL;
- gate completo de integridad;
- plan de reparación segura;
- publicación de evidencias JSON como artefactos;
- trabajo final denominado `Deployment Gate`.

Para bloquear efectivamente merges o despliegues, el repositorio debe configurar `Deployment Gate` como verificación obligatoria de la rama protegida.

## 10. Configuración productiva

En producción:

```env
DATABASE_URL=postgresql://...
REQUIRE_POSTGRESQL_IN_PRODUCTION=true
INTEGRITY_ENGINE_ENABLED=true
METRICS_ENABLED=true
```

Railway consulta:

```text
/api/ready
```

El inicio productivo ejecuta preflight PostgreSQL y gate rápido antes de inicializar el esquema y levantar Gunicorn.

## 11. Límites pendientes

No fue posible ejecutar en el entorno de preparación:

- PostgreSQL real;
- `psycopg` contra un servidor activo;
- PowerShell sobre Windows;
- Docker completo;
- Railway con volumen y tráfico reales;
- GitHub Actions dentro del repositorio del usuario.

Estas pruebas están automatizadas en CI o documentadas para el entorno de pruebas. La promoción a producción debe realizarse solo después de aprobar la migración contra una copia real de la base y verificar respaldo/restauración.
