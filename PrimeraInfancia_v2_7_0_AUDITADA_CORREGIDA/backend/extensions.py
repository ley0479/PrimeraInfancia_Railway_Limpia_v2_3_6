"""Extensiones Flask inicializadas de forma diferida."""
from __future__ import annotations

from flask_cors import CORS

cors = CORS()


def init_extensions(app, *, origins) -> None:
    """Inicializa CORS únicamente cuando existe una allowlist explícita."""
    if app.extensions.get("primera_infancia_cors_initialized"):
        return
    if origins:
        cors.init_app(
            app,
            origins=origins,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Auth-Token", "X-Requested-With"],
            expose_headers=[
                "Content-Disposition",
                "X-Auth-Instance-ID",
                "X-Auth-Environment",
                "X-Auth-Database-Backend",
                "X-Auth-Database-Target",
                "X-Auth-Env-SHA256",
                "X-Auth-Request-ID",
                "X-Client-Request-ID",
                "X-Login-Duration-Ms",
                "X-Login-DB-Retries",
            ],
            supports_credentials=False,
            max_age=86400,
        )
    app.extensions["primera_infancia_cors_initialized"] = True
