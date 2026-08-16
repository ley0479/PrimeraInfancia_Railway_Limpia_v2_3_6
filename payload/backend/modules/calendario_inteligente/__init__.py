"""Calendario Inteligente de Entregables.

La importación del blueprint se hace de forma diferida para permitir pruebas de
servicios y repositorio en entornos donde Flask no esté instalado.
"""


def register_calendario_inteligente(app, database_path: str, upload_folder: str) -> None:
    from .routes import register_calendario_inteligente as _register
    return _register(app, database_path, upload_folder)


__all__ = ["register_calendario_inteligente"]
