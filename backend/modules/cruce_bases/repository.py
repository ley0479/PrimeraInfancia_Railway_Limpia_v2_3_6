from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from modules.dbapi_compat import sqlite3
from modules.sqlalchemy_compat import CoreCompatRepository

from .schema import SCHEMA_SQL


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


class CruceBasesRepository(CoreCompatRepository):
    """Repositorio de cruce de bases migrado a SQLAlchemy Core.

    Fase 2C.6 elimina la apertura directa de sqlite3 para novedades,
    movimientos de cruce y reportes por unidad/docente/coordinador.
    """

    def __init__(self, database_path: str | None = None):
        self.database_path = database_path

    def init_schema(self) -> None:
        self.execute_script(SCHEMA_SQL)

    def execute_many(self, sql: str, rows: list[tuple]) -> int:
        """Ejecuta lotes mediante el repositorio protegido por tenant."""
        return super().execute_many(sql, rows)

    def guardar_cruce(self, resultado: dict[str, Any], metadata: dict[str, Any]) -> int:
        resumen = resultado.get('resumen', {})
        # El INSERT necesita lastrowid para relacionar detalles y auditoría.
        # CompatConnection implementa ese contrato sobre PostgreSQL sin cerrar
        # el cursor al procesar RETURNING.
        with sqlite3.connect(self.database_path) as conn:
            cur = conn.cursor()
            cruce_id = cur.execute(
                """
                INSERT INTO cb_cruces
                (fundacion_id, usuario_id, usuario, mes, anio, periodo, archivo_anterior, archivo_actual,
                 ruta_anterior, ruta_actual, total_anterior, total_actual, nuevos, retirados, reemplazados,
                 trasladados, cambios_unidad, cambios_docente, cambios_acudiente, cambios_telefono,
                 cambios_direccion, cambios_total, resultado_json, errores_json, fecha_cruce)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.get('fundacion_id') or 1,
                    metadata.get('usuario_id'),
                    metadata.get('usuario') or 'sistema',
                    metadata.get('mes'),
                    metadata.get('anio'),
                    metadata.get('periodo'),
                    metadata.get('archivo_anterior'),
                    metadata.get('archivo_actual'),
                    metadata.get('ruta_anterior'),
                    metadata.get('ruta_actual'),
                    resumen.get('total_anterior', 0),
                    resumen.get('total_actual', 0),
                    resumen.get('nuevos', 0),
                    resumen.get('retirados', 0),
                    resumen.get('reemplazados', 0),
                    resumen.get('trasladados', 0),
                    resumen.get('cambios_unidad', 0),
                    resumen.get('cambios_docente', 0),
                    resumen.get('cambios_acudiente', 0),
                    resumen.get('cambios_telefono', 0),
                    resumen.get('cambios_direccion', 0),
                    resumen.get('cambios_total', 0),
                    json.dumps(resultado, ensure_ascii=False),
                    json.dumps(resultado.get('errores', []), ensure_ascii=False),
                    now_iso(),
                ),
            ).lastrowid

            detalle_rows: list[tuple] = []
            for tipo in ['nuevos', 'retirados', 'reemplazados', 'trasladados', 'cambios', 'cambios_unidad', 'cambios_docente', 'cambios_acudiente', 'cambios_telefono', 'cambios_direccion']:
                for item in resultado.get(tipo, []) or []:
                    detalle_rows.append((
                        cruce_id,
                        metadata.get('fundacion_id') or 1,
                        tipo,
                        item.get('documento') or item.get('documento_nuevo') or item.get('documento_retirado'),
                        item.get('nombre') or item.get('nombre_nuevo') or item.get('nombre_retirado'),
                        item.get('unidad_anterior') or item.get('unidad_retirado'),
                        item.get('unidad_actual') or item.get('unidad_nuevo'),
                        item.get('docente_anterior') or item.get('docente_retirado'),
                        item.get('docente_actual') or item.get('docente_nuevo'),
                        json.dumps(item, ensure_ascii=False),
                        now_iso(),
                    ))
            for row in detalle_rows:
                cur.execute(
                    """
                    INSERT INTO cb_detalles
                    (cruce_id, fundacion_id, tipo, documento, nombre, unidad_anterior, unidad_actual,
                     docente_anterior, docente_actual, datos_json, fecha_creacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
            cur.execute(
                """
                INSERT INTO cb_auditoria (cruce_id, fundacion_id, usuario_id, usuario, accion, detalle, fecha)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cruce_id, metadata.get('fundacion_id') or 1, metadata.get('usuario_id'), metadata.get('usuario'), 'CREAR_CRUCE_BASES', json.dumps(resumen, ensure_ascii=False), now_iso()),
            )
            conn.commit()
            return int(cruce_id)

    def actualizar_reportes(self, cruce_id: int, excel: str | None = None, pdf: str | None = None) -> None:
        self.execute_update(
            "UPDATE cb_cruces SET reporte_excel = COALESCE(?, reporte_excel), reporte_pdf = COALESCE(?, reporte_pdf) WHERE id = ?",
            (excel, pdf, cruce_id),
        )

    def ultimo_cruce(self, fundacion_id: int | None = None, superadmin: bool = False) -> dict[str, Any] | None:
        if superadmin:
            return self.fetch_one("SELECT * FROM cb_cruces ORDER BY fecha_cruce DESC, id DESC LIMIT 1")
        return self.fetch_one(
            "SELECT * FROM cb_cruces WHERE fundacion_id = ? ORDER BY fecha_cruce DESC, id DESC LIMIT 1",
            (fundacion_id or 1,),
        )
