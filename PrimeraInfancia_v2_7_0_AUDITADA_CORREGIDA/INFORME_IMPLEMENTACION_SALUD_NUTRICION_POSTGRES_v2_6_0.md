# Informe de implementación — PrimeraInfancia 2.6.0

## Salud y Nutrición Integral, PostgreSQL y lanzadores Windows corregidos

**Fecha de preparación:** 5 de agosto de 2026  
**Versión fuente:** PrimeraInfancia 2.5.4 — Supervisión, Familias y Redes  
**Versión resultante:** `2.6.0-salud-nutricion-postgresql`  
**Fuente funcional:** *Manual Técnico Modalidad Propia e Intercultural para la Atención a la Primera Infancia*, código MT3.PP, versión 2, 26/12/2025.

## 1. Alcance

La entrega atiende tres frentes que debían resolverse conjuntamente:

1. Evolución del componente Salud y Nutrición hacia un sistema integral por participante y UCA.
2. Preparación técnica y herramientas verificables para migrar de SQLite a PostgreSQL sin destruir el origen.
3. Sustitución de los scripts Windows frágiles por lanzadores pequeños, verificables y compatibles con inicio local y Cloudflare Quick Tunnel.

Se preservaron Base Maestra, RAM, RPP, Bienestarina, Pedagogía, Talento Humano, Familias y Redes, Supervisión, Biblioteca, Motor de Gestión, roles, rutas y aislamiento multi-fundación.

## 2. Diagnóstico de los scripts de inicio

El archivo BAT anterior concentraba detección de ruta, Python, entorno virtual, secretos, base, puerto, backend y navegador en un único archivo de cientos de líneas. La copia observada terminaba además con una instrucción truncada (`endloca`) y el intérprete CMD mostraba fragmentos como `t`, `not`, `r` y `et` como comandos independientes. Ese patrón es consistente con un BAT dañado por saltos de línea, codificación o truncamiento, no con la ausencia real de `backend/app.py`.

### Solución aplicada

Los BAT de entrada ahora son envoltorios ASCII con CRLF uniforme y menos de doce líneas:

- `INICIAR_PLATAFORMA_LOCAL.bat`
- `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat`
- `DETENER_PLATAFORMA_LOCAL.bat`

La lógica se trasladó a:

- `scripts_windows/iniciar_plataforma.ps1`
- `scripts_windows/detener_plataforma.ps1`
- `scripts_windows/iniciar_tunel_cloudflare.ps1`

El lanzador:

- resuelve la raíz desde su propia ubicación;
- verifica `backend/app.py` y `frontend/index.html`;
- admite Python 3.11 y 3.12;
- crea o repara `backend/.venv`;
- reinstala dependencias cuando cambia su SHA-256;
- distingue SQLite y PostgreSQL;
- genera secretos locales aleatorios fuera de Git;
- comprueba `/api/health`, la huella de la copia y el modo local/túnel;
- registra el PID del backend;
- no usa `/api/acceso/ping` como healthcheck;
- evita BAT extensos sensibles a codificación.

Se añadió `DIAGNOSTICAR_INICIO_WINDOWS.bat`, que informa rutas, Python, entorno virtual, escritura en `data`, puerto 5000, base configurada, health local, `cloudflared.exe`, `pg_dump.exe`, `pg_restore.exe` y logs recientes.

## 3. Arquitectura de base de datos

### 3.1 Gestor central

`backend/database.py` quedó como punto de configuración del Engine SQLAlchemy:

- SQLite para desarrollo, contingencia y migración.
- PostgreSQL mediante `postgresql+psycopg://` para concurrencia y producción.
- `pool_pre_ping`.
- tamaño de pool y overflow configurables.
- timeout de conexión y de obtención de conexión.
- reciclaje de conexiones.
- rollback al devolver la conexión.
- `statement_timeout` y `application_name`.
- zona horaria UTC.

### 3.2 Capa de compatibilidad

`backend/modules/dbapi_compat.py` conserva temporalmente la API histórica de `sqlite3` sobre PostgreSQL:

- placeholders `?` convertidos a parámetros nombrados;
- `sqlite_master` y `PRAGMA table_info` emulados;
- `INTEGER PRIMARY KEY AUTOINCREMENT` traducido a `BIGSERIAL PRIMARY KEY`;
- `INSERT OR IGNORE` traducido a `ON CONFLICT DO NOTHING`;
- `IFNULL`, `GROUP_CONCAT`, `strftime`, `printf`, fecha y hora traducidos;
- `lastrowid` mediante `RETURNING`;
- errores PostgreSQL expuestos de forma compatible;
- cortafuegos multi-fundación aplicado antes de ejecutar SQL;
- conexiones SQLite explícitas de pruebas, respaldo y migración conservadas como SQLite nativo.

Esta capa permite migración progresiva. No debe considerarse una razón para conservar indefinidamente SQL dependiente de SQLite.

## 4. Migración SQLite → PostgreSQL

Se añadió `backend/tools/migrate_sqlite_to_postgresql.py`. La herramienta:

