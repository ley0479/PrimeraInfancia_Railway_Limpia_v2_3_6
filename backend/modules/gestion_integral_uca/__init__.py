"""Expediente Operativo por UCA, Ruta Operativa y Biblioteca Oficial ICBF."""


def register_gestion_integral_uca(app, database_path: str, data_dir: str, output_folder: str) -> None:
    from .routes import register_routes

    register_routes(app, database_path, data_dir, output_folder)
