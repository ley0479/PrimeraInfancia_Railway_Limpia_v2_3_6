# Corrección final del formato oficial RAM

Fecha de verificación: 2026-08-11. Alcance exclusivo: RAM V3. No se ejecutaron migraciones ni se modificaron autenticación, roles, multi-tenant, RPP, Bienestarina u otros módulos funcionales.

## Causas raíz

1. El QA anterior comparaba estilos, pero no protegía valores y fórmulas estáticas de la plantilla.
2. La limpieza de filas sustituía la numeración y las fórmulas oficiales de `A15:A34` aun en la primera página.
3. NUI/Código CUÉNTAME se resolvía mediante un único alias y no consultaba variantes guardadas en `datos_json` de la UDS.
4. Las pruebas sintéticas no dejaban explícito que PostgreSQL debe contener Base Maestra, unidad y asignación de Talento Humano para completar una descarga real. En la base activa auditada hay 0 filas en `master_ninos`, `master_unidades`, `master_talento_humano`, `th_personas` y `th_asignaciones`; no se inventaron valores.

## Cambios mínimos

- `backend/services/ram_v3_service.py`
  - Conserva valores y fórmulas oficiales de `A15:A34` en la primera página.
  - Numera dinámicamente solo las páginas adicionales.
  - Resuelve Código CUÉNTAME con prioridad `codigo_cuentame`, `nui_uds`, `codigo_uds`.
  - Advierte cuando faltan agente, cédula, código o teléfono en las fuentes.
- `backend/app.py`, función interna `metadata_ram_v3`
  - Extrae NUI y Código CUÉNTAME desde columnas reales o `datos_json`.
  - Mantiene Talento Humano/asignaciones como fuente del agente, documento y teléfono.
- `backend/services/ram_visual_qa.py`
  - Compara valores/fórmulas estáticas, merges, estilos, fuentes, rellenos, bordes, alineaciones, rotación, dimensiones, impresión, márgenes, encabezados y pies.
- `backend/tests/test_ram_official_template_preservation.py`
  - Ejecuta el QA reutilizable y protege las fórmulas de numeración oficial.

## Evidencia funcional y visual

Archivo generado: `data/output/RAM_PRUEBA_QA_2026_08.xlsx`.

- MES: PASS
- NUI/Código CUÉNTAME: PASS
- agente educativo: PASS
- cédula del agente como texto: PASS
- teléfono: PASS
- tipos RC, TI, CC, CE y PPT: PASS
- documentos largos y con ceros iniciales como texto: PASS
- nombres y apellidos: PASS
- edades 2, 8 y 18 meses, 4 años y gestante: PASS
- orden por grupo etario: PASS
- asistencia, inasistencia y retiro: PASS
- totales 1 menor de 6 meses, 3 mayores de 6 meses y 1 gestante: PASS
- 775 celdas estáticas comparadas: PASS
- merges, dimensiones, estilos e impresión: PASS
- plantilla fuente sin modificación (hash): PASS

El libro fue abierto en Microsoft Excel en modo de solo lectura. La inspección confirmó orientación vertical de días, ASISTENCIAS y CAUSA DE RETIRO; marcas uniformes; totales negros y centrados; y conservación de bordes, firmas y pie oficial. Capturas: `data/output/RAM_PRUEBA_QA_2026_08_excel.png` y `data/output/RAM_PRUEBA_QA_2026_08_totales.png`.

## Regresión

Las tres regresiones RAM terminaron en PASS:

- `test_ram_official_template_preservation.py`
- `test_ram_v3_integration.py`
- `test_ram_download_period_wiring.py`

El gate transversal terminó en `BLOCKED` por fallos preexistentes fuera del alcance RAM: contratos antiguos de los BAT de inicio, limpieza de archivos temporales SQLite bloqueados y una prueba antigua que escanea `.venv`. Los contratos estáticos, sintaxis Python/JavaScript, plantillas oficiales, PostgreSQL runtime y las pruebas RAM pasaron. Evidencia: `data/integrity/integrity_gate_ram_final.json`.

La corrección RAM está verificada, pero la versión global no debe declararse desplegable hasta resolver separadamente esos fallos históricos del gate.
