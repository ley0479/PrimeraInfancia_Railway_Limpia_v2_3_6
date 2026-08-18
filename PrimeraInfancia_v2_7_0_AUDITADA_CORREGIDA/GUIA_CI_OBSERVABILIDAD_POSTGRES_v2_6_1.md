# Guía — CI, observabilidad y operación PostgreSQL 2.6.1

## 1. Workflow

Archivo:

```text
.github/workflows/integrity-ci.yml
```

Se ejecuta en pull requests, pushes a ramas principales y ejecución manual.

## 2. Controles de CI

1. Instala Python 3.12 y Node 22.
2. Levanta PostgreSQL 16 como servicio.
3. Ejecuta preflight.
4. Crea una base SQLite limpia de prueba.
5. Migra la base a PostgreSQL real del job.
6. Verifica filas y huellas.
7. Inicializa y prueba la aplicación contra PostgreSQL.
8. Ejecuta el Motor de Integridad.
9. Genera un plan de reparación segura.
10. Publica evidencias JSON.
11. Finaliza en el job `Deployment Gate`.

## 3. Bloqueo real del despliegue

El workflow por sí solo reporta estado. Para que bloquee merges:

- active protección de rama o ruleset;
- exija pull request;
- agregue `Deployment Gate` como status check obligatorio;
- impida merge cuando el check esté pendiente o fallido;
- conecte Railway únicamente a la rama protegida o a un workflow posterior dependiente del gate.

## 4. Ejecución local del gate

```text
EJECUTAR_GATE_INTEGRIDAD.bat
```

O:

```powershell
python backend/tools/integrity_gate.py --root . --report data/integrity/integrity_gate.json
```

## 5. Reparación segura

Plan:

```text
REPARACION_SEGURA.bat
```

La opción de aplicar requiere confirmación. Nunca modifica datos de negocio.

## 6. Monitoreo local

```text
MONITOREAR_PLATAFORMA.bat
```

El monitor consulta readiness y guarda muestras técnicas. No debe utilizarse para copiar información de participantes.

## 7. Endpoints

### Readiness

```text
GET /api/ready
```

Devuelve 200 solo si la base responde dentro del límite configurado.

### Estado del motor

```text
GET /api/integrity/status
```

Requiere rol de coordinación.

### Métricas

```text
GET /api/integrity/metrics
X-Metrics-Token: <token>
```

Si no se configura token, requiere usuario autenticado con rol autorizado.

## 8. Métricas incluidas

- uptime;
- solicitudes totales;
- respuestas 5xx;
- latencia media y máxima;
- conteos por estado HTTP;
- top de rutas normalizadas;
- conectividad y latencia de base;
- estado del pool.

## 9. Alertas recomendadas

| Señal | Umbral inicial |
|---|---:|
| `/api/ready` no disponible | 2 comprobaciones consecutivas |
| Error rate 5xx | > 2 % durante 5 minutos |
| Latencia p95 | > 2 s durante 5 minutos |
| Pool sin conexiones disponibles | cualquier ocurrencia repetida |
| Gate bloqueado | inmediata |
| Backup PostgreSQL vencido | > 24 horas en producción |

Los umbrales deben ajustarse después de medir tráfico real.

## 10. Limitaciones actuales

- Las métricas son por proceso y residen en memoria.
- Un reinicio reinicia los contadores.
- Se mantiene un worker por defecto por la existencia de jobs en memoria.
- Para escalar horizontalmente se requiere externalizar jobs, métricas y coordinación distribuida.
