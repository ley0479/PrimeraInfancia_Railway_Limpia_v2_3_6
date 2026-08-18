from __future__ import annotations


def register_theme_manager(app, database_path: str) -> None:
    from .routes import register_theme_manager as _register_theme_manager
    return _register_theme_manager(app, database_path)


__all__ = ['register_theme_manager']
