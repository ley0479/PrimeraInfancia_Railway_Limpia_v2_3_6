# Informe de implementación — Biblioteca Oficial ICBF y Motor Inteligente de Gestión

**Versión resultante:** PrimeraInfancia 2.5.3 — Biblioteca y Motor de Gestión  
**Versión base:** PrimeraInfancia 2.5.2 — Expediente Operativo central por UCA  
**Fecha:** 5 de agosto de 2026

## 1. Alcance

Se implementaron dos capacidades complementarias:

1. **Biblioteca Oficial ICBF ampliada**, con control de fuentes, versiones candidatas, revisión humana, historial, notificaciones y relaciones con módulos.
2. **Motor Inteligente de Gestión del Proyecto**, que consolida referencias a tareas y entregables de los módulos existentes, calcula prioridades, genera recordatorios y prepara productos operativos en estado borrador.

No se creó una segunda Base Maestra ni se copiaron participantes, valoraciones, planeaciones, entregables o evidencias. La integración conserva una fuente única por módulo y guarda únicamente referencias de orquestación.

## 2. Biblioteca Oficial ICBF

### 2.1 Modelo de actualización controlada

La Biblioteca mantiene cuatro niveles:

- **Fuente:** mecanismo y ubicación autorizada.
- **Candidato:** metadatos de una posible versión nueva.
- **Versión:** registro documental revisado.
- **Versión vigente:** activación explícita posterior a verificación.

Una detección remota o importación manual nunca sustituye automáticamente la versión vigente. El flujo es:

```text
Fuente autorizada
      ↓
Detección de candidato
      ↓
Revisión administrativa
      ↓
Aprobación de metadatos
      ↓
Carga/verificación de archivo o fuente institucional
      ↓
Activación explícita
      ↓
Versión anterior pasa a histórica
```

### 2.2 Integración futura segura

La consulta remota queda deshabilitada de forma predeterminada. Para habilitarla se requiere:

- `BIBLIOTECA_REMOTE_CHECKS_ENABLED=true`.
- Fuente marcada como autorizada y habilitada.
- Mecanismo `CATALOGO_JSON`.
- URL HTTPS sin credenciales embebidas.
- Dominio incluido en `BIBLIOTECA_ALLOWED_DOMAINS`.
- Resolución DNS hacia una dirección pública.
- Respuesta JSON con contrato documentado.

No se implementó scraping de intranet ni automatización sobre mecanismos no autorizados.

### 2.3 Trazabilidad

Se añadieron:

- `biblioteca_icbf_fuentes`.
- `biblioteca_icbf_candidatos`.
- `biblioteca_icbf_notificaciones`.
- `biblioteca_icbf_historial`.

Cada acción conserva fundación, usuario, fecha, estado anterior, estado nuevo y detalle técnico.

### 2.4 Relación con módulos

El sistema propone relaciones según código, nombre, componente y descripción. La propuesta es revisable y puede vincular documentos con:

- Expediente Operativo por UCA.
- Motor de Gestión.
- Salud y Nutrición.
- Gestión Pedagógica.
- Talento Humano.
- Formatos ICBF.
- Reportes Gerenciales.
- Biblioteca Oficial.

La activación de una versión genera notificaciones para los módulos vinculados. No regenera automáticamente productos históricos.

## 3. Motor Inteligente de Gestión del Proyecto

### 3.1 Principio de arquitectura

El motor es una capa de orquestación. No reemplaza los módulos fuente y no modifica sus registros originales. Construye tareas referenciales a partir de:

- Ruta Operativa y planes del Expediente UCA.
- Calendario Inteligente.
- Gestión Pedagógica.
- Salud y Nutrición.
- Entregables operativos disponibles.

Cada tarea utiliza una clave única por fundación, tabla y registro fuente. La sincronización es idempotente.

### 3.2 Capacidades

- Tareas manuales controladas.
- Responsables, revisores y aprobadores.
- Estados y fechas.
- Priorización por reglas.
- Dependencias obligatorias.
- Bloqueos visibles.
- Recordatorios.
- Tablero por periodo.
- Filtrado por rol.
- Productos operativos.
- Cierre mensual.
- Auditoría.

### 3.3 Reglas iniciales

- Tarea vencida: prioridad crítica.
- Vencimiento dentro de 48 horas: prioridad alta.
- Vencimiento dentro de siete días: advertencia.
- Evidencia obligatoria faltante: aumento de prioridad.
- Tarea devuelta: prioridad alta.
- Dependencia abierta: tarea bloqueada.

Las reglas proponen prioridades; no sustituyen decisiones profesionales.

### 3.4 Productos operativos

El motor puede preparar:

- Matriz Excel de seguimiento.
- Borrador PDF de informe mensual.
- Paquete ZIP mensual.
- Resumen JSON.
- CSV de tareas.
- Relación de documentos aplicables.

Todos se guardan con:

- Estado `BORRADOR`.
- SHA-256.
- Usuario generador.
- Fecha.
- Revisor y aprobador cuando corresponda.

El sistema no inventa campos faltantes ni convierte borradores en documentos aprobados sin intervención humana.

## 4. Seguridad y multi-fundación

- Todas las tablas nuevas incluyen `fundacion_id`.
- Las rutas usan la fundación de la sesión.
- Los productos se almacenan en `/data/tenants/<fundacion_id>/...`.
- No se aceptan descargas fuera del almacenamiento autorizado.
- Las fuentes remotas rechazan HTTP, credenciales embebidas y resoluciones privadas.
- Los roles operativos consultan el motor; coordinación administra y los roles de aprobación revisan productos y cierres.
- La Biblioteca no activa automáticamente versiones detectadas.

## 5. Interfaz

Se añadió al menú **Gestión Integral UCA**:

```text
Motor de Gestión
```

El panel incluye:

- Resumen del periodo.
- Tareas consolidadas.
- Recordatorios.
- Creación de tareas controladas.
- Preparación y descarga de productos.
- Revisión de productos.
- Cierres mensuales.

La Biblioteca añade vistas de:

- Fuentes.
- Candidatos.
- Notificaciones.
- Historial.
- Importación manual de candidatos.
- Registro de fuentes autorizadas.

## 6. Pruebas

La prueba específica `test_biblioteca_motor_gestion_v2_5_3.py` valida:

- Esquema Biblioteca v3.
- Esquema Motor v1.
- Sincronización idempotente.
- Integración de Ruta Operativa, Pedagogía y Salud/Nutrición.
- Detección de vencimientos y recordatorios.
- Generación de Excel, PDF y ZIP.
- Estado borrador y SHA-256.
- Cierre mensual borrador.
- Fuente remota deshabilitada por defecto.
- Importación y aprobación manual de candidatos.
- Ausencia de activación automática.
- Relaciones, notificaciones e historial.
- Aislamiento entre dos fundaciones.

También se conservan las suites de regresión heredadas.

## 7. Límites

No se ejecutó una integración real con sistemas internos del ICBF porque no se suministró una API oficial ni un contrato autorizado. Tampoco se ejecutaron desde este entorno PowerShell, Cloudflare Tunnel, Docker completo o Railway con tráfico real.

La versión queda como candidata para pruebas controladas con datos ficticios.
