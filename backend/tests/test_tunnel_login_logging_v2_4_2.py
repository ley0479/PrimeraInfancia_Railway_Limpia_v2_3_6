#!/usr/bin/env python3
"""Regresión del login por túnel, huella de instancia y logging 2.4.2.

No abre Cloudflare ni requiere credenciales reales. Comprueba el contrato del
healthcheck, el reporte no vacío y sanitizado, el login con Host de túnel y los
scripts que impiden publicar otra copia del proyecto.
"""
from __future__ import annotations

import hashlib
import secrets
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TESTS = BACKEND / "tests"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(TESTS))


def require(path: str, *needles: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8-sig", errors="strict")
    for needle in needles:
        if needle not in text:
            raise AssertionError(f"{path} no contiene {needle!r}")
    return text


def assert_true(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_runtime_diagnostics() -> None:
    from modules.seguridad.runtime_diagnostics import (
        logging_health,
        project_instance_id,
        write_exception_report,
    )

    with tempfile.TemporaryDirectory(prefix="pi_v242_logs_") as raw:
        root = Path(raw)
        data = root / "data"
        logs = data / "logs"
        config = {
            "PROJECT_DIR": str(root),
            "DATA_DIR": str(data),
            "LOG_FOLDER": str(logs),
            "DATABASE_PATH": str(data / "database.sqlite3"),
            "APP_VERSION": "2.4.2-test",
            "APP_ENV": "development",
            "SERVER_MODE": "TUNEL_ONLINE",
            "PROJECT_INSTANCE_ID": "instance-test-242",
        }
        assert_true(project_instance_id(config) == "instance-test-242", "No respetó PROJECT_INSTANCE_ID explícito")
        config_without_id = dict(config)
        config_without_id["PROJECT_INSTANCE_ID"] = ""
        first = project_instance_id(config_without_id)
        second = project_instance_id(config_without_id)
        assert_true(first == second and len(first) == 16, "La huella calculada no es estable")

        try:
            raise RuntimeError("database locked password=NoDebeAparecer token=NoDebeAparecer")
        except RuntimeError as exc:
            report = write_exception_report(exc, "trace-v242", config)
        assert_true(report["written"] is True, f"No escribió reporte: {report}")
        target = root / report["reference"]
        content = target.read_text(encoding="utf-8")
        assert_true(target.stat().st_size > 0, "El reporte quedó vacío")
        assert_true("trace-v242" in content and "TRACEBACK" in content, "Reporte incompleto")
        assert_true("NoDebeAparecer" not in content and "[REDACTED]" in content, "El reporte no ocultó secretos")
        health = logging_health(config)
        assert_true(health.get("writable") is True, f"La carpeta de logs no es escribible: {health}")


def test_tunnel_host_login() -> None:
    # Reutiliza los dobles de Flask/Werkzeug ya probados en la suite 2.4.1.
    import test_tunnel_admin_recovery_v2_4_1 as helpers

    with tempfile.TemporaryDirectory(prefix="pi_v242_login_") as raw:
        temp = Path(raw)
        database = temp / "database.sqlite3"
        data_dir = temp / "data"
        data_dir.mkdir()
        config = {
            "SINGLE_TENANT_MODE": False,
            "MULTI_TENANT_STRICT": True,
            "TENANT_STORAGE_ISOLATION": True,
            "MULTI_TENANT_SCHEMA_VERSION": 3,
            "DATA_DIR": str(data_dir),
            "BASE_DIR": str(BACKEND),
            "APP_ENV": "development",
            "PUBLIC_TUNNEL_MODE": True,
            "ALLOW_LOCAL_RECOVERY_CODE": False,
            "PASSWORD_RESET_EXPIRES_MINUTES": 30,
            "PASSWORD_RESET_PUBLIC_URL": "https://example.trycloudflare.com",
            "RESEND_API_KEY": "",
            "PASSWORD_RESET_FROM_EMAIL": "",
            "ALLOW_PASSWORD_RESET_TOKEN_RESPONSE": False,
            "LOGIN_MAX_ATTEMPTS": 5,
            "LOGIN_WINDOW_SECONDS": 900,
            "LOGIN_LOCK_SECONDS": 900,
            "RECOVERY_MAX_ATTEMPTS": 10,
            "RECOVERY_WINDOW_SECONDS": 3600,
            "RECOVERY_LOCK_SECONDS": 3600,
            "RESET_MAX_ATTEMPTS": 8,
            "RESET_WINDOW_SECONDS": 900,
            "RESET_LOCK_SECONDS": 900,
            "MIN_PASSWORD_LENGTH": 12,
            "SESSION_LIFETIME_MINUTES": 720,
            "SQLITE_TIMEOUT_SECONDS": 30,
            "ALLOW_LEGACY_QUERY_TOKENS": False,
        }
        helpers.current_app.config = config
        app = helpers.FakeApp(config)

        from modules.seguridad.routes import register_seguridad
        from modules.seguridad.services import connect, ensure_security_schema

        ensure_security_schema(str(database))
        password = "TunelSeguro#2026"
        now = "2026-08-04T00:00:00"
        conn = connect(str(database))
        conn.execute(
            """
            INSERT INTO usuarios_app
            (username,email,password_hash,rol,fundacion_id,activo,estado,nombre_completo,fecha_creacion,fecha_actualizacion)
            VALUES ('tunel.user','tunel.user@example.test',?,'SUPERADMIN',1,1,'ACTIVO','Usuario Túnel',?,?)
            """,
            (helpers.generate_password_hash(password), now, now),
        )
        conn.execute(
            """
            INSERT INTO usuarios_app
            (username,email,password_hash,rol,fundacion_id,activo,estado,nombre_completo,fecha_creacion,fecha_actualizacion)
            VALUES ('hash.roto','hash.roto@example.test','hash-invalido','GERENTE',1,1,'ACTIVO','Hash Roto',?,?)
            """,
            (now, now),
        )
        conn.commit()
        conn.close()
        register_seguridad(app, str(database))
        login = app.routes[("/api/auth/login", "POST")]

        helpers.set_request(
            "POST",
            {"username": "tunel.user", "password": password},
            path="/api/auth/login",
            host="example.trycloudflare.com",
        )
        helpers.request.headers.update({
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "example.trycloudflare.com",
            "X-Client-Request-ID": "tunnel-login-test",
        })
        body, status = helpers.unwrap(login())
        assert_true(status == 200 and body.get("token"), f"Login por host de túnel falló: {status} {body}")
        assert_true(body.get("request_id") == "tunnel-login-test", "No propagó el ID de solicitud")

        helpers.set_request(
            "POST",
            {"username": "hash.roto", "password": "cualquier-clave"},
            path="/api/auth/login",
            host="example.trycloudflare.com",
        )
        broken, status = helpers.unwrap(login())
        assert_true(status == 401 and broken.get("code") == "INVALID_CREDENTIALS", "Un hash roto produjo error técnico")


def test_static_contracts() -> None:
    env = require(".env.example", "APP_VERSION=2.7.2-document-center", "PROJECT_INSTANCE_ID=")
    assert_true("AdminLocal2026*" not in env, ".env.example contiene credencial local")

    require("INICIAR_PLATAFORMA_LOCAL.bat", "iniciar_plataforma.ps1", "-Mode Local")
    launcher = require(
        "scripts_windows/iniciar_plataforma.ps1",
        "PRIMERA INFANCIA 2.7.0",
        "PROJECT_INSTANCE_ID",
        "project_instance_id",
        "ExpectedTunnel",
        r"data\logs",
        "/api/health",
    )
    assert_true("/api/acceso/ping" not in launcher, "El script local usa un ping autenticado")

    tunnel = require(
        "scripts_windows/iniciar_tunel_cloudflare.ps1",
        "ExpectedInstanceId",
        "Test-ExpectedBackend",
        "project_instance_id",
        "public_tunnel_mode",
        "data\\logs",
        "Instancia verificada",
    )
    assert_true("Test-HttpOk $PublicHealth" not in tunnel, "El túnel acepta cualquier health 200 sin comprobar instancia")

    require(
        "scripts_windows/diagnosticar_login_tunel.ps1",
        "DIAGNOSTICO_TUNEL_LOGIN",
        "Prueba segura de ruta login",
        "data\\logs",
        "backend\\logs es un marcador",
    )
    require("DIAGNOSTICAR_LOGIN_TUNEL.bat", "diagnosticar_login_tunel.ps1")
    require("ABRIR_LOGS_ERRORES.bat", "data\\logs", "backend\\logs no es la carpeta operativa")

    frontend = require(
        "frontend/js/app.js",
        "X-Client-Request-ID",
        "trace_id",
        "log_file",
        "DIAGNOSTICAR_LOGIN_TUNEL.bat",
        "LOGIN_DATABASE_BUSY",
    )
    assert_true("await resp.json();" not in frontend[frontend.index("function configurarFormularioLogin"):frontend.index("let passwordResetToken")],
                "El login todavía falla al parsear una respuesta no JSON")

    require(
        "backend/modules/seguridad/services.py",
        "_WAL_INITIALIZED_DATABASES",
        "PRAGMA busy_timeout",
        "database is locked",
    )
    require(
        "backend/modules/seguridad/routes.py",
        "LOGIN_DATABASE_BUSY",
        "client_request_id",
        "g.error_context",
        "_safe_warning",
    )
    require(
        "backend/modules/seguridad/runtime_diagnostics.py",
        "RotatingFileHandler",
        "os.fsync",
        "logs_fallback",
        "[REDACTED]",
    )
    require(
        "backend/app.py",
        "project_instance_id",
        "write_exception_report",
        "X-Trace-Id",
        "data/logs",
    )


def main() -> None:
    test_runtime_diagnostics()
    test_tunnel_host_login()
    test_static_contracts()
    print("PASS test_tunnel_login_logging_v2_4_2")


if __name__ == "__main__":
    main()
