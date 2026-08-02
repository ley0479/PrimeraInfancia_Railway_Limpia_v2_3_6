"""Módulo de Reportes Gerenciales Profesionales."""


def register_reportes_gerenciales(*args, **kwargs):
    from .routes import register_reportes_gerenciales as _register
    return _register(*args, **kwargs)


__all__ = ['register_reportes_gerenciales']
