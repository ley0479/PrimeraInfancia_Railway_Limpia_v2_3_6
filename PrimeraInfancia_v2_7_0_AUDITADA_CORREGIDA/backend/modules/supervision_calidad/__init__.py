"""Centro Inteligente de Supervisión, Auditoría y Calidad."""


def register_supervision_calidad(app, database_path: str, data_dir: str, output_folder: str) -> None:
    from .routes import register_routes
    register_routes(app, database_path, data_dir, output_folder)
