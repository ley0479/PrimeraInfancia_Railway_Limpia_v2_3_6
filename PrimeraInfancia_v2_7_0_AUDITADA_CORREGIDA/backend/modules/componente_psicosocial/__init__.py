"""Componente Psicosocial especializado sobre Familias, Comunidad y Redes."""


def register_componente_psicosocial(app, database_path: str, data_dir: str, output_folder: str) -> None:
    from .routes import register_componente_psicosocial as register_routes
    register_routes(app, database_path, data_dir, output_folder)


__all__ = ["register_componente_psicosocial"]
