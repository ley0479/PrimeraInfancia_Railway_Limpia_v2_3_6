# Arquitectura — Centro de Planeación y Componente Psicosocial 2.7.0

## 1. Contexto

La solución se agrega sobre PrimeraInfancia 2.6.1. Mantiene PostgreSQL en producción, SQLite para recuperación local y la capa de compatibilidad DB-API existente.

## 2. Diagrama lógico

```text
Módulos misionales
├── Salud y Nutrición
├── Gestión Pedagógica
├── Familias y Redes
├── Motor de Gestión
├── Calendario histórico
└── Planeaciones
          │
          ▼
Centro de Planeación
├── reglas
├── metadatos
├── dependencias
├── notificaciones
├── documentos borrador
└── auditoría
          │
          ├──────────────► Vista por rol
          ├──────────────► Vista global de coordinación
          └──────────────► Paquete mensual

Base Maestra / Familias y Redes
          │ referencias, no copias
          ▼
Componente Psicosocial
├── expediente referencial
├── caracterizaciones versionadas
├── planes
├── acciones
├── actividades vinculadas
├── seguimientos
├── documentos restringidos
└── auditoría de acceso
          │
          ▼
Expediente Operativo por UCA
```

## 3. Propiedad de los datos

| Información | Módulo propietario | Uso en 2.7.0 |
|---|---|---|
| Participantes | Base Maestra | Referencia de lectura |
| Familias | Familias y Redes | Referencia de expediente |
| Actividades familiares | Familias y Redes | Vinculación y sincronización |
| Salud | Salud y Nutrición | Fuente del calendario |
| Pedagogía | Gestión Pedagógica | Fuente del calendario |
| Tareas | Motor de Gestión | Fuente solo cuando no existe fuente directa |
| Fecha/estado básico | `calendario_entregables` | Registro canónico |
| Reglas/dependencias | Centro de Planeación | Datos propios |
| Caracterización profesional | Psicosocial | Datos propios, versionados |

## 4. Esquema Centro de Planeación

- `cpo_schema_version`
- `cpo_reglas_operativas`
- `cpo_actividad_metadata`
- `cpo_dependencias`
- `cpo_documentos_preparados`
- `cpo_notificaciones`
- `cpo_auditoria`

Claves de idempotencia:

```text
fundacion_id + fuente_tabla + fuente_clave
fundacion_id + entregable_id
```

## 5. Esquema Psicosocial

- `ps_schema_version`
- `ps_expedientes`
- `ps_caracterizaciones`
- `ps_planes_acompanamiento`
- `ps_acciones_plan`
- `ps_vinculos_actividad`
- `ps_seguimientos`
- `ps_documentos`
- `ps_auditoria_accesos`

Claves relevantes:

```text
fundacion_id + fcr_expediente_familiar_id
fundacion_id + expediente_id + version
fundacion_id + expediente_id + fcr_actividad_id
```

## 6. API Centro de Planeación

Prefijo: `/api/centro-planeacion`

- `GET /salud`
- `POST /sincronizar`
- `GET /dashboard`
- `GET /actividades`
- `GET|PATCH /actividades/<id>`
- `POST /actividades/<id>/dependencias`
- `POST /actividades/<id>/documentos`
- `GET /documentos/<id>/descargar`
- `POST /documentos/<id>/<acción>`
- `GET|POST /reglas`
- `POST /notificaciones/<id>/leer`
- `POST /paquetes/mensual`
- `GET /paquetes/descargar`

## 7. API Psicosocial

Prefijo: `/api/psicosocial`

- `GET /salud`
- `POST /sincronizar`
- `GET /dashboard`
- `GET /expedientes`
- `GET /expedientes/<id>`
- `POST /expedientes/<id>/caracterizaciones`
- `POST /caracterizaciones/<id>/<acción>`
- `POST /expedientes/<id>/planes`
- `POST /planes/<id>/acciones`
- `PATCH /acciones/<id>`
- `POST /planes/<id>/cerrar`
- `POST /expedientes/<id>/actividades/<actividad>/vincular`
- `POST /expedientes/<id>/seguimientos`
- `POST /expedientes/<id>/informe`
- `GET /documentos/<id>/descargar`

## 8. Autorización

### Centro de Planeación

Todos los roles autenticados pueden consultar dentro de su alcance. Las aprobaciones, dependencias y configuración de reglas corresponden a SUPERADMIN, GERENTE y COORDINADOR.

### Psicosocial

Acceso funcional para SUPERADMIN, GERENTE, COORDINADOR y PSICOSOCIAL. La validación de caracterizaciones y el cierre de planes corresponden a coordinación.

## 9. Integración multi-tenant

Todas las consultas incluyen `fundacion_id`. Los usuarios operativos quedan limitados a las UCA asignadas. Una lista vacía de UCA no otorga acceso global.

## 10. Flujo de documentos

```text
Actividad sincronizada
→ regla aplicable
→ solicitud de producto
→ archivo BORRADOR
→ revisión
→ aprobación o devolución
→ auditoría
```

Los archivos conservan SHA-256, tamaño, tipo MIME, usuario y fechas.

## 11. Gate de integridad

El baseline 2.7.0 protege ambos módulos, sus rutas, archivos frontend, roles y pruebas. El despliegue se bloquea si se pierde una capacidad crítica.
