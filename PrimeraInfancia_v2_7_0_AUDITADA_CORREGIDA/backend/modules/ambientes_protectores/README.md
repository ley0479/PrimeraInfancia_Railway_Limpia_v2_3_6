# Ambientes Educativos y Protectores

Módulo independiente para condiciones de calidad por UCA. `aep_activos` es la fuente de inventario/dotación y `aep_mantenimientos` registra programación y cierres validados. Las inspecciones, evidencias, hallazgos, planes y productos PDF/XLSX/ZIP se reutilizan desde `csc_*`; no se copian.

## Seguridad y trazabilidad

- Toda consulta y escritura se filtra por `fundacion_id`.
- Los roles operativos trabajan únicamente sobre sus UCA asignadas (fail-closed).
- Cerrar un mantenimiento como `EJECUTADO` requiere Coordinador, Gerente o Superadmin.
- Cada mutación deja registro en `aep_auditoria`.
- Los productos de inspección permanecen como borradores en Supervisión hasta aprobación humana.

## API

- `GET /api/ambientes-protectores/salud`
- `GET /api/ambientes-protectores/dashboard?unidad=...`
- `POST/PATCH /api/ambientes-protectores/activos`
- `POST/PATCH /api/ambientes-protectores/mantenimientos`
