"""Centro de Integraciones, Configuración y Administración General."""
def register_integraciones_configuracion(app,database_path,project_root,data_dir):
    from .routes import register_routes
    register_routes(app,database_path,project_root,data_dir)
