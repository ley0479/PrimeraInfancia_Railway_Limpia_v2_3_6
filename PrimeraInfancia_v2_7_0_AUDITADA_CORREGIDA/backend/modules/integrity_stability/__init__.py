"""Motor transversal de integridad, supervisión técnica y estabilidad."""

def register_integrity_stability(app, project_root: str, data_dir: str, database_path: str | None = None) -> None:
    from .routes import register_routes
    register_routes(app, project_root, data_dir, database_path)
