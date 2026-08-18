# Calendario, checklist y documentos — implementación incremental 2.7.0

## Arquitectura

El módulo `calendario_inteligente` es una capa de orquestación. Consume Base
Maestra, Talento Humano y el generador oficial RAM existente; no replica esas
fuentes. PostgreSQL es la fuente runtime. Los archivos se guardan bajo el
almacenamiento del tenant y nunca se expone la ruta física.

Flujo principal:

`calendario → obligación → requisitos → formato/evidencia → revisión → aprobación → cumplimiento`

## Tablas utilizadas

- `calendario_entregables`: eventos, recurrencias, responsables y UDS.
- `calendario_cronogramas`: importaciones y vista previa humana.
- `calendario_obligaciones`, `calendario_requisitos`, `calendario_asignaciones`:
  checklist institucional, fecha sugerida o pendiente y aplicación por UDS/rol.
- `calendario_evidencias`: originales seguros, versión, MIME, tamaño, SHA-256,
  estado de revisión y tenant.
- `calendario_alertas`: recordatorios idempotentes por evento, usuario, tipo y
  fecha programada.
- `calendario_auditoria`: eventos operacionales del módulo.

Las migraciones son aditivas, idempotentes y se ejecutan en el startup
controlado. No se elimina ni trunca información.

## Estados

- Importación: `LISTO_PARA_REVISION`, `APROBADO`, `ERROR` cuando aplica.
- Checklist: `PENDIENTE`, `EN_PROGRESO`, `ENTREGADO`, `APROBADO`, `DEVUELTO`,
  `NO_APLICA` justificado.
- Evidencia: `CARGADA`, `APROBADA`, `DEVUELTA`.
- Fecha importada: `ASIGNADA` o `PENDIENTE_ASIGNACION`.

## Endpoints nuevos conservando los existentes

| URL | Método | Contrato principal |
|---|---|---|
| `/api/calendario-inteligente/checklist` | GET/POST | Lista o crea obligación; coordinación para crear |
| `/checklist/{id}/estado` | PATCH | Cambio de estado, propiedad/rol y tenant |
| `/checklist/importar` | POST | Word/Excel/PowerPoint/PDF a propuestas |
| `/checklist/importar/{id}/confirmar` | POST | Incorpora solo propuestas revisadas |
| `/evidencias/{tipo}/{id}` | GET/POST | Historial o carga múltiple segura |
| `/evidencias/{tipo}/{id}/enviar` | POST | Envía a revisión con evidencia real |
| `/evidencias/{tipo}/{id}/revision` | PATCH | Coordinación aprueba/devuelve; devolución motivada |
| `/evidencias/{id}/descargar` | GET | Descarga autorizada con verificación SHA-256 |
| `/cumplimiento?periodo=AAAA-MM` | GET | Indicadores reales multidimensionales |
| `/api/descargar/{uds}/ram?mes=M&anio=A` | GET | Generador RAM oficial preexistente reutilizado |

Respuestas funcionales usan 400/401/403/404/409/422; los errores inesperados
permanecen como 500 con detalle técnico solo en logs.

## Lector documental

Soporta Excel, Word, PowerPoint y PDF con texto; PDF/imagen escaneada usa OCR si
las dependencias locales están disponibles. Siempre produce propuestas con
origen, confianza, advertencias y vista previa. Una fecha ausente permanece como
`FECHA PENDIENTE DE ASIGNACIÓN`.

## RAM y motor universal

Se reutiliza `GeneradorFormatos` y la plantilla oficial versionada. El mapa real
está en [AUDITORIA_PLANTILLA_RAM_V3.md](AUDITORIA_PLANTILLA_RAM_V3.md). Se
generan páginas adicionales cada 20 participantes y no se inventan asistencias.
RAN/RRAN sigue bloqueado hasta recibir su propia plantilla oficial.

## Seguridad

- Autenticación y tenant comprobados en backend.
- Propiedad del entregable/asignación para usuarios no coordinadores.
- Extensión, MIME, nombre seguro, tamaño máximo 50 MB y SHA-256.
- Descarga por ID; sin rutas físicas en JSON.
- Pruebas con Fundación A/B sin cruces de calendario, checklist, evidencia,
  alertas ni indicadores.

## Fórmula de cumplimiento

`obligaciones aprobadas / obligaciones exigibles × 100`.

`NO_APLICA` exige motivo, usuario y fecha y se excluye del denominador.

## Matriz de regresión ejecutada

| Funcionalidad | Antes | Después | Regresión |
|---|---:|---:|---:|
| Login y seguridad | PASS | PASS | No detectada |
| Panel principal | PASS | PASS | No detectada |
| Base Maestra / UDS | PASS | PASS | No detectada |
| Multi-tenant | PASS | PASS | No detectada |
| Formatos existentes | PASS | PASS | No detectada |
| RAM oficial y paginación | PASS | PASS | No detectada |
| Calendario mes/semana/año/agenda | PASS | PASS | No detectada |
| Checklist / evidencias / revisión | N/A | PASS | N/A |
| Lector documental | Parcial | PASS en formatos probados | No detectada |
| Alertas idempotentes | N/A | PASS | N/A |
| Cumplimiento por dimensiones | N/A | PASS | N/A |

## Evidencia de pruebas

Los reportes por gate se encuentran en `.runtime_windows/phase*_integrity_after.json`.
El gate más reciente ejecuta 32 pruebas críticas, sintaxis Python/JavaScript,
contratos PostgreSQL, plantillas oficiales y funcionalidades protegidas.

## Pendientes de validación externa

- Railway no puede probarse desde esta estación sin una URL/despliegue y acceso
  autorizados. Se verificó compatibilidad PostgreSQL y startup local, pero no se
  declara validación de producción.
- La auditoría estática de Railway sí pasó: normalización de `DATABASE_URL`,
  codificación de variables `PG*`, PostgreSQL obligatorio, orden de migración
  antes de Gunicorn, workers sin DDL, healthcheck `/api/ready`, volumen
  persistente y ejecución no-root. Esta estación no dispone de Docker ni de
  Railway CLI, por lo que no puede construir ni consultar el despliegue remoto.
- RAN/RRAN requiere una plantilla oficial independiente; no se reconstruye ni
  se deriva de RAM.
