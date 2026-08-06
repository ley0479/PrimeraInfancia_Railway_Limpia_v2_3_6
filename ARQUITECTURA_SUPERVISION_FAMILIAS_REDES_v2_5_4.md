# Arquitectura — Supervisión, Familias, Comunidad y Redes 2.5.4

## 1. Vista general

```text
Frontend SPA
  ├─ Supervisión y Calidad
  └─ Familias, Comunidad y Redes
          ↓
Blueprints Flask con autenticación, roles, tenant y UCA
          ↓
Repositorios de dominio
  ├─ supervision_calidad  → csc_*
  └─ familias_redes       → fcr_*
          ↓
Integraciones por referencia
  ├─ giu_expedientes_uca
  ├─ beneficiarios / Base Maestra
  ├─ mgp_tareas
  └─ documentos y calendario existentes
          ↓
SQLite + /data/tenants/<fundacion_id>/...
```

## 2. Principios

1. **Fuente única:** los participantes permanecen en Base Maestra; el módulo familiar conserva referencias.
2. **Fachadas especializadas:** las vistas consolidan información sin reemplazar el módulo fuente.
3. **Tenant obligatorio:** cada tabla y consulta utiliza `fundacion_id`.
4. **UCA fail-closed:** un rol operativo sin asignaciones explícitas no obtiene acceso global.
5. **Idempotencia:** la sincronización familiar y las tareas del Motor pueden repetirse sin duplicar registros.
6. **Revisión humana:** no existen cierres automáticos de supervisiones, hallazgos, planes, acciones, compromisos o alertas.
7. **Integridad documental:** evidencias y productos guardan tamaño, MIME y SHA-256.
8. **Almacenamiento seguro:** los archivos solo se sirven desde la raíz autorizada del tenant.
9. **Borradores:** actas, informes y productos se generan para revisión; nunca se consideran aprobados automáticamente.
10. **Minimización:** no se incorporó una historia psicosocial clínica ni campos libres reservados de alto riesgo.

## 3. Prefijos de tablas

### Centro de Supervisión

- `csc_checklist_catalogo`
- `csc_supervisiones`
- `csc_verificaciones`
- `csc_hallazgos`
- `csc_planes_mejora`
- `csc_acciones_mejora`
- `csc_seguimientos`
- `csc_evidencias`
- `csc_productos`
- `csc_auditoria`

### Familias, Comunidad y Redes

- `fcr_expedientes_familiares`
- `fcr_actividades`
- `fcr_asistencias`
- `fcr_compromisos`
- `fcr_seguimientos`
- `fcr_redes_apoyo`
- `fcr_alertas`
- `fcr_evidencias`
- `fcr_documentos_generados`
- `fcr_auditoria`

## 4. Contratos de integración

- Expediente UCA: `fundacion_id + expediente_uca_id`.
- Participante: referencia a `beneficiarios.id`, sin copiar identidad ni caracterización.
- Motor: `fundacion_id + fuente_tabla + fuente_clave`.
- UCA: nombre normalizado mediante clave estable.
- Archivos: raíz obtenida con `tenant_storage_root`.
- Expediente central: vínculos documentales por `source_module`, `source_table` y `source_id`.

## 5. Flujo de Supervisión

```text
csc_supervisiones
    ├─ csc_verificaciones
    ├─ csc_hallazgos
    │    └─ csc_planes_mejora
    │         └─ csc_acciones_mejora
    ├─ csc_seguimientos
    ├─ csc_evidencias
    └─ csc_productos
```

Los cambios críticos requieren rol autorizado y se registran en `csc_auditoria`.

## 6. Flujo de Familias

```text
beneficiarios
    ↓ referencia idempotente
fcr_expedientes_familiares
    ├─ fcr_actividades
    │    ├─ fcr_asistencias
    │    └─ fcr_documentos_generados
    ├─ fcr_compromisos
    │    └─ fcr_seguimientos
    ├─ fcr_alertas
    └─ fcr_evidencias

fcr_redes_apoyo ← actores y rutas territoriales
```

## 7. API

### Supervisión

Prefijo: `/api/supervision-calidad`

Incluye dashboard, expedientes, supervisiones, verificaciones, hallazgos, planes, acciones, seguimientos, evidencias y productos.

### Familias

Prefijo: `/api/familias-redes`

Incluye dashboard, sincronización y consulta de expedientes, actividades, asistencias, documentos, compromisos, seguimientos, redes, alertas, evidencias y paquete de reporte.

## 8. Seguridad

- La fundación proviene de la sesión autenticada.
- Las descargas validan tenant, entidad vinculada, UCA e integridad del archivo.
- Las rutas físicas no se retornan al navegador.
- Los archivos quedan bajo `/data/tenants/<fundacion_id>/...`.
- Los roles operativos no pueden aprobar su propio proceso.
- La ausencia de UCA asignada se interpreta como ningún acceso, no como acceso global.
