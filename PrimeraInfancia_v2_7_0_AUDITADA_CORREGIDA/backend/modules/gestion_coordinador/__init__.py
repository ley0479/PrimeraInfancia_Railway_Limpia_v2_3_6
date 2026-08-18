"""Módulo independiente Gestión por Coordinador y Calendario Inteligente."""


def register_gestion_coordinador(app, database_path: str, upload_folder: str) -> None:
    from .routes import register_gestion_coordinador as _register
    _register(app, database_path, upload_folder)
