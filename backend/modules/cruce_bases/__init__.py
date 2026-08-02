"""Módulo de cruce mensual de bases Cuéntame."""

__all__ = ["register_cruce_bases"]


def register_cruce_bases(*args, **kwargs):
    # Import diferido para que repositorios/servicios puedan probarse sin Flask.
    from .routes import register_cruce_bases as _register
    return _register(*args, **kwargs)
