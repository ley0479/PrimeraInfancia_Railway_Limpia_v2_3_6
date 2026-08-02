"""Servicios de operación central para Fase 2C.6.

La lógica masiva de carga Cuéntame y generación de formatos continúa en
backend/app.py por compatibilidad, pero se deja este punto de expansión para
migrar servicios por dominio sin volver a abrir sqlite3 directamente.
"""
from __future__ import annotations

from .repository import OperacionCentralRepository


def resumen_operacion(fundacion_id: int | None = None) -> dict:
    repo = OperacionCentralRepository()
    return {
        "beneficiarios": repo.contar_beneficiarios(fundacion_id),
        "unidades": len(repo.listar_unidades(fundacion_id)),
    }
