#!/usr/bin/env python3
"""Pruebas de regresión del login concurrente y estable 2.5.1.

Se ejecutan sin Flask/Werkzeug instalados, reutilizando los dobles mínimos de la
suite 2.4.1. Validan transacciones SQLite, sesiones simultáneas, reintentos
acotados, ausencia de falsos bloqueos y el contrato del frontend.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TESTS = BACKEND / "tests"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(TESTS))

import test_tunnel_admin_recovery_v2_4_1 as helpers  # noqa: E402


METRICS: dict[str, object] = {}


def assert_true(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def configure() -> dict:
    config = {
        "SINGLE_TENANT_MODE": False,
        "MULTI_TENANT_STRICT": True,
        "TENANT_STORAGE_ISOLATION": True,
        "MULTI_TENANT_SCHEMA_VERSION": 3,
        "APP_ENV": "development",
        "PUBLIC_TUNNEL_MODE": False,
        "SESSION_LIFETIME_MINUTES": 720,
        "LOGIN_MAX_ATTEMPTS": 5,
        "LOGIN_WINDOW_SECONDS": 900,
        "LOGIN_LOCK_SECONDS": 900,
        "LOGIN_DB_RETRY_ATTEMPTS": 6,
        "LOGIN_DB_BUSY_TIMEOUT_MS": 100,
        "LOGIN_DB_RETRY_BASE_MS": 35,
        "LOGIN_DB_RETRY_BUDGET_MS": 1500,
        "LOGIN_SLOW_THRESHOLD_MS": 1500,
        "SQLITE_TIMEOUT_SECONDS": 30,
        "MIN_PASSWORD_LENGTH": 12,
        "ALLOW_LEGACY_QUERY_TOKENS": False,
    }
    helpers.current_app.config = config
    return config


def create_fixture(database: Path):
    from modules.seguridad.services import connect, ensure_security_schema

    ensure_security_schema(str(database))
    now = "2026-08-05T00:00:00"
    password = "AdminConcurrente#2026"
    conn = connect(str(database))
    conn.execute(
        """
        INSERT INTO usuarios_app
        (username,email,password_hash,rol,fundacion_id,activo,estado,nombre_completo,
         fecha_creacion,fecha_actualizacion,debe_cambiar_password)
        VALUES (?,?,?,?,?,1,'ACTIVO',?,?,?,0)
        """,
        (
            "admin.concurrente",
            "admin.concurrente@example.test",
            helpers.generate_password_hash(password),
            "SUPERADMIN",
            1,
            "Administrador Concurrente",
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM usuarios_app WHERE username='admin.concurrente'"
    ).fetchone()
    conn.close()
    return row, password


def test_parallel_sessions(database: Path, user_row) -> None:
    from modules.seguridad.services import connect, create_login_session_atomic

    total = 8

    def worker(index: int):
        started = time.monotonic()
        token, payload, meta = create_login_session_atomic(
            str(database),
            user_row,
            identifiers=(
                "admin.concurrente",
                "admin.concurrente@example.test",
            ),
            request_id=f"parallel-{index}",
            ip=f"10.0.0.{index + 1}",
            user_agent=f"device-{index}",
        )
        return {
            "token": token,
            "payload": payload,
            "meta": meta,
            "elapsed": time.monotonic() - started,
        }

    results = []
    with ThreadPoolExecutor(max_workers=total) as pool:
        futures = [pool.submit(worker, index) for index in range(total)]
        for future in as_completed(futures):
            results.append(future.result())

    assert_true(len(results) == total, "No finalizaron todas las sesiones concurrentes")
    assert_true(len({item["token"] for item in results}) == total, "Se repitieron tokens de sesión")
    assert_true(
        all(item["payload"].get("username") == "admin.concurrente" for item in results),
        "Alguna sesión devolvió otro usuario",
    )
    assert_true(
        max(item["elapsed"] for item in results) < 2.0,
        f"Una sesión concurrente superó 2 s: {max(item['elapsed'] for item in results):.3f}",
    )

    conn = connect(str(database))
    active = int(
        conn.execute(
            "SELECT COUNT(*) AS total FROM sesiones_usuario WHERE usuario_id=? AND activa=1",
            (user_row["id"],),
        ).fetchone()["total"]
    )
    conn.close()
    assert_true(active == total, f"Se invalidaron sesiones simultáneas: activas={active}, esperadas={total}")
    METRICS["parallel_sessions"] = {
        "requested": total,
        "active": active,
        "unique_tokens": len({item["token"] for item in results}),
        "max_seconds": round(max(item["elapsed"] for item in results), 4),
        "mean_seconds": round(sum(item["elapsed"] for item in results) / len(results), 4),
        "max_db_retries": max(int(item["meta"].get("db_retries", 0)) for item in results),
    }


def hold_write_lock(database: Path, seconds: float, ready: threading.Event) -> None:
    conn = sqlite3.connect(str(database), timeout=0.1, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout=100")
        conn.execute("BEGIN IMMEDIATE")
        ready.set()
        time.sleep(seconds)
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def test_transient_lock_retry(database: Path, user_row) -> None:
    from modules.seguridad.services import create_login_session_atomic

    ready = threading.Event()
    holder = threading.Thread(
        target=hold_write_lock,
        args=(database, 0.35, ready),
        daemon=True,
    )
    holder.start()
    assert_true(ready.wait(2), "No se estableció el bloqueo transitorio")

    started = time.monotonic()
    _, _, meta = create_login_session_atomic(
        str(database),
        user_row,
        identifiers=("admin.concurrente",),
        request_id="transient-lock",
        ip="10.10.10.10",
        user_agent="transient-device",
    )
    elapsed = time.monotonic() - started
    holder.join(timeout=2)

    assert_true(elapsed < 2.0, f"El reintento transitorio superó 2 s: {elapsed:.3f}")
    assert_true(int(meta.get("db_retries", 0)) >= 1, "No se registró reintento ante SQLITE_BUSY")
    METRICS["transient_lock"] = {
        "hold_seconds": 0.35,
        "login_seconds": round(elapsed, 4),
        "db_retries": int(meta.get("db_retries", 0)),
        "result": "success",
    }


def test_persistent_lock_has_no_false_rate_limit(database: Path, config: dict) -> None:
    from modules.seguridad.services import connect, is_sqlite_busy_error, record_login_failure_atomic

    config.update(
        {
            "LOGIN_DB_RETRY_ATTEMPTS": 3,
            "LOGIN_DB_BUSY_TIMEOUT_MS": 100,
            "LOGIN_DB_RETRY_BASE_MS": 35,
            "LOGIN_DB_RETRY_BUDGET_MS": 500,
        }
    )
    ready = threading.Event()
    holder = threading.Thread(
        target=hold_write_lock,
        args=(database, 1.1, ready),
        daemon=True,
    )
    holder.start()
    assert_true(ready.wait(2), "No se estableció el bloqueo persistente")

    started = time.monotonic()
    raised = None
    try:
        record_login_failure_atomic(
            str(database),
            "usuario.inexistente",
            maximum=5,
            window_seconds=900,
            lock_seconds=900,
            request_id="persistent-lock",
            ip="192.0.2.50",
            user_agent="blocked-device",
        )
    except sqlite3.OperationalError as exc:
        raised = exc
    elapsed = time.monotonic() - started
    holder.join(timeout=2)

    assert_true(raised is not None and is_sqlite_busy_error(raised), "No se propagó SQLITE_BUSY correctamente")
    assert_true(elapsed < 1.5, f"El bloqueo persistente dejó el login colgado: {elapsed:.3f} s")

    conn = connect(str(database))
    attempts = int(conn.execute("SELECT COUNT(*) AS total FROM auth_intentos").fetchone()["total"])
    conn.close()
    assert_true(attempts == 0, "La contención creó un bloqueo de credenciales falso")
    METRICS["persistent_lock"] = {
        "hold_seconds": 1.1,
        "response_seconds": round(elapsed, 4),
        "result": "sqlite_busy_bounded",
        "false_rate_limit_rows": attempts,
    }

    config.update(
        {
            "LOGIN_DB_RETRY_ATTEMPTS": 6,
            "LOGIN_DB_BUSY_TIMEOUT_MS": 100,
            "LOGIN_DB_RETRY_BASE_MS": 35,
            "LOGIN_DB_RETRY_BUDGET_MS": 1500,
        }
    )


def test_route_contract(database: Path, password: str, config: dict) -> None:
    from modules.seguridad.routes import register_seguridad
    from modules.seguridad.services import connect

    app = helpers.FakeApp(config)
    register_seguridad(app, str(database))
    login = app.routes[("/api/auth/login", "POST")]

    tokens = []
    for device in ("browser-a", "browser-b"):
        helpers.set_request(
            "POST",
            {"username": "admin.concurrente", "password": password},
            path="/api/auth/login",
        )
        helpers.request.headers = {
            "User-Agent": device,
            "X-Client-Request-ID": f"route-{device}",
        }
        started = time.monotonic()
        response = login()
        elapsed = time.monotonic() - started
        body, status = helpers.unwrap(response)
        assert_true(status == 200, f"Login por ruta falló para {device}: {status} {body}")
        assert_true(elapsed < 2.0, f"Login por ruta superó 2 s para {device}: {elapsed:.3f}")
        tokens.append(body["token"])
        headers = getattr(response, "headers", {}) if not isinstance(response, tuple) else response[0].headers
        assert_true("X-Login-Duration-Ms" in headers, "Falta telemetría de duración de login")
        assert_true("X-Login-DB-Retries" in headers, "Falta telemetría de reintentos de login")

    assert_true(tokens[0] != tokens[1], "Dos dispositivos recibieron el mismo token")
    conn = connect(str(database))
    count = int(
        conn.execute(
            "SELECT COUNT(*) AS total FROM sesiones_usuario s JOIN usuarios_app u ON u.id=s.usuario_id "
            "WHERE u.username='admin.concurrente' AND s.activa=1"
        ).fetchone()["total"]
    )
    conn.close()
    assert_true(count >= 2, "El segundo dispositivo invalidó la primera sesión")
    METRICS["route_login"] = {
        "devices": 2,
        "distinct_tokens": len(set(tokens)),
        "active_sessions_after": count,
        "result": "success",
    }


def test_static_contract() -> None:
    frontend = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8", errors="strict")
    for needle in (
        "let loginEnCurso = false",
        "new AbortController()",
        "LOGIN_DATABASE_BUSY",
        "Reintentando automáticamente",
        "finally",
    ):
        assert_true(needle in frontend, f"Frontend de login no contiene {needle!r}")

    routes = (ROOT / "backend/modules/seguridad/routes.py").read_text(encoding="utf-8", errors="strict")
    assert_true("create_login_session_atomic" in routes, "La ruta no usa sesión atómica")
    assert_true("load_login_state" in routes, "La ruta no combina la lectura inicial")
    assert_true("trusted_internal=True" in routes, "El login no usa lectura interna explícita de suscripción")
    assert_true("g.current_user = user_payload" not in routes, "El login altera el contexto autenticado antes de terminar")

    billing = (ROOT / "backend/modules/facturacion_suscripcion/services.py").read_text(encoding="utf-8", errors="strict")
    middleware_start = billing.index("def _billing_before_request")
    middleware_end = billing.index("@app.after_request", middleware_start)
    assert_true("service.init()" not in billing[middleware_start:middleware_end], "Facturación inicializa/escribe en cada request")
    assert_true("get_subscription_snapshot" in billing[middleware_start:middleware_end], "Middleware no usa snapshot de solo lectura")

    compatibility = (ROOT / "backend/modules/sqlalchemy_compat.py").read_text(encoding="utf-8", errors="strict")
    assert_true("journal_mode" not in compatibility.lower(), "CoreConnection renegocia WAL en cada conexión")

    services = (ROOT / "backend/modules/seguridad/services.py").read_text(encoding="utf-8", errors="strict")
    assert_true("WHERE u.username=? OR u.email=?" in services, "Login no aprovecha índices exactos existentes")
    assert_true("BEGIN IMMEDIATE" in services, "Login no controla explícitamente su transacción de escritura")


def main() -> None:
    config = configure()
    with tempfile.TemporaryDirectory(prefix="pi_auth_v251_") as raw:
        database = Path(raw) / "database.sqlite3"
        user_row, password = create_fixture(database)
        test_parallel_sessions(database, user_row)
        test_transient_lock_retry(database, user_row)
        test_persistent_lock_has_no_false_rate_limit(database, config)
        test_route_contract(database, password, config)
    test_static_contract()
    METRICS["static_contract"] = {"result": "success"}
    output = os.environ.get("AUTH_TEST_JSON", "").strip()
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "version": "2.5.4-supervision-familias-redes",
            "generated_at": "2026-08-05",
            "status": "PASS",
            "metrics": METRICS,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS test_auth_concurrency_v2_5_1")


if __name__ == "__main__":
    main()
