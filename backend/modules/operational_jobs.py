"""Gestor liviano de trabajos operativos en segundo plano.

Alpha24: evita timeouts 524 en túnel Cloudflare/ngrok moviendo tareas largas
(carga de base Cuéntame, generación de formatos y cronogramas) a jobs
consultables por /api/jobs/<job_id>.
"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Callable

_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_LOG_DIR: str | None = None
_MAX_LOGS = 200


def configure(log_dir: str | None = None) -> None:
    """Configura carpeta de logs de jobs. No falla si no puede crearla."""
    global _LOG_DIR
    _LOG_DIR = log_dir
    if _LOG_DIR:
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
        except Exception:
            _LOG_DIR = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _public_job(job: dict[str, Any], include_result: bool = True) -> dict[str, Any]:
    data = {k: v for k, v in job.items() if k not in {"thread"}}
    if not include_result and "resultado" in data:
        data["resultado"] = None
    return data


def _write_job_log(job: dict[str, Any], include_result: bool = False) -> None:
    if not _LOG_DIR:
        return
    try:
        path = os.path.join(_LOG_DIR, f"job_{job['id']}.json")
        data = _public_job(job, include_result=include_result)
        # El resultado puede contener miles de beneficiarios; para el archivo se evita
        # guardar un JSON pesado, pero la respuesta en memoria sí conserva el resultado.
        if not include_result and data.get("resultado") is None:
            data.pop("resultado", None)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


def _append_log(job: dict[str, Any], message: str) -> None:
    logs = job.setdefault("logs", [])
    logs.append({"fecha": _now(), "mensaje": str(message)[:1000]})
    if len(logs) > _MAX_LOGS:
        del logs[:-_MAX_LOGS]


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        return _public_job(job) if job else None


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        jobs = sorted(_JOBS.values(), key=lambda j: j.get("fecha_creacion", ""), reverse=True)
        return [_public_job(j, include_result=False) for j in jobs[:limit]]


def _cleanup_old_jobs(max_age_seconds: int = 3600 * 8, keep: int = 100) -> None:
    now_ts = time.time()
    with _LOCK:
        finished = [
            (job_id, job)
            for job_id, job in _JOBS.items()
            if job.get("estado") in {"completado", "error", "cancelado"}
        ]
        finished.sort(key=lambda item: item[1].get("fecha_actualizacion", ""), reverse=True)
        protected = {job_id for job_id, _ in finished[:keep]}
        for job_id, job in finished[keep:]:
            if job_id not in protected:
                _JOBS.pop(job_id, None)
                continue
            started = float(job.get("_ts", now_ts))
            if now_ts - started > max_age_seconds:
                _JOBS.pop(job_id, None)


def start_job(
    tipo: str,
    target: Callable[[Callable[..., None]], Any],
    metadata: dict[str, Any] | None = None,
    descripcion: str | None = None,
) -> dict[str, Any]:
    """Inicia un trabajo en segundo plano.

    target recibe update(**kwargs), por ejemplo:
        update(progreso=40, etapa="Generando formatos")
    El resultado retornado por target queda en job["resultado"].
    """
    _cleanup_old_jobs()
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "tipo": tipo,
        "descripcion": descripcion or tipo,
        "estado": "pendiente",
        "progreso": 0,
        "etapa": "En cola",
        "resultado": None,
        "error": None,
        "traceback": None,
        "metadata": metadata or {},
        "logs": [],
        "fecha_creacion": _now(),
        "fecha_inicio": None,
        "fecha_fin": None,
        "fecha_actualizacion": _now(),
        "_ts": time.time(),
    }

    def update(**kwargs: Any) -> None:
        with _LOCK:
            current = _JOBS.get(job_id)
            if not current:
                return
            for key, value in kwargs.items():
                if key in {"log", "mensaje"}:
                    _append_log(current, str(value))
                elif key == "logs" and isinstance(value, (list, tuple)):
                    for item in value:
                        _append_log(current, str(item))
                else:
                    current[key] = value
            current["fecha_actualizacion"] = _now()
            _write_job_log(current, include_result=False)

    def runner() -> None:
        with _LOCK:
            job["estado"] = "procesando"
            job["fecha_inicio"] = _now()
            job["etapa"] = "Iniciando"
            job["fecha_actualizacion"] = _now()
            _write_job_log(job, include_result=False)
        try:
            result = target(update)
            with _LOCK:
                job["estado"] = "completado"
                job["progreso"] = 100
                job["etapa"] = "Completado"
                job["resultado"] = result
                job["fecha_fin"] = _now()
                job["fecha_actualizacion"] = _now()
                _write_job_log(job, include_result=False)
        except Exception as exc:  # pragma: no cover - cubierto por integración manual
            tb = traceback.format_exc()
            with _LOCK:
                job["estado"] = "error"
                job["error"] = str(exc)
                job["traceback"] = tb[-6000:]
                job["etapa"] = "Error"
                job["fecha_fin"] = _now()
                job["fecha_actualizacion"] = _now()
                _append_log(job, str(exc))
                _write_job_log(job, include_result=False)

    thread = threading.Thread(target=runner, name=f"PrimeraInfanciaJob-{job_id}", daemon=True)
    job["thread"] = thread
    with _LOCK:
        _JOBS[job_id] = job
    thread.start()
    return _public_job(job, include_result=False)
