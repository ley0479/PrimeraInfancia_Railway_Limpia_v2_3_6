"""Centro Inteligente de Planeación y Calendario Operativo."""


def register_centro_planeacion(app, database_path: str, data_dir: str, output_folder: str) -> None:
    from .routes import register_centro_planeacion as register_routes
    register_routes(app, database_path, data_dir, output_folder)


__all__ = ["register_centro_planeacion"]
