#!/usr/bin/env python3
"""Pruebas autocontenidas de túnel, usuarios, fundaciones y recuperación 2.4.1.

Se ejecutan sin instalar Flask/Werkzeug: crean dobles mínimos para invocar las
rutas de seguridad contra una base SQLite temporal. No reemplazan la prueba en
Windows/Railway, pero validan SQL, aislamiento y contratos JSON críticos.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


class FakeResponse(dict):
    def __init__(self, value=None):
        super().__init__(value or {})
        self.status_code = 200
        self.headers = {}

    def get_json(self):
        return dict(self)


class CurrentApp:
    config = {}


request = SimpleNamespace(
    method="GET",
    args={},
    headers={},
    form={},
    remote_addr="127.0.0.1",
    host="127.0.0.1:5000",
    path="/",
    url_root="http://127.0.0.1:5000/",
    is_secure=False,
    url="http://127.0.0.1:5000/",
    get_json=lambda silent=True: {},
)
g = SimpleNamespace(current_user={})
current_app = CurrentApp()


def jsonify(value=None, **kwargs):
    if value is None:
        value = kwargs
    return FakeResponse(value)


def redirect(url, code=302):
    response = FakeResponse({"redirect": url})
    response.status_code = code
    return response


flask = types.ModuleType("flask")
flask.jsonify = jsonify
flask.request = request
flask.g = g
flask.current_app = current_app
flask.has_request_context = lambda: True
flask.redirect = redirect
sys.modules["flask"] = flask


def generate_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000).hex()
    return f"test-pbkdf2${salt}${digest}"


def check_password_hash(stored: str, password: str) -> bool:
    try:
        marker, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if marker != "test-pbkdf2":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000).hex()
    return secrets.compare_digest(candidate, digest)


werkzeug = types.ModuleType("werkzeug")
werkzeug_security = types.ModuleType("werkzeug.security")
werkzeug_security.generate_password_hash = generate_password_hash
werkzeug_security.check_password_hash = check_password_hash
werkzeug.security = werkzeug_security
sys.modules["werkzeug"] = werkzeug
sys.modules["werkzeug.security"] = werkzeug_security


class FakeApp:
    def __init__(self, config):
        self.config = config
        self.routes = {}

    def route(self, path, methods=None):
        methods = methods or ["GET"]

        def decorator(func):
            for method in methods:
                self.routes[(path, method.upper())] = func
            return func

        return decorator


def set_request(method="GET", body=None, args=None, path="/", host="127.0.0.1:5000"):
    request.method = method
    request.args = args or {}
    request.headers = {"User-Agent": "test-suite"}
    request.form = {}
    request.remote_addr = "127.0.0.1"
    request.host = host
    request.path = path
    request.url_root = f"http://{host}/"
    request.url = f"http://{host}{path}"
    request.get_json = lambda silent=True: body or {}


def unwrap(result):
    if isinstance(result, tuple):
        response, status = result[0], int(result[1])
    else:
        response, status = result, int(getattr(result, "status_code", 200))
    return dict(response), status


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="pi_v241_") as temp_dir:
        temp = Path(temp_dir)
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
            "PUBLIC_TUNNEL_MODE": False,
            "ALLOW_LOCAL_RECOVERY_CODE": True,
            "LOCAL_RECOVERY_CODE_LENGTH": 10,
            "PASSWORD_RESET_EXPIRES_MINUTES": 30,
            "PASSWORD_RESET_PUBLIC_URL": "http://127.0.0.1:5000",
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
        current_app.config = config
        app = FakeApp(config)

        from modules.seguridad.routes import register_seguridad
        from modules.seguridad.services import connect, ensure_security_schema

        ensure_security_schema(str(database))
        conn = connect(str(database))
        # Segunda fundación ficticia para probar aislamiento sin depender de activos pesados.
        now = "2026-08-04T00:00:00"
        conn.execute(
            "INSERT INTO fundaciones (id,nombre,estado,plan,fecha_creacion,fecha_actualizacion) VALUES (2,'Fundación Prueba B','ACTIVA','PRUEBA',?,?)",
            (now, now),
        )
        super_password = "SuperAdmin#2026"
        conn.execute(
            """
            INSERT INTO usuarios_app
            (username,email,password_hash,rol,fundacion_id,activo,estado,nombre_completo,fecha_creacion,fecha_actualizacion)
            VALUES ('super.local','super@local.test',?,'SUPERADMIN',1,1,'ACTIVO','Super Local',?,?)
            """,
            (generate_password_hash(super_password), now, now),
        )
        conn.commit()
        super_row = conn.execute("SELECT * FROM usuarios_app WHERE username='super.local'").fetchone()
        conn.close()
        super_user = dict(super_row)
        g.current_user = super_user

        register_seguridad(app, str(database))

        # Una fundación existente se devuelve como entidad reutilizable; nunca
        # se obliga a crear un duplicado para poder asignar usuarios.
        set_request("POST", {"nombre": "  FUNDACIÓN PRUEBA B  "}, path="/api/fundaciones")
        duplicate_foundation, status = unwrap(app.routes[("/api/fundaciones", "POST")]())
        assert_true(status == 409, f"Duplicado de fundación no devolvió 409: {status} {duplicate_foundation}")
        assert_true(
            duplicate_foundation.get("code") == "FUNDACION_EXISTENTE"
            and duplicate_foundation.get("fundacion_id") == 2
            and duplicate_foundation.get("reutilizable") is True,
            f"Duplicado no devolvió la fundación reutilizable: {duplicate_foundation}",
        )

        # Crear usuarios en dos tenants y comprobar que sus credenciales funcionan.
        create_user = app.routes[("/api/usuarios", "POST")]
        set_request("POST", {
            "username": "gerente.a",
            "email": "gerente.a@example.test",
            "password": "GerenteA#2026",
            "rol": "GERENTE",
            "fundacion_id": 1,
            "nombre_completo": "Gerente A",
        }, path="/api/usuarios")
        body, status = unwrap(create_user())
        assert_true(status == 201, f"No creó usuario A: {status} {body}")
        user_a_id = body["usuario"]["id"]

        g.current_user = super_user
        set_request("POST", {
            "username": "gerente.b",
            "email": "gerente.b@example.test",
            "password": "GerenteB#2026",
            "rol": "GERENTE",
            "fundacion_id": 2,
            "nombre_completo": "Gerente B",
        }, path="/api/usuarios")
        body, status = unwrap(create_user())
        assert_true(status == 201, f"No creó usuario B: {status} {body}")
        user_b_id = body["usuario"]["id"]

        login = app.routes[("/api/auth/login", "POST")]
        set_request("POST", {"username": "gerente.a", "password": "GerenteA#2026"}, path="/api/auth/login")
        login_a, status = unwrap(login())
        assert_true(status == 200 and login_a["usuario"]["fundacion_id"] == 1, f"Login A falló: {status} {login_a}")

        set_request("POST", {"username": "gerente.b", "password": "GerenteB#2026"}, path="/api/auth/login")
        login_b, status = unwrap(login())
        assert_true(status == 200 and login_b["usuario"]["fundacion_id"] == 2, f"Login B falló: {status} {login_b}")

        # GERENTE solo lista usuarios y fundación propios.
        g.current_user = login_a["usuario"]
        set_request("GET", path="/api/usuarios")
        listed, status = unwrap(app.routes[("/api/usuarios", "GET")]())
        assert_true(status == 200 and all(item["fundacion_id"] == 1 for item in listed["usuarios"]), "Usuario A vio otro tenant")
        set_request("GET", path="/api/fundaciones")
        foundations, status = unwrap(app.routes[("/api/fundaciones", "GET")]())
        assert_true(status == 200 and [item["id"] for item in foundations["fundaciones"]] == [1], "Usuario A vio otra fundación")

        # GERENTE A no puede editar al usuario de B.
        set_request("PUT", {"username": "gerente.b", "email": "gerente.b@example.test", "rol": "GERENTE"}, path=f"/api/usuarios/{user_b_id}")
        denied, status = unwrap(app.routes[("/api/usuarios/<int:usuario_id>", "PUT")](user_b_id))
        assert_true(status == 403, f"No bloqueó edición cruzada: {status} {denied}")

        # Recuperación local por código de un solo uso.
        g.current_user = {}
        set_request("POST", {"username": "gerente.a"}, path="/api/auth/recuperar")
        recovery, status = unwrap(app.routes[("/api/auth/recuperar", "POST")]())
        assert_true(status == 200 and recovery.get("delivery") == "local_code", f"No generó código local: {status} {recovery}")
        code = recovery["local_recovery_code"]
        set_request("POST", {"codigo": code, "password": "NuevaClaveA#2026"}, path="/api/auth/restablecer")
        reset, status = unwrap(app.routes[("/api/auth/restablecer", "POST")]())
        assert_true(status == 200, f"No restableció con código: {status} {reset}")
        set_request("POST", {"username": "gerente.a", "password": "NuevaClaveA#2026"}, path="/api/auth/login")
        relogin, status = unwrap(login())
        assert_true(status == 200, f"Login después de recuperación falló: {status} {relogin}")

        # Restablecimiento administrativo genera clave temporal y exige cambio.
        g.current_user = super_user
        set_request("POST", {"reactivar": False}, path=f"/api/usuarios/{user_b_id}/restablecer-password")
        admin_reset, status = unwrap(app.routes[("/api/usuarios/<int:usuario_id>/restablecer-password", "POST")](user_b_id))
        assert_true(status == 200 and admin_reset.get("temporary_password"), f"Reset administrativo falló: {status} {admin_reset}")
        set_request("POST", {"username": "gerente.b", "password": admin_reset["temporary_password"]}, path="/api/auth/login")
        temp_login, status = unwrap(login())
        assert_true(status == 200 and temp_login["usuario"]["debe_cambiar_password"], "Clave temporal no permite login/cambio obligatorio")

        # Dependencias, eliminación lógica y restauración.
        g.current_user = super_user
        set_request("GET", path=f"/api/usuarios/{user_a_id}/dependencias")
        dep, status = unwrap(app.routes[("/api/usuarios/<int:usuario_id>/dependencias", "GET")](user_a_id))
        assert_true(status == 200 and dep["eliminacion"] == "LOGICA", "Diagnóstico de usuario falló")
        set_request("DELETE", args={"accion": "eliminar"}, path=f"/api/usuarios/{user_a_id}")
        deleted, status = unwrap(app.routes[("/api/usuarios/<int:usuario_id>", "DELETE")](user_a_id))
        assert_true(status == 200 and deleted["eliminacion"] == "LOGICA", f"Eliminación usuario falló: {status} {deleted}")
        conn = connect(str(database))
        row = conn.execute("SELECT activo,estado FROM usuarios_app WHERE id=?", (user_a_id,)).fetchone()
        conn.close()
        assert_true(row["activo"] == 0 and row["estado"] == "ELIMINADO", "Usuario no quedó eliminado lógicamente")

        set_request("PUT", {
            "username": "gerente.a", "email": "gerente.a@example.test", "rol": "GERENTE",
            "fundacion_id": 1, "activo": 1, "estado": "ACTIVO", "debe_cambiar_password": False,
        }, path=f"/api/usuarios/{user_a_id}")
        restored_user, status = unwrap(app.routes[("/api/usuarios/<int:usuario_id>", "PUT")](user_a_id))
        assert_true(status == 200 and restored_user["usuario"]["estado"] == "ACTIVO", "No restauró usuario eliminado")
        conn = connect(str(database))
        restored_row = conn.execute("SELECT activo,estado,eliminado_en FROM usuarios_app WHERE id=?", (user_a_id,)).fetchone()
        conn.close()
        assert_true(restored_row["activo"] == 1 and restored_row["estado"] == "ACTIVO" and restored_row["eliminado_en"] is None, "Restauración de usuario incompleta")
        set_request("POST", {"username": "gerente.a", "password": "NuevaClaveA#2026"}, path="/api/auth/login")
        restored_login, status = unwrap(login())
        assert_true(status == 200 and restored_login["usuario"]["fundacion_id"] == 1, "Usuario restaurado no pudo iniciar sesión")

        # El indicador de cambio obligatorio se puede gestionar sin reemplazar la clave.
        conn = connect(str(database))
        before_hash = conn.execute("SELECT password_hash FROM usuarios_app WHERE id=?", (user_b_id,)).fetchone()["password_hash"]
        conn.close()
        set_request("PUT", {
            "username": "gerente.b", "email": "gerente.b@example.test", "rol": "GERENTE",
            "fundacion_id": 2, "activo": 1, "estado": "ACTIVO", "debe_cambiar_password": True,
        }, path=f"/api/usuarios/{user_b_id}")
        forced, status = unwrap(app.routes[("/api/usuarios/<int:usuario_id>", "PUT")](user_b_id))
        assert_true(status == 200 and forced["usuario"]["debe_cambiar_password"] == 1, "No actualizó cambio obligatorio")
        conn = connect(str(database))
        after_hash = conn.execute("SELECT password_hash FROM usuarios_app WHERE id=?", (user_b_id,)).fetchone()["password_hash"]
        conn.close()
        assert_true(before_hash == after_hash, "Cambió la contraseña al editar solo el indicador")

        # ELIMINADA no puede asignarse mediante PUT; debe pasar por eliminación lógica controlada.
        set_request("PUT", {"nombre": "Fundación B", "estado": "ELIMINADA"}, path="/api/fundaciones/2")
        invalid_delete, status = unwrap(app.routes[("/api/fundaciones/<int:fundacion_id>", "PUT")](2))
        assert_true(status == 400 and invalid_delete.get("code") == "FOUNDATION_DELETE_REQUIRES_ACTION", "PUT permitió eliminar fundación")

        # Fundación 2 no es la de la sesión SUPERADMIN (fundación 1), puede eliminarse y restaurarse.
        set_request("GET", path="/api/fundaciones/2/dependencias")
        fdep, status = unwrap(app.routes[("/api/fundaciones/<int:fundacion_id>/dependencias", "GET")](2))
        assert_true(status == 200 and fdep["dependencias"]["total"] >= 1, "No contó dependencias de fundación")
        set_request("DELETE", args={"accion": "eliminar"}, path="/api/fundaciones/2")
        fdel, status = unwrap(app.routes[("/api/fundaciones/<int:fundacion_id>", "DELETE")](2))
        assert_true(status == 200 and fdel["eliminacion"] == "LOGICA", f"Eliminación fundación falló: {status} {fdel}")
        set_request("DELETE", args={"estado": "ACTIVA"}, path="/api/fundaciones/2")
        restored, status = unwrap(app.routes[("/api/fundaciones/<int:fundacion_id>", "DELETE")](2))
        assert_true(status == 200, f"Restauración fundación falló: {status} {restored}")

        # Contratos estáticos del túnel y frontend.
        local_bat = (ROOT / "INICIAR_PLATAFORMA_LOCAL.bat").read_text(encoding="utf-8")
        launcher_ps = (ROOT / "scripts_windows" / "iniciar_plataforma.ps1").read_text(encoding="utf-8")
        tunnel_ps = (ROOT / "scripts_windows" / "iniciar_tunel_cloudflare.ps1").read_text(encoding="utf-8")
        frontend_js = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
        app_source = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")
        services_source = (ROOT / "backend" / "modules" / "seguridad" / "services.py").read_text(encoding="utf-8")
        assert_true("iniciar_plataforma.ps1" in local_bat and "-Mode Local" in local_bat, "El BAT local no delega al lanzador robusto")
        assert_true("/api/acceso/ping" not in launcher_ps, "El inicio local aún usa ping autenticado")
        assert_true("/api/health" in launcher_ps and "/api/health" in tunnel_ps, "Falta healthcheck público")
        assert_true("CREDENCIALES_INICIALES_LOCAL.txt" in launcher_ps, "No se documentan credenciales iniciales aleatorias")
        assert_true("secrets.token_urlsafe(64)" in launcher_ps, "SECRET_KEY/JWT_SECRET_KEY locales no son aleatorias")
        assert_true("AdminLocal2026*" not in launcher_ps, "Persiste una contraseña local fija")
        assert_true("local-dev-secret-key" not in launcher_ps, "Persiste una SECRET_KEY local fija")
        assert_true("RedirectStandardError" in tunnel_ps and "trycloudflare.com" in tunnel_ps, "El túnel no captura URL robustamente")
        assert_true("Stop-VerifiedLocalBackend" in tunnel_ps and "public_tunnel_mode" in tunnel_ps, "El túnel no fuerza modo seguro")
        assert_true("cloudflared_tunnel.pid" in tunnel_ps and "Stop-ActiveTunnel" in tunnel_ps, "El túnel no controla su proceso")
        assert_true("'public_tunnel_mode'" in app_source and "'server_mode'" in app_source, "Health no informa modo de ejecución")
        assert_true("ENLACE_PUBLICO_TUNEL.txt" in services_source, "Recuperación por correo no resuelve URL del túnel")
        for required in ("Editar", "Eliminar", "Restablecer clave", "local_recovery_code"):
            assert_true(required in frontend_js, f"Frontend no contiene {required}")

    print("PASS: túnel, usuarios, fundaciones, aislamiento y recuperación v2.4.1")


if __name__ == "__main__":
    main()
