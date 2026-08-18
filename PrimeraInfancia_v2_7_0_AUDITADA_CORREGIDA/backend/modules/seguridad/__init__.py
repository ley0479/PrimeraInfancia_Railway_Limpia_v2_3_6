"""Módulo independiente de seguridad, roles, sesiones y fundaciones."""


def register_security(app, database_path: str) -> None:
    from .routes import register_seguridad
    from .services import activate_security_guard

    register_seguridad(app, database_path)
    activate_security_guard(app, database_path)
