# Auditoría del Motor Universal de Mapeo

Fecha: 2026-08-20  
Estado inicial auditado: commit `6c521f7`

## Flujo actual

La carga operativa entra por `POST /api/base-maestra/cargar-fuente`, guarda el archivo en almacenamiento privado por tenant, lo lee en `modules/base_maestra/services.py`, normaliza inmediatamente los encabezados con `make_columns`, elige una hoja mediante pesos fijos, mapea cada fila con `pick` y la deposita en tablas `staging_*`. Después valida, consolida una versión y finalmente publica `master_ninos`, `master_unidades`, talento humano y nutrición. Los generadores consumen mayoritariamente Base Maestra y conservan adaptadores heredados.

## Causa raíz reproducida

El importador existente usa un diccionario de aliases con selección por prioridad. La defensa añadida para `nombre_de_la_unidad_de_servicio` corrige el archivo conocido, pero no reúne evidencia semántica ni perfila valores, no puntúa todos los candidatos, no evalúa código–nombre como pareja, no conserva procedencia por campo y no abre confirmación asistida. Por eso la solución seguía dependiendo de encabezados predefinidos y podía recaer con otra institución.

La columna regional contiene además las palabras “unidad de servicio”. Un algoritmo basado en coincidencia parcial o primera coincidencia puede elegirla. La solución de raíz requiere penalizar “regional”, “municipio” y “centro zonal” para campos de unidad y comparar todos los candidatos.

## Archivos y restricciones relevantes

- `backend/modules/base_maestra/services.py`: lectura, aliases, staging, validación y consolidación.
- `backend/modules/base_maestra/schema.py`: staging y modelo maestro versionado.
- `backend/modules/base_maestra/routes.py`: rutas y roles.
- `frontend/js/modules/base-maestra.js`: carga y panel existentes.
- `backend/migrations/migrate_unidades_tenant_unique_v7.py`: ya elimina `UNIQUE(nombre)` global y garantiza `UNIQUE(fundacion_id,nombre)` sin fusionar datos.
- `backend/services/listado_asistencia_usuarios_service.py`, RAM, RPP y Bienestarina: consumidores existentes del modelo consolidado/adaptadores compatibles.

## Estado inicial de pruebas

`pytest` no está instalado en el entorno virtual compartido (`No module named pytest`). Se ejecutarán pruebas `unittest` directamente. Se inspeccionaron 8 libros `.xlsx/.xlsm`; ninguno contiene la hoja `ICBFCUEBeneficiariosPIActivosRe`. La validación con el archivo real queda pendiente y se utiliza el fixture sintético obligatorio de 417 filas, 41 columnas y 39 UDS.

## Riesgos y controles

- Compatibilidad: el motor se agrega detrás de `ENABLE_UNIVERSAL_DATA_MAPPER`; el importador anterior permanece.
- Multitenancy: toda persistencia debe incluir `tenant_id/fundacion_id` y filtrar por el contexto autenticado.
- Códigos: se conservan como texto; notación científica irrecuperable debe advertirse.
- Ambigüedad: no pasa a tablas operativas hasta confirmación.
- Migraciones: no se eliminan filas ni se fusionan unidades; se crea identidad externa por tenant, perfil y código.

## Plan de modificación y reversión

Se incorpora `backend/services/data_import` con adaptadores, detector de encabezado, normalizadores, perfilado, catálogo, scoring y evaluación conjunta. Posteriormente se conecta staging persistente/API/asistente a Base Maestra. Para revertir, se desactiva la bandera, se retiran las rutas nuevas y se conservan las tablas nuevas sin afectar datos existentes; la migración descendente elimina únicamente índices/tablas del motor si están vacíos o después de exportar su auditoría.
