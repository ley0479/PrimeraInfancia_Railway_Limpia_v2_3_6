# Arquitectura — PrimeraInfancia 2.6.0

## 1. Capas

```text
Navegador / roles
        │
        ▼
Flask API y autorización fail-closed
        │
        ├── Salud y Nutrición Integral
        ├── Base Maestra / RAM / RPP / Bienestarina
        ├── Expediente UCA / Motor / Supervisión
        └── demás módulos existentes
        │
        ▼
Cortafuegos SQL multi-fundación
        │
        ▼
DB-API Compatibility Layer
        │
        ▼
SQLAlchemy Engine / Pool
        ├── SQLite (local, respaldo, origen de migración)
        └── PostgreSQL + psycopg (producción recomendada)
```

## 2. Decisiones

- Un único Engine por proceso.
- PostgreSQL normalizado a `postgresql+psycopg://`.
- Compatibilidad temporal con consultas `sqlite3` históricas.
- Nuevos desarrollos no deben añadir SQL exclusivo de SQLite.
- La fuente del participante permanece en Base Maestra.
- Salud Integral almacena referencias y actuaciones propias, no copias del participante.
- Evidencias y productos se aíslan por tenant.
- Aprobación, cierre y diagnóstico permanecen bajo decisión humana.

## 3. Pool PostgreSQL

```text
DB_POOL_SIZE=8
DB_MAX_OVERFLOW=12
DB_POOL_TIMEOUT_SECONDS=15
DB_POOL_RECYCLE_SECONDS=1200
DB_CONNECT_TIMEOUT_SECONDS=10
DB_STATEMENT_TIMEOUT_MS=30000
DB_APPLICATION_NAME=primera-infancia-2.6.0
```

## 4. Transacciones

- Cada unidad de trabajo abre una transacción corta.
- El pool devuelve conexiones con rollback.
- Las operaciones de login mantienen su presupuesto de reintentos.
- La migración copia por lotes y valida cada tabla.
- El origen SQLite nunca se elimina automáticamente.

## 5. Datos de Salud y Nutrición

Tablas nuevas:

- `sn_expedientes_integrales`
- `sn_documentos_salud`
- `sn_valoracion_validaciones`
- `sn_actividades_integrales`
- `sn_actividad_participantes`
- `sn_productos_actividad`
- `sn_canalizaciones`
- `sn_seguimientos_integrales`
- `sn_evidencias_integrales`

Los datos antropométricos base continúan en las tablas existentes; las validaciones profesionales referencian la valoración original.

## 6. Inicio Windows

```text
BAT pequeño CRLF
      │
      ▼
scripts_windows/iniciar_plataforma.ps1
      ├── ruta y archivos
      ├── Python / venv / dependencias
      ├── SQLite o PostgreSQL
      ├── secretos privados
      ├── init_hosting
      ├── puerto / PID
      ├── backend
      └── /api/health + huella de instancia
                    │
                    └── Cloudflare Quick Tunnel cuando corresponde
```

## 7. Reversibilidad

- Mantener la base SQLite original y su SHA-256.
- No activar PostgreSQL en producción hasta validar conteos y módulos.
- Eliminar `.runtime_windows/database_url.local.txt` para volver localmente a SQLite.
- En Railway, restaurar la variable `DATABASE_URL` anterior y el respaldo correspondiente.
