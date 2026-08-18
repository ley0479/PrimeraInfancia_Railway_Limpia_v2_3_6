# Arquitectura — Motor de Integridad, Supervisión y Estabilidad 2.6.1

## 1. Objetivo

Crear una capa transversal que conozca el contrato funcional de la plataforma y detecte regresiones sin interferir con la lógica de negocio.

## 2. Componentes

```text
integrity/
├── baseline_v2_6_0.json
├── critical_tests.json
└── safe_autofix_policy.json

backend/tools/
├── integrity_gate.py
├── postgresql_runtime_audit.py
├── postgresql_preflight.py
├── postgresql_cutover.py
├── verify_sqlite_postgresql.py
├── safe_repair.py
├── runtime_monitor.py
└── capture_integrity_baseline.py

backend/modules/integrity_stability/
├── routes.py
└── service.py

backend/services/
└── observability.py
```

## 3. Línea base estable

La línea base 2.6.0 describe capacidades, no datos personales. Incluye:

- módulos críticos;
- rutas críticas;
- roles;
- formatos operativos;
- huellas de plantillas oficiales;
- contrato de base de datos;
- archivos de arranque y despliegue.

Las mejoras posteriores se comparan contra esta línea. Agregar capacidades es válido; perder una capacidad estable bloquea el gate.

## 4. Flujo de un cambio

```text
Cambio propuesto
      ↓
Sintaxis y contrato arquitectónico
      ↓
Auditoría SQL PostgreSQL
      ↓
Pruebas de regresión
      ↓
Comparación con línea base
      ↓
PASS ───────────────→ candidato a despliegue
FAIL ───────────────→ despliegue bloqueado
```

## 5. Separación de responsabilidades

### Gate

Solo lee archivos y ejecuta pruebas. No modifica datos.

### Safe Repair

Solo actúa sobre cachés, temporales y logs dentro de la política permitida.

### Cutover PostgreSQL

Es un orquestador independiente. Nunca es ejecutado automáticamente por Safe Repair.

### Aplicación

Expone el estado del gate y de la base, pero no modifica la línea base ni aprueba su propia versión.

## 6. Observabilidad

La instrumentación se instala en Flask mediante `before_request` y `after_request`:

- genera o preserva un identificador de solicitud;
- mide latencia;
- cuenta estados HTTP;
- registra rutas normalizadas, no URLs con parámetros;
- produce métricas Prometheus;
- agrega estado del pool y la base.

Las métricas residen en memoria y se reinician al reiniciar el proceso. Para alta disponibilidad futura se recomienda enviarlas a un sistema externo.

## 7. Readiness y health

- `/api/health`: identidad, versión, modo y salud general.
- `/api/ready`: base conectada y latencia dentro del límite.
- `/api/integrity/health`: disponibilidad del módulo de integridad.

Railway usa `/api/ready` para evitar enviar tráfico a una instancia cuya base no está lista.

## 8. Concurrencia PostgreSQL

El `DatabaseManager` configura:

- `pool_pre_ping`;
- tamaño del pool;
- overflow controlado;
- timeout de adquisición;
- reciclaje;
- timeout de conexión;
- timeout de sentencias;
- zona horaria UTC;
- rollback al devolver conexiones;
- reintentos limitados para serialización, deadlock o lock transitorio.

No se reintentan indiscriminadamente errores de negocio o integridad.

## 9. Riesgos controlados

| Riesgo | Control |
|---|---|
| Pérdida de módulos existentes | Baseline y pruebas críticas |
| SQL exclusivo de SQLite | Auditoría AST y traductor explícito |
| Migración incompleta | Conteos, huellas y FK |
| Activación prematura | Cutover activa URL solo tras PASS |
| Reparación destructiva | Política allowlist/denylist |
| Métricas expuestas | Token en cabecera o rol autorizado |
| Datos sensibles en logs | Solo metadatos técnicos y rutas normalizadas |
| Despliegue con base caída | Readiness PostgreSQL |

## 10. Evolución recomendada

1. Externalizar métricas a Prometheus/OpenTelemetry.
2. Externalizar jobs en memoria antes de aumentar workers.
3. Convertir gradualmente SQL heredado a SQLAlchemy nativo.
4. Añadir pruebas E2E de navegador.
5. Configurar ambientes independientes: desarrollo, pruebas, preproducción y producción.
