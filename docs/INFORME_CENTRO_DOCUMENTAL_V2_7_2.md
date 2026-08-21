# Informe — Centro de Actas, Informes y Documentos Institucionales

## A. Baseline

- Commit inicial: `79d519ef6af03dd861620e5268164cf86f95c2b1`.
- Rama: `feature/motor-universal-actas-informes-capture`.
- Baseline seleccionada: 6/6 PASS.
- Auditoría: `docs/AUDITORIA_CENTRO_DOCUMENTAL_V7.md`.

## B. Arquitectura

Flujo implementado: plantilla oficial → hash/versión → inspección → mapa propuesto → aprobación → contexto canónico → planeación → hechos confirmados → narrativa → copia DOCX → revisión → PDF opcional/ZIP → auditoría.

El módulo `backend/modules/centro_documental` es aditivo. Reutiliza Base Maestra, Talento Humano, TenantPath, Calendario/Checklist y el generador oficial de asistencia. No ejecuta DDL al importar el blueprint ni durante requests.

## C. Archivos nuevos

- Módulo `backend/modules/centro_documental/`.
- `backend/migrations/migrate_centro_documental_v7.py`.
- Seis pruebas `backend/tests/test_centro_documental_*_v7.py`.
- `frontend/js/modules/centro-documental.js`.
- `frontend/css/centro-documental.css`.
- Auditoría e informe documental.

## D. Archivos modificados

- `backend/app.py`: registro puntual del blueprint y metadatos de versión.
- `backend/init_hosting.py`: migración exclusiva en predeploy.
- `frontend/index.html` y `frontend/js/app.js`: asistente en la sección IDP y permisos visuales.
- `.env.example`, `backend/config.py`, lanzador, pruebas de versión y `CHANGELOG.md`: versión y banderas.

## E. Base de datos

Se añadieron tablas `doc_tipos_documento`, `doc_plantillas`, `doc_plantilla_versiones`, `doc_mapeos`, `doc_catalogos_respuesta`, `doc_opciones_respuesta`, `doc_instancias`, `doc_participantes`, `doc_selecciones`, `doc_versiones`, `doc_revisiones`, `doc_evidencias` y `doc_auditoria`, con índices por tenant/estado. La migración es incremental e idempotente y se registra en `init_hosting.py`.

## F. Plantillas

DOCX, XLSX/XLSM y PDF se inspeccionan estructuralmente. El original queda en almacenamiento privado por tenant y hash. El mapa comienza `PROPUESTO`; no se activa silenciosamente. No se suministraron plantillas oficiales nuevas para actas/informes durante esta ejecución.

## G. CAPTURE

Estado: **PENDING — PLANTILLA_PENDIENTE**. No existe archivo oficial CAPTURE en el alcance recibido. Su carga puede inspeccionarse durante el piloto, pero aprobación/generación permanecen bloqueadas con `ENABLE_CAPTURE_FORMAT=false`.

## H. Catálogos desplegables

Se sembraron opciones deterministas para Pedagógico, Psicosocial y Salud/Nutrición. Admiten selección múltiple, texto personalizado, estados explícitos y `NO_APLICA` con justificación. Datos clínicos y antropométricos no se sugieren ni inventan.

## I. Generador por tema

Genera contenido marcado `PLANEADO`: objetivo, descripción, metodología, recursos, logros esperados, dificultades posibles, compromisos sugeridos y recomendaciones. Los resultados reales provienen únicamente de selecciones confirmadas y producen narrativa editable.

## J. Word, PDF y ZIP

- DOCX abre, conserva membrete de prueba, firma vacía, texto largo y hash del original: PASS.
- ZIP y manifiesto JSON con hashes: PASS.
- PDF: PENDING local por ausencia de LibreOffice. El error conserva Word y no tumba el proceso.

## K. Seguridad y multi-tenant

