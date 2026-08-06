# Arquitectura — Expediente Operativo central por UCA 2.5.2

## Principio

El Expediente UCA es una **fachada de integración**, no una base paralela.

```text
Fuente operativa única  →  Adaptador de lectura  →  Vista UCA  →  Supervisión
```

## Capas

### 1. Fuentes operativas

- `master_ninos`, `master_inconsistencias`.
- `gp_entregables`, `gp_evidencias`, `gp_documentos`.
- `pp_planeaciones`, `pp_documentos_generados`.
- `sn_valoraciones`, `sn_alertas`, `sn_entregables_mes`, `sn_adjuntos`.
- `plantillas_oficiales_versiones`.
- `th_personas`, `th_asignaciones`.
- `calendario_entregables` y calendarios compatibles.
- `rg_reportes`, `pm_paquetes`.

### 2. Integración

`UCAIntegrationEngine`:

- Descubre tablas y columnas de forma defensiva.
- Aplica filtro por fundación.
- Aplica filtro por UCA/código.
- Deriva métricas.
- Consolida alertas y cronograma.
- Descubre referencias documentales.
- No ejecuta `INSERT`, `UPDATE` o `DELETE` sobre módulos fuente.

### 3. Persistencia propia

- `giu_expedientes_uca`.
- `giu_ruta_catalogo`.
- `giu_ruta_instancias`.
- `giu_ruta_evidencias`.
- `giu_planes_uca`.
- `giu_vinculos_documentales`.
- `giu_paquetes_supervision`.
- `giu_auditoria`.

### 4. API

```text
GET  /expedientes/<id>
GET  /expedientes/<id>/vista-unica
GET  /expedientes/<id>/preparacion-supervision
GET  /expedientes/<id>/documentos
POST /expedientes/<id>/documentos
GET  /expedientes/<id>/documentos/<link_id>/descargar
GET  /expedientes/<id>/paquete-supervision
```

### 5. Interfaz

Una vista única con navegación por dominios; cada tarjeta conserva acceso al módulo fuente.

## No duplicidad

No se copian:

- Participantes.
- Medidas antropométricas.
- Planeaciones.
- Alertas.
- Entregables.
- Personal.
- Archivos.

El índice documental solo guarda identificadores y metadatos para localizar el archivo original.

## Aislamiento

Cada consulta usa `fundacion_id` cuando la tabla lo soporta. La UCA se compara mediante valores normalizados de nombre y código. Las descargas se limitan a archivos bajo `DATA_DIR`.

## Rendimiento

- El listado de UCA usa métricas persistidas de la Ruta Operativa.
- La vista transversal se calcula al seleccionar una UCA.
- El índice documental se sincroniza por `UPSERT`.
- Los límites de consulta evitan cargas no acotadas.

## Extensibilidad

Para integrar un módulo futuro se añade un adaptador de lectura en `integrations.py`, se declara su sección y se incorpora su indicador; no se modifica la fuente operativa.
