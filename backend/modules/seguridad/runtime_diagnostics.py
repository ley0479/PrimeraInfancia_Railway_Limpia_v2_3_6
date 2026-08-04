"""Diagnóstico de instancia y registro robusto de errores de ejecución.

Este módulo no registra contraseñas, tokens, cuerpos JSON ni cookies. Su
objetivo es hacer trazables los fallos que ocurren antes de iniciar sesión y
permitir que los scripts de Windows confirmen que el puerto 5000 pertenece a la
misma copia del proyecto que el usuario está intentando abrir.
"""
from __future__ import annotations

import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import traceback
from typing import Any, Mapping


_SAFE_INSTANCE_RE = re.compile(r"[^a-zA-Z0-9_.-]+")
_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-auth-token",
    "proxy-authorization",
}
_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)\b(password|passwd|contrase(?:ña|na)|token|secret|authorization|cookie)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/]+=*")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")


def _redact_text(value: Any) -> str:
    text = str(value or "")
    text = _SENSITIVE_TEXT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _JWT_RE.sub("[JWT_REDACTED]", text)
    return text


def _resolved(value: Any, default: Path) -> Path:
    try:
        raw = str(value or "").strip()
        return (Path(raw).expanduser() if raw else default).resolve()
    except Exception:
        return default.resolve()


def project_instance_id(config: Mapping[str, Any]) -> str:
    """Identificador estable de una copia local, sin exponer su ruta.

    Los scripts Windows suministran ``PROJECT_INSTANCE_ID``. En Railway o en
    ejecuciones manuales se calcula un hash corto de la raíz y la base activa.
    """
    explicit = str(config.get("PROJECT_INSTANCE_ID") or os.getenv("PROJECT_INSTANCE_ID") or "").strip()
    if explicit:
        clean = _SAFE_INSTANCE_RE.sub("-", explicit).strip("-._")
        if clean:
            return clean[:64]

    project_dir = _resolved(config.get("PROJECT_DIR"), Path(__file__).resolve().parents[3])
    database_path = _resolved(config.get("DATABASE_PATH"), project_dir / "data" / "database.sqlite3")
    seed = f"{project_dir.as_posix().lower()}|{database_path.as_posix().lower()}"
    return hashlib.sha256(seed.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def _relative_log_reference(path: Path, config: Mapping[str, Any]) -> str:
    project_dir = _resolved(config.get("PROJECT_DIR"), Path(__file__).resolve().parents[3])
    data_dir = _resolved(config.get("DATA_DIR"), project_dir / "data")
    try:
        relative = path.resolve().relative_to(project_dir)
        return relative.as_posix()
    except Exception:
        pass
    try:
        relative = path.resolve().relative_to(data_dir)
        return f"data/{relative.as_posix()}"
    except Exception:
        return f"logs/{path.name}"


def _request_metadata(request_obj: Any, g_obj: Any = None) -> dict[str, Any]:
    if request_obj is None:
        return {}

    headers: dict[str, str] = {}
    try:
        for name in (
            "Host",
            "Origin",
            "User-Agent",
            "X-Forwarded-Proto",
            "X-Forwarded-Host",
            "X-Forwarded-For",
            "CF-Ray",
            "CF-Connecting-IP",
            "X-Client-Request-ID",
        ):
            if name.lower() in _SENSITIVE_HEADERS:
                continue
            value = request_obj.headers.get(name)
            if value:
                value = str(value)
                # Evita logs gigantes y no conserva cadenas de proxy completas.
                if name.lower() in {"x-forwarded-for", "cf-connecting-ip"}:
                    value = hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16]
                headers[name] = value[:500]
    except Exception:
        headers = {}

    metadata: dict[str, Any] = {
        "method": str(getattr(request_obj, "method", "") or ""),
        "path": str(getattr(request_obj, "path", "") or "")[:1000],
        "scheme": str(getattr(request_obj, "scheme", "") or ""),
        "headers": headers,
    }
    try:
        context = getattr(g_obj, "error_context", None) if g_obj is not None else None
        if isinstance(context, Mapping):
            metadata["context"] = {
                str(key)[:100]: str(value)[:1000]
                for key, value in context.items()
                if str(key).lower() not in {"password", "token", "authorization", "cookie"}
            }
    except Exception:
        pass
    return metadata


