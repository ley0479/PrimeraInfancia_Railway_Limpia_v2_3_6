"""Centro Documental institucional (registro lazy, sin DDL al importar)."""

from __future__ import annotations


def register_centro_documental(*args, **kwargs):
    from .routes import register_centro_documental as _register
    return _register(*args, **kwargs)


__all__ = ["register_centro_documental"]