Consultas, archivos, plantillas, participantes, evidencias y documentos filtran por `fundacion_id`. Pruebas A/B y roles backend: PASS. Las rutas físicas no se exponen como API de descarga.

## L. Rendimiento

Base Maestra y Talento Humano usan búsqueda, filtros, límite y offset. Generación documental es bajo demanda. No se añadieron consultas masivas al abrir la interfaz. Benchmark de producción: PENDING.

## M. Regresiones

| Prueba | Resultado | Evidencia |
|---|---|---|
| Núcleo documental | PASS | `test_centro_documental_core_v7.py` |
| Plantillas e integridad | PASS | `test_centro_documental_templates_v7.py` |
| Contexto y flujo | PASS | `test_centro_documental_flow_v7.py` |
| Word/ZIP | PASS | `test_centro_documental_exports_v7.py` |
| HTTP, roles y A/B | PASS | `test_centro_documental_http_v7.py` |
| Evidencias/Calendario | PASS | `test_centro_documental_integrations_v7.py` |
| Motor de plantillas anterior | PASS | `test_motor_plantillas_tenant_versions.py` |
| IDP anterior | PASS | `test_idp_documental_core_v1.py` |
| Base Maestra HTTP | PASS | `test_base_maestra_http_contract.py` |
| Talento Humano | PASS | `test_talento_integral_refresh_v2_7_1.py` |
| Checklist/Calendario | PASS | pruebas fase 3 y fase 5 |
| Asistencia/Calendario | PASS | `test_attendance_calendar_integration_v2_7_0.py` |
| Formatos complementarios | PASS | `test_alpha68_formatos_complementarios_v2_7_0.py` |
| Motor universal tabular | PASS | 11 casos internos |
| PDF local | PENDING | LibreOffice no instalado |
| CAPTURE real | PENDING | plantilla oficial no suministrada |
| Railway/staging/GitHub Actions | PENDING | requiere credenciales y despliegue autorizado |
| Validador global de release | FAIL | 8 PASS/9 FAIL: manifiestos/hashes históricos, cachés y log runtime, Bash/Docker, versión histórica esperada y reglas públicas no contempladas por el analizador |

Matriz amplia ejecutada: 15 archivos, 0 fallidos.

## N. Railway

Predeploy incluye la migración documental. Startup solo registra rutas. `/api/health`, `/api/ready` y `/api/system/version` conservan sus contratos; versión `2.7.2-document-center`. Despliegue real: PENDING.

## O. Rollback

1. Mantener todas las banderas documentales en `false`.
2. Revertir los commits de la rama si fuera necesario.
3. No borrar tablas ni archivos; preservar historial y originales.
4. Los motores IDP, plantillas, asistencia y Calendario anteriores continúan operativos.

## P. Pendientes

- Cargar plantillas oficiales reales de cada acta/informe y aprobar sus mapas.
- Instalar LibreOffice en el runtime que generará PDF y ejecutar el gate correspondiente.
- Recibir, inspeccionar, mapear y probar CAPTURE real.
- Ejecutar migración y smoke tests sobre PostgreSQL/Railway staging.
- Validar visualmente la interfaz en dispositivos y probar impresión con formatos reales.
- Ejecutar GitHub Actions y piloto controlado antes de activar banderas.
- Sanear por el proceso formal de release los manifiestos/hashes y residuos históricos señalados por `tools/validate_release.py`; no se regeneraron silenciosamente.

## Ejecución local

```powershell
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe backend\tests\test_centro_documental_core_v7.py
```

Las banderas deben continuar en `false` hasta completar predeploy y piloto. Para un piloto controlado se activan primero `ENABLE_DOCUMENT_AUTOMATION`, luego `ENABLE_TEMPLATE_MAPPING` y `ENABLE_RESPONSE_CATALOGS`. IA y CAPTURE permanecen apagados.

## Estado

**IMPLEMENTACIÓN PARCIAL — PENDIENTES DE VALIDACIÓN**
