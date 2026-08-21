"""Migración aditiva y reversible del Motor Universal de Mapeo.

No modifica tablas operativas ni elimina información. La reversión se deja
explícita y exige ``allow_drop=True`` para impedir borrados accidentales.
"""
from __future__ import annotations

from modules.importaciones_universales.repository import UniversalImportRepository


def migrate(database_path: str) -> dict:
    UniversalImportRepository(database_path).init_schema()
    return {"status": "migrated", "mode": "additive", "tables": [
        "importaciones_universales", "perfiles_mapeo_universal",
        "importaciones_filas_staging", "auditoria_importaciones_universal",
        "unidades_identificadores_origen", "aliases_campos_universal",
    ]}


def downgrade(database_path: str, *, allow_drop: bool = False) -> dict:
    if not allow_drop:
        return {"status": "blocked", "reason": "La reversión requiere exportar auditoría y allow_drop=True."}
    repo = UniversalImportRepository(database_path)
    with repo.connect() as conn:
        for table in ("auditoria_importaciones_universal", "importaciones_filas_staging", "unidades_identificadores_origen", "aliases_campos_universal", "perfiles_mapeo_universal", "importaciones_universales"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    return {"status": "reverted"}
