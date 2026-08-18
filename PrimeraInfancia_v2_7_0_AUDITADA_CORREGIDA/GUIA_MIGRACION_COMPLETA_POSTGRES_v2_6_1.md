# Guía — Migración completa SQLite → PostgreSQL 2.6.1

## Advertencia

Realice primero la migración sobre una copia de la base y un PostgreSQL vacío de pruebas. No cambie `DATABASE_URL` productiva hasta que conteos, huellas, pruebas funcionales y restauración hayan sido aprobados.

## 1. Requisitos

- PostgreSQL 16 recomendado.
- Python 3.12.
- Dependencias de `backend/requirements-production.txt`.
- Acceso de lectura al SQLite vigente.
- Usuario PostgreSQL con capacidad de crear tablas, secuencias, índices y restricciones en el esquema destino.
- Espacio suficiente para dos respaldos.

## 2. Conservar el origen

Detenga temporalmente las escrituras o utilice una ventana de mantenimiento. La herramienta genera un snapshot consistente, pero el corte final debe evitar que aparezcan registros nuevos después del snapshot.

## 3. Comando Windows guiado

Ejecute:

```text
MIGRAR_COMPLETO_A_POSTGRESQL.bat
```

El asistente solicita la URL PostgreSQL, ejecuta todo el corte y solo guarda la URL local si todos los controles pasan.

## 4. Comando directo

```powershell
python backend/tools/postgresql_cutover.py `
  --sqlite C:\PI\data\database.sqlite3 `
  --postgres "postgresql+psycopg://USUARIO:CLAVE@HOST:5432/BASE" `
  --report-dir data/migration_reports/cutover `
  --activate-env-file .runtime_windows/database_url.local.txt
```

## 5. Etapas automáticas

### Preflight

Comprueba conexión, versión, base, usuario, escritura y esquema.

### Auditoría SQL runtime

Bloquea la migración si encuentra SQL no soportado o importaciones directas de SQLite fuera de la capa autorizada.

### Snapshot

Crea una copia consistente mediante la API de respaldo SQLite y valida `PRAGMA integrity_check`.

### Copia

- refleja el esquema;
- crea tablas e índices;
- copia por lotes;
- conserva identificadores;
- restablece secuencias.

### Verificación

- compara tablas;
- compara cantidad de filas;
- calcula huella SHA-256 determinística de cada tabla;
- verifica restricciones foráneas no validadas.

### Gate

Ejecuta la regresión completa antes de marcar el corte como `READY`.

## 6. Verificar una migración ya realizada

```text
VERIFICAR_MIGRACION_POSTGRESQL.bat
```

O:

```powershell
python backend/tools/postgresql_cutover.py `
  --sqlite C:\PI\data\database.sqlite3 `
  --postgres "postgresql+psycopg://..." `
  --verify-existing
```

## 7. Railway

### Ruta recomendada

1. Crear un servicio PostgreSQL independiente de pruebas.
2. Ejecutar la migración desde un equipo o job temporal que tenga acceso tanto al SQLite como a PostgreSQL.
3. Revisar los reportes JSON.
4. Configurar `DATABASE_URL` en el servicio de pruebas.
5. Desplegar.
6. Verificar `/api/ready`.
7. Ejecutar login y pruebas por módulo.
8. Tomar `pg_dump` después de aprobar.
9. Repetir el procedimiento controlado para producción.

### Variables mínimas

```env
APP_ENV=production
DATABASE_URL=postgresql://...
REQUIRE_POSTGRESQL_IN_PRODUCTION=true
SECRET_KEY=<aleatoria>
JWT_SECRET_KEY=<aleatoria y distinta>
```

Las variables `INITIAL_ADMIN_*` solo son necesarias cuando el PostgreSQL está vacío y se requiere crear la primera cuenta.

## 8. Verificación funcional obligatoria

- login y cierre de sesión;
- dos fundaciones aisladas;
- usuarios con UCA asignadas;
- Base Maestra;
- Expediente UCA;
- RAM y RAN;
- RPP;
- Bienestarina;
- listados de asistencia;
- Salud y Nutrición;
- Pedagogía;
- Talento Humano;
- Familias y Redes;
- Supervisión y Calidad;
- Biblioteca y Motor de Gestión;
- paquetes mensuales;
- backups y restauración.

## 9. Evidencias producidas

```text
data/migration_reports/cutover/cutover_*.json
data/migration_reports/cutover/preflight_*.json
data/migration_reports/cutover/runtime_sql_*.json
data/migration_reports/cutover/migration_*.json
data/migration_reports/cutover/verification_*.json
data/migration_reports/cutover/integrity_gate_*.json
```

## 10. Prohibiciones

- No eliminar el SQLite después de la primera migración.
- No usar `--truncate-target` sin respaldo y aprobación.
- No activar la URL si el manifest queda `BLOCKED`.
- No realizar escrituras simultáneas en SQLite después del snapshot de corte.
- No ejecutar una migración automática desde Safe Repair.
