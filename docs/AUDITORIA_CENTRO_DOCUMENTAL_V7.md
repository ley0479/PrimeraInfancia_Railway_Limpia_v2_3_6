# Auditoría — Centro de Actas, Informes y Documentos Institucionales

Fecha de baseline: 2026-08-21

## Estado inicial

- Repositorio: `ley0479/PrimeraInfancia_Railway_Limpia_v7_0`
- Commit protegido: `79d519ef6af03dd861620e5268164cf86f95c2b1`
- Rama de implementación: `feature/motor-universal-actas-informes-capture`
- Árbol de trabajo al iniciar: limpio.
- Estrategia: implementación aditiva, protegida por banderas y migrada solo en predeploy.

## Pruebas de caracterización

| Prueba | Resultado | Evidencia |
|---|---|---|
| Motor de plantillas por tenant y versiones | PASS | `test_motor_plantillas_tenant_versions.py` |
| Núcleo IDP documental | PASS | `test_idp_documental_core_v1.py` |
| Calendario y checklist fase 3 | PASS | `test_calendar_phase3_checklist_v2_7_0.py` |
| Lector documental de calendario | PASS | `test_calendar_phase5_document_reader_v2_7_0.py` |
| Talento Humano integral | PASS | `test_talento_integral_refresh_v2_7_1.py` |
| Integración calendario–asistencia | PASS | `test_attendance_calendar_integration_v2_7_0.py` |

El entorno Python disponible no contiene `pytest`; las pruebas se ejecutaron como scripts con `PYTHONPATH=backend`, que es el contrato actual de esos archivos.

## Arquitectura existente que se protege y reutiliza

- `backend/app.py`: composición principal y registro de blueprints. Solo se permitirá un registro puntual del nuevo módulo.
- `backend/init_hosting.py`: predeploy/migraciones. Será el único punto de registro de DDL nuevo.
- `backend/modules/motor_plantillas`: catálogo, inspección y versionado actual de plantillas Excel.
- `backend/modules/idp_documental`: almacenamiento privado, extracción, corrección, aprobación, auditoría y cola persistente.
- `backend/modules/seguridad/tenant_context.py`: resolución de rutas y almacenamiento aislado por fundación.
- `backend/modules/base_maestra`: fuente canónica de participantes y UDS; solo lectura desde el nuevo motor.
- `backend/modules/talento_humano`: fuente canónica de profesionales; no se duplicarán personas.
- `backend/modules/calendario_inteligente`: actividades, requisitos, checklist y evidencias existentes.
- `backend/services/listado_asistencia_usuarios_service.py`: generador oficial de asistencia ya operativo; el Centro Documental lo referenciará.
- `backend/modules/plantillas_oficiales.py`: formatos oficiales actuales; no se alterarán sus plantillas.
- `backend/seed_data/templates_originales`: originales oficiales existentes, protegidos contra sobrescritura.

## Brecha confirmada

No existe todavía un dominio transversal que gestione en un único flujo plantillas narrativas DOCX/PDF, planeación por tema, hechos confirmados, catálogos multiselección, contradicciones, versiones documentales, revisión/devolución/aprobación, evidencias y paquetes. CAPTURE tampoco dispone de plantilla oficial real en el repositorio, por lo cual debe permanecer `PLANTILLA_PENDIENTE` y desactivado.

## Archivos protegidos

- Plantillas y seed data oficiales.
- Base Maestra y sus tablas operativas.
- Talento Humano y sus tablas operativas.
- Generadores RAM, RAN, RRAN, RPP, Bienestarina y listado oficial.
- Autenticación, sesiones, suscripciones, créditos y configuración de base de datos.
- Calendario y checklist existentes.

## Cambios previstos

Archivos nuevos:

- `backend/modules/centro_documental/`: rutas, esquema, repositorio, permisos y servicios documentales.
- Migración idempotente del esquema documental.
- Pruebas unitarias, HTTP, multitenant, plantillas y flujo integral.
- Interfaz frontend aislada y documentación operativa.

Archivos compartidos previstos para modificación mínima:

- `backend/app.py`: registrar un blueprint sin ejecutar DDL.
- `backend/init_hosting.py`: ejecutar la migración documental en predeploy.
- configuración/versionado y frontend principal: exponer banderas y montar la interfaz.

## Riesgos y controles

- Duplicación del motor de plantillas: se evita mediante servicios/adaptadores y referencias al catálogo existente.
- Fuga entre fundaciones: todas las operaciones incorporarán `fundacion_id`; se probarán accesos A/B.
- Corrupción de originales: almacenamiento inmutable por hash y generación sobre copias.
- Narrativa inventada: el generador determinista solo usa tema para planeación y hechos confirmados para resultados.
- DDL en requests/startup: prohibido; migración exclusiva de predeploy.
- CAPTURE ficticio: bandera desactivada y estado pendiente hasta recibir archivo real aprobado.
- Conversión PDF no disponible: Word debe conservarse y el fallo se reportará sin perder el borrador.

## Plan de rollback

1. Desactivar `ENABLE_DOCUMENT_AUTOMATION` y las banderas derivadas.
2. Retirar únicamente el registro del blueprint nuevo si fuera necesario.
3. Conservar tablas y archivos documentales para no perder historial.
4. Revertir el commit funcional; no ejecutar `DROP`, `TRUNCATE` ni borrar originales.
5. Mantener intactos los motores preexistentes, que continúan siendo la ruta operativa de respaldo.

## Quality Gate Fase 0

Baseline seleccionada: **PASS (6/6)**.

CAPTURE: **PENDING**, por ausencia de plantilla oficial real.

## Avance posterior a la auditoría

- Fases 1–2: catálogo versionado, hash, original privado, inspección DOCX/XLSX/PDF y aprobación de mapa — PASS.
- Fases 3–5: contexto paginado de Base Maestra/Talento Humano, planeación determinista, catálogos, selecciones, narrativa y revisión — PASS.
- Fase 6: Word sobre copia, integridad del original, texto largo, membrete, firma vacía y ZIP con manifiesto — PASS.
- PDF: PENDING en el entorno local por ausencia de LibreOffice; se verificó que el fallo conserva y ofrece el Word.
- CAPTURE: PENDING; no existe plantilla real aprobada y la bandera permanece desactivada.
- Evidencias privadas, referencias a Calendario/Checklist y participantes de fuentes maestras — PASS.
- Reutilización del listado oficial existente — integrada; requiere que cada fundación tenga su planilla oficial cargada.
- Contrato HTTP, roles y aislamiento A/B — PASS.
- Asistente frontend dentro del Motor Documental IDP — sintaxis PASS; oculto mientras la bandera permanezca apagada.
