from __future__ import annotations


def register_base_maestra(app, database_path: str, upload_folder: str, output_folder: str) -> None:
    # Importación diferida para que las migraciones puedan cargar repositorio/schema
    # sin depender de Flask durante validaciones offline.
    from .routes import register_base_maestra as _register
    _register(app, database_path, upload_folder, output_folder)


__all__ = ['register_base_maestra']