def configure_application_logging(app: Any) -> dict[str, Any]:
    """Añade un archivo rotativo global bajo ``DATA_DIR/logs``.

    La función es idempotente y nunca impide que Flask inicie. El resultado se
    guarda en ``app.extensions`` para que el healthcheck informe si el destino
    es escribible.
    """
    status: dict[str, Any] = {"configured": False, "writable": False, "reference": ""}
    try:
        if app.extensions.get("primera_infancia_file_logging"):
            return dict(app.extensions["primera_infancia_file_logging"])

        log_dir = _resolved(app.config.get("LOG_FOLDER"), Path(app.config.get("DATA_DIR") or ".") / "logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "application.log"
        probe = log_dir / f".write_probe_{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)

        handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            delay=True,
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            "%Y-%m-%dT%H:%M:%S",
        ))
        level_name = str(app.config.get("LOG_LEVEL") or "INFO").upper()
        handler.setLevel(getattr(logging, level_name, logging.INFO))
        app.logger.addHandler(handler)
        app.logger.setLevel(min(app.logger.level or logging.INFO, handler.level))

        status.update({
            "configured": True,
            "writable": True,
            "reference": _relative_log_reference(log_file, app.config),
        })
    except Exception as exc:  # pragma: no cover - depende del sistema de archivos
        status["error"] = f"{type(exc).__name__}: {exc}"
        try:
            print(f"[LOGGING] No se pudo configurar el archivo de aplicación: {exc}", file=sys.stderr, flush=True)
        except Exception:
            pass

    try:
        app.extensions["primera_infancia_file_logging"] = dict(status)
    except Exception:
        pass
    return status


def write_exception_report(
    exc: BaseException,
    trace_id: str,
    config: Mapping[str, Any],
    *,
    request_obj: Any = None,
    g_obj: Any = None,
) -> dict[str, Any]:
    """Escribe un reporte no vacío de forma atómica y devuelve su referencia.

    Si el destino principal falla, el traceback se envía a ``stderr`` y se
    intenta un archivo alterno en ``DATA_DIR/logs_fallback``.
    """
    instance = project_instance_id(config)
    project_dir = _resolved(config.get("PROJECT_DIR"), Path(__file__).resolve().parents[3])
    data_dir = _resolved(config.get("DATA_DIR"), project_dir / "data")
    primary_dir = _resolved(config.get("LOG_FOLDER"), data_dir / "logs")
    fallback_dir = data_dir / "logs_fallback"
    filename = f"error_api_{trace_id}.log"

    stack = _redact_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    if not stack.strip():
        stack = _redact_text(f"{type(exc).__name__}: {exc}\n")
    payload = {
        "timestamp": __import__("datetime").datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "trace_id": trace_id,
        "instance_id": instance,
        "app_version": str(config.get("APP_VERSION") or "unknown"),
        "environment": str(config.get("APP_ENV") or "unknown"),
        "server_mode": str(config.get("SERVER_MODE") or "unknown"),
        "exception_type": type(exc).__name__,
        "exception_message": _redact_text(exc)[:4000],
        "request": _request_metadata(request_obj, g_obj),
    }
    content = (
        "PRIMERA INFANCIA - REPORTE DE ERROR API\n"
        "========================================\n"
        + json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        + "\n\nTRACEBACK\n---------\n"
        + stack
    )

    errors: list[str] = []
    for directory in (primary_dir, fallback_dir):
        temp_path: Path | None = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            final_path = directory / filename
            temp_path = directory / f".{filename}.{os.getpid()}.tmp"
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if temp_path.stat().st_size <= 0:
                raise OSError("El archivo temporal quedó vacío.")
            os.replace(temp_path, final_path)
            return {
                "written": True,
                "reference": _relative_log_reference(final_path, config),
                "size": final_path.stat().st_size,
                "instance_id": instance,
            }
        except Exception as write_exc:  # pragma: no cover - depende del sistema de archivos
            errors.append(f"{directory}: {type(write_exc).__name__}: {write_exc}")
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    try:
        print(content, file=sys.stderr, flush=True)
    except Exception:
        pass
    return {
        "written": False,
        "reference": "",
        "size": 0,
        "instance_id": instance,
        "errors": errors,
    }


def logging_health(config: Mapping[str, Any]) -> dict[str, Any]:
    """Comprueba que la carpeta real de logs es escribible, sin crear datos de usuario."""
    project_dir = _resolved(config.get("PROJECT_DIR"), Path(__file__).resolve().parents[3])
    data_dir = _resolved(config.get("DATA_DIR"), project_dir / "data")
    log_dir = _resolved(config.get("LOG_FOLDER"), data_dir / "logs")
    result = {
        "writable": False,
        "reference": _relative_log_reference(log_dir / "application.log", config),
    }
    probe = log_dir / f".health_probe_{os.getpid()}"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        result["writable"] = probe.stat().st_size > 0
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            probe.unlink(missing_ok=True)
        except Exception:
            pass
    return result
