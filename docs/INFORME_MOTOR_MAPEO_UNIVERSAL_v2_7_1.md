# Informe del Motor Universal de Mapeo — v2.7.1

Fecha de corte: 2026-08-20  
Commit de corte: `a2ed9f8`  
Estado: implementación terminada; activación productiva pendiente.

## 1. Resultado general

Se implementó un motor tabular independiente, determinista y auditable. Analiza fuentes sin escribir en tablas operativas, propone mapeos explicables, solicita confirmación, versiona correcciones y finalmente importa mediante el staging existente de Base Maestra. La publicación continúa siendo una acción separada.

## 2. Causa raíz encontrada

El importador anterior normalizaba los encabezados demasiado pronto y seleccionaba aliases por prioridad aislada. No puntuaba todos los candidatos ni evaluaba el par código–nombre. La palabra “Regional” no anulaba suficientemente una coincidencia amplia con “unidad de servicio”. Véase `docs/AUDITORIA_MOTOR_MAPEO_UNIVERSAL.md`.

## 3. Arquitectura implementada

Flujo: adaptador → inspección de tablas → detección de encabezado → perfilado → scoring semántico → mapeo conjunto UDS → staging con procedencia → confirmación/perfil → validación → staging Base Maestra → consolidación/publicación existente → formatos.

Adaptadores activos: Excel/XLS/XLSM, ODS, CSV/TSV/TXT y JSON/NDJSON. Los contratos relacional e IDP fallan de forma explícita hasta contar con configuración o extracción tabular aprobada.

## 4. Archivos modificados

`.env.example`, `README_RAILWAY.md`, `backend/app.py`, `backend/config.py`, `backend/init_hosting.py`, `backend/modules/integrity_stability/service.py`, `backend/modules/seguridad/services.py`, tres pruebas históricas de versión, `frontend/index.html`, `frontend/js/modules/base-maestra.js`, `scripts_windows/iniciar_plataforma.ps1` y `tools/validate_release.py`.

## 5. Archivos creados

`CHANGELOG.md`; migración `migrate_universal_mapper_v7.py`; módulo `importaciones_universales`; paquete `services/data_import` con adaptadores, catálogo, normalizadores, detector, perfilador, mapper, seguridad y servicio; tres pruebas nuevas; auditoría e informe.

## 6. Migraciones aplicadas

La migración aditiva crea importaciones, perfiles, aliases, filas staging, auditoría e identificadores externos. En SQLite temporal: PASS. En PostgreSQL/Railway real: PENDING. El DDL está bloqueado durante runtime y autorizado solo en predeploy.

## 7. Pruebas ejecutadas

| Prueba | Resultado | Evidencia |
|---|---|---|
| Regresión universal, 11 casos | PASS | `Ran 11 tests ... OK` |
| E2E SQLite 417/39 | PASS | `UNIVERSAL_IMPORT_E2E_SQLITE_PASS` |
| Contrato HTTP | PASS | `UNIVERSAL_IMPORT_HTTP_CONTRACT_PASS` |
| Base Maestra HTTP | PASS | `BASE_MAESTRA_HTTP_CONTRACT_PASS` |
| Listado oficial | PASS | carga, mapeo, UDS e impresión OK |
| RAM V3 | PASS | hash, paginación, instrucciones y plantilla intacta |
| RPP minuta vigente | PASS | código de salida 0 |
| Multitenant release | PASS | `PASS test_multitenant_release_v2_4_0` |
| Túnel Cloudflare | PASS | `PASS test_tunnel_cloudflare_v2_4_3` |
| Login/túnel | PASS | `PASS test_tunnel_login_logging_v2_4_2` |
| PostgreSQL/Railway | PENDING | Railway/GitHub CLI no disponibles |
| Excel real solicitado | PENDING | no está en el workspace |

El validador global produjo 8 PASS y 9 FAIL. Los fallos corresponden a manifiestos/hashes históricos, cachés generados, archivos runtime, Bash no disponible, residuos operativos y configuración Docker previa. La familia `/api/importaciones` sí fue agregada posteriormente a la matriz central de autorización.

## 8. Resultado de la base real

PENDING: se inspeccionaron ocho libros y ninguno contiene `ICBFCUEBeneficiariosPIActivosRe`. No se afirma validación real.

Fixture equivalente: 417 registros, 41 columnas, 39 UDS, cero códigos/nombres vacíos; J → `unidad.codigo`, K → `unidad.nombre`, F → `regional.nombre`, G/H → municipio, I → centro zonal; “Chocó” no aparece como unidad.

## 9. Resultado por formato

RAM, RPP y listado oficial: PASS de no regresión. Bienestarina consume Base Maestra/plantilla oficial por la capa existente; su generación E2E posterior a una publicación universal real queda PENDING hasta el piloto PostgreSQL.

## 10. Verificación multitenant

PASS en SQLite: el mismo hash no cruza tenants; todos los accesos usan tenant autenticado; rutas de escritura excluyen Docente, Coordinador y Psicosocial. PostgreSQL real: PENDING.

## 11. Errores pendientes

- Falta el archivo Excel real.
- No hay Railway CLI ni GitHub CLI disponibles para consultar predeploy.
- Prueba `.xls` binaria real pendiente; XLSM y ODS están en PASS.
- Activación productiva pendiente por decisión de dejarla al final.

## 12. Riesgos conocidos

Archivos muy grandes aún se procesan por bloques para staging, pero la inspección de algunas hojas usa DataFrame completo. El piloto debe observar memoria y duración. Un Excel que ya perdió precisión numérica no permite reconstruir códigos; debe revisarse manualmente.

## 13. Plan de reversión

1. Configurar `ENABLE_UNIVERSAL_DATA_MAPPER=false`.
2. Mantener el importador anterior operativo.
3. Revertir commits en orden inverso si fuera necesario, sin `reset --hard`.
4. La función `downgrade(..., allow_drop=True)` solo debe usarse después de exportar auditoría; no toca Base Maestra.

## 14. Comandos para ejecutar localmente

```powershell
$env:PYTHONPATH=(Resolve-Path 'backend').Path
python backend/tests/test_universal_data_mapper_regression.py
python backend/tests/test_universal_import_http_contract.py
python backend/tests/test_universal_import_e2e_sqlite.py
```

## 15. Pasos de despliegue

1. Ejecutar el predeploy habitual (`backend/init_hosting.py`).
2. Confirmar en logs `[MIGRATION] universal mapper`.
3. Mantener la bandera apagada y verificar salud/login.
4. Activar `ENABLE_UNIVERSAL_DATA_MAPPER=true` y `UNIVERSAL_IMPORT_MAX_BYTES=52428800`.
5. Reiniciar, cargar el archivo real en piloto, confirmar 417/39 y generar los cuatro formatos.
6. Si falla, apagar la bandera; no publicar la versión de Base Maestra.

## 16. Versión final

`2.7.1-universal-data-mapper`. Código publicado en `origin/main` mediante siete commits entre `29100ca` y `a2ed9f8`. La palabra “final” se refiere al código implementado; la aceptación productiva continúa PENDING hasta completar los puntos 8, 9 y 10 en Railway.
