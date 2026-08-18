# Guía segura de migración SQLite → PostgreSQL

## Regla principal

No migres directamente la única copia operativa. Trabaja con respaldo, PostgreSQL vacío y datos ficticios o una copia controlada.

## 1. Preparación

1. Detén backend y túnel.
2. Conserva la carpeta anterior completa.
3. Verifica que exista `data/database.sqlite3`.
4. Ejecuta `DIAGNOSTICAR_INICIO_WINDOWS.bat`.
5. Crea una base PostgreSQL de pruebas.
6. Conserva la URL privada fuera de Git.

## 2. Instalar herramientas

La aplicación instala `psycopg` dentro del entorno virtual. Para respaldo y restauración local necesitas PostgreSQL Client Tools con:

```text
pg_dump.exe
pg_restore.exe
```

## 3. Configurar PostgreSQL local

Ejecuta:

```text
CONFIGURAR_POSTGRESQL_LOCAL.bat
```

La herramienta comprueba `SELECT 1` y guarda la URL en:

```text
.runtime_windows/database_url.local.txt
```

## 4. Migrar

Ejecuta:

```text
MIGRAR_SQLITE_A_POSTGRESQL.bat
```

Escribe `MIGRAR` cuando lo solicite. La herramienta crea:

- respaldo SQLite;
- SHA-256;
- esquema PostgreSQL;
- copia por lotes;
- verificación de conteos;
- restablecimiento de secuencias;
- reporte JSON.

No uses `--truncate-target` salvo que la base destino sea exclusivamente de pruebas y aceptes borrar su contenido.

## 5. Validación mínima

1. Ejecuta `INICIAR_PLATAFORMA_LOCAL.bat`.
2. Confirma en `/api/health`:

```json
{"status":"ok","database_backend":"postgresql"}
```

3. Prueba login con dos navegadores.
4. Verifica fundaciones y UCA.
5. Compara Base Maestra, RAM, RPP y Bienestarina.
6. Prueba Salud y Nutrición, CAPTURE y reportes.
7. Genera un respaldo PostgreSQL.
8. Reinicia y confirma persistencia.

## 6. Railway

1. Crea un servicio PostgreSQL de pruebas.
2. Configura `DATABASE_URL` y secretos.
3. Mantén `/data` para archivos, plantillas y evidencias.
4. Despliega en una rama o servicio separado.
5. Ejecuta la migración desde un entorno autorizado.
6. Verifica conteos, login, módulos y archivos.
7. Solo después cambia tráfico o dominio.

## 7. Respaldo y restauración

```text
RESPALDAR_POSTGRESQL.bat
RESTAURAR_POSTGRESQL.bat
```

La restauración usa `--clean --if-exists` y debe ejecutarse únicamente en ventana de mantenimiento.

## 8. Volver a SQLite local

1. Detén la plataforma.
2. Renombra o elimina `.runtime_windows/database_url.local.txt`.
3. Conserva intacto `data/database.sqlite3`.
4. Ejecuta el inicio local.

Esto no revierte cambios nuevos realizados únicamente en PostgreSQL. Por eso no debes operar simultáneamente ambas bases después del corte definitivo.
