"""Repositorio transicional de operación central.

La aplicación histórica conserva funciones en backend/app.py, pero desde Fase
2C.6 esas funciones usan get_db_connection(), que ahora retorna una conexión
compatible basada en SQLAlchemy Core. Este repositorio ofrece operaciones
explícitas para pruebas y para migrar gradualmente la lógica fuera de app.py.
"""
from __future__ import annotations

from typing import Any

from modules.sqlalchemy_compat import CoreCompatRepository


class OperacionCentralRepository(CoreCompatRepository):
    """Operaciones Core para beneficiarios, usuarios, unidades y auditoría."""

    def contar_beneficiarios(self, fundacion_id: int | None = None) -> int:
        if fundacion_id is None:
            row = self.fetch_one("SELECT COUNT(*) AS total FROM beneficiarios")
        else:
            row = self.fetch_one(
                "SELECT COUNT(*) AS total FROM beneficiarios WHERE COALESCE(fundacion_id, 1) = ?",
                (fundacion_id,),
            )
        return int((row or {}).get("total") or 0)

    def listar_unidades(self, fundacion_id: int | None = None) -> list[dict[str, Any]]:
        if fundacion_id is None:
            return self.fetch_all("SELECT * FROM unidades ORDER BY nombre")
        return self.fetch_all(
            "SELECT * FROM unidades WHERE COALESCE(fundacion_id, 1) = ? ORDER BY nombre",
            (fundacion_id,),
        )

    def registrar_auditoria_operativa(
        self,
        *,
        usuario: str,
        accion: str,
        archivo: str = "",
        total_registros: int = 0,
        cambios_detectados: str = "",
    ) -> int:
        return self.execute(
            """
            INSERT INTO auditoria
            (fecha, usuario, accion, archivo, total_registros, cambios_detectados, archivo_cargado, fecha_accion)
            VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (usuario, accion, archivo, total_registros, cambios_detectados, archivo),
        )
