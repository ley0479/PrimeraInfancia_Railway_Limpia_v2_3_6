"""Sistema Integral Administrativo y Financiero."""
def register_administrativo_financiero(app,database_path,data_dir,output_folder):
    from .routes import register_routes
    register_routes(app,database_path,data_dir,output_folder)
