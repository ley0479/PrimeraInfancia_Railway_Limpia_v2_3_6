"""Fase 2C.6: operación central migrada progresivamente a SQLAlchemy Core.

Este módulo documenta y concentra utilidades para beneficiarios, usuarios,
unidades, movimientos y auditoría operativa. Las rutas públicas existentes se
conservan en backend/app.py para no romper compatibilidad.
"""

from .repository import OperacionCentralRepository

__all__ = ["OperacionCentralRepository"]
