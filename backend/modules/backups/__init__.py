"""Módulo independiente de Backups y Restauración."""


def register_backups(*args, **kwargs):
    from .routes import register_backups as _register_backups
    return _register_backups(*args, **kwargs)


__all__ = ['register_backups']
