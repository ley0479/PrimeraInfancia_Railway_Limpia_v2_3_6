"""Motor de Plantillas.

ALPHA52: exporta register_motor_plantillas de forma lazy para que los servicios,
migraciones y pruebas del motor puedan importarse sin cargar Flask en entornos
ligeros de validación.
"""
from __future__ import annotations


def register_motor_plantillas(*args, **kwargs):
    from .routes import register_motor_plantillas as _register
    return _register(*args, **kwargs)

__all__ = ['register_motor_plantillas']