1. verifica que el archivo SQLite exista;
2. ejecuta `PRAGMA integrity_check`;
3. crea una copia del origen sin modificarlo;
4. calcula SHA-256 del origen y del respaldo;
5. exige PostgreSQL vacío por defecto;
6. refleja tablas, columnas, claves y relaciones;
7. crea el esquema destino;
8. copia por lotes preservando identificadores;
9. difiere restricciones durante cada lote;
10. restablece secuencias;
11. compara conteos tabla por tabla;
12. produce un informe JSON;
13. se detiene en el primer error sin borrar SQLite.

Herramientas Windows:

- `CONFIGURAR_POSTGRESQL_LOCAL.bat`
- `MIGRAR_SQLITE_A_POSTGRESQL.bat`
- `RESPALDAR_POSTGRESQL.bat`
- `RESTAURAR_POSTGRESQL.bat`

La URL local se guarda únicamente en `.runtime_windows/database_url.local.txt`, carpeta excluida de la distribución y del repositorio.

## 5. Sistema Integral de Salud y Nutrición

El Manual Técnico organiza el componente en cinco líneas. La interfaz y el modelo se estructuraron para soportarlas:

1. Articulación para la atención en salud.
2. Educación para la Salud Alimentaria.
3. Prevención de enfermedades prevalentes.
4. Acceso y consumo de alimentos sanos y seguros con enfoque territorial.
5. Evaluación y seguimiento del estado nutricional.

### 5.1 Expediente integral

Se relaciona, sin copiar el participante:

- identidad y UCA;
- afiliación, EAPB y soportes;
- vacunación;
- valoración integral;
- salud bucal;
- control prenatal;
- tamizaje neonatal;
- discapacidad cuando aplique;
- lactancia y alimentación complementaria;
- estado documental;
- valoraciones y validaciones profesionales;
- canalizaciones, seguimientos y evidencias.

### 5.2 Historia antropométrica y CAPTURE

Las valoraciones existentes continúan siendo la fuente. Se añadió validación profesional versionada. El CAPTURE:

- se genera en XLSX o PDF;
- usa solamente datos validados;
- deja vacíos los campos sin dato válido;
- queda como `BORRADOR CONTROLADO`;
- registra usuario, fecha, plantilla, versión, tamaño y SHA-256;
- no emite diagnóstico clínico autónomo.

### 5.3 Jornadas y productos

El módulo gestiona jornadas, asistencia y evidencias. Puede preparar:

- acta PDF;
- listado XLSX;
- informe PDF;
- CAPTURE XLSX/PDF.

Los campos de análisis profesional no se inventan ni se cierran automáticamente.

### 5.4 Rutas y seguimientos

Las canalizaciones registran motivo, prioridad, entidad, responsable, fechas, actuaciones, próximo seguimiento y evidencia. El cierre requiere resultado y evidencia; la plataforma no toma decisiones clínicas o jurídicas.

## 6. Multi-fundación y privacidad

- Todas las tablas nuevas incluyen `fundacion_id`.
- Los roles operativos funcionan en modo fail-closed por UCA.
- Los productos y evidencias se guardan bajo `data/tenants/<fundacion_id>/`.
- No se exponen rutas físicas.
- No se registran contraseñas, tokens ni DATABASE_URL en logs.
- Las descargas verifican pertenencia al tenant y al almacenamiento autorizado.
- Los registros históricos se conservan; las correcciones se versionan.

## 7. Despliegue Railway

La imagen incorpora `postgresql-client` para `pg_dump` y `pg_restore`. `start_hosting.sh` mantiene un worker por defecto, parametrizable mediante `GUNICORN_WORKERS`; se recomienda conservar uno hasta externalizar los trabajos que aún usan memoria del proceso.

Variables mínimas:

- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `DATA_DIR=/data`
- variables iniciales de administrador solo cuando la base está vacía
- controles multi-fundación

## 8. Pruebas ejecutadas

Se ejecutaron pruebas verificables de:

- compatibilidad SQL PostgreSQL;
- preservación de SQLite explícito;
- traducciones SQL;
- scripts Windows y Quick Tunnel;
- módulo Salud y Nutrición Integral;
- migración: reflexión, integridad, SHA-256 y contrato de seguridad;
- autenticación concurrente SQLite;
- regresiones 2.4.0 a 2.5.4;
- aislamiento entre fundaciones;
- sintaxis Python, JavaScript, Bash y JSON;
- integridad de plantillas Office y manifiestos.

## 9. Límites reales

No se ejecutó en este entorno:

- un servidor PostgreSQL real;
- PowerShell 5.1 sobre Windows;
- `cloudflared.exe` contra la red real del usuario;
- Docker completo;
- Railway con volumen y usuarios concurrentes;
- navegador integral con todos los módulos.

Por tanto, la entrega es una **candidata técnicamente validada para pruebas controladas**, no una certificación de producción. La migración real debe ejecutarse primero sobre una copia y una base PostgreSQL de pruebas.
