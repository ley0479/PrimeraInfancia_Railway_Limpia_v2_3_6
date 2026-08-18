"""Módulo de Paquete Mensual Completo."""


def register_paquete_mensual(*args, **kwargs):
    from .routes import register_paquete_mensual as _register
    return _register(*args, **kwargs)


__all__ = ['register_paquete_mensual']
