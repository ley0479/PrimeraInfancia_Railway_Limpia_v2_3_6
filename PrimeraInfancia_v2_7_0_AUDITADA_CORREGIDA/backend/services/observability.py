"""Observabilidad liviana y segura para Primera Infancia.

No registra cuerpos, cookies, tokens, contraseñas ni datos de participantes.
Expone métricas agregadas y correlación por solicitud para diagnóstico local,
Railway y túnel.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import Counter, deque
from datetime import datetime, timezone
from typing import Any

from flask import g, request


class RuntimeMetrics:
    def __init__(self, max_recent: int = 250) -> None:
        self._lock = threading.RLock()
        self.started_at = time.time()
        self.requests_total = 0
        self.errors_total = 0
        self.status_counts: Counter[str] = Counter()
        self.method_counts: Counter[str] = Counter()
        self.route_counts: Counter[str] = Counter()
        self.duration_sum_ms = 0.0
        self.duration_max_ms = 0.0
        self.recent = deque(maxlen=max_recent)

    def observe(self, *, method: str, route: str, status: int, duration_ms: float, request_id: str) -> None:
        route = route[:180]
        with self._lock:
            self.requests_total += 1
            if status >= 500:
                self.errors_total += 1
            self.status_counts[str(status)] += 1
            self.method_counts[method] += 1
            self.route_counts[route] += 1
            self.duration_sum_ms += duration_ms
            self.duration_max_ms = max(self.duration_max_ms, duration_ms)
            self.recent.append({
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "request_id": request_id,
                "method": method,
                "route": route,
                "status": status,
                "duration_ms": round(duration_ms, 2),
            })

    def snapshot(self, database_health: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            average = self.duration_sum_ms / self.requests_total if self.requests_total else 0.0
            return {
                "started_at": datetime.fromtimestamp(self.started_at, timezone.utc).isoformat(timespec="seconds"),
                "uptime_seconds": round(time.time() - self.started_at, 1),
                "requests_total": self.requests_total,
                "errors_total": self.errors_total,
                "error_rate": round(self.errors_total / self.requests_total, 6) if self.requests_total else 0.0,
                "duration_average_ms": round(average, 2),
                "duration_max_ms": round(self.duration_max_ms, 2),
                "status_counts": dict(self.status_counts),
                "method_counts": dict(self.method_counts),
                "top_routes": dict(self.route_counts.most_common(25)),
                "database": database_health or {},
                "recent": list(self.recent)[-50:],
            }

    def prometheus(self, database_health: dict[str, Any] | None = None) -> str:
        snap = self.snapshot(database_health)
        lines = [
            "# HELP primera_infancia_uptime_seconds Tiempo activo del proceso.",
            "# TYPE primera_infancia_uptime_seconds gauge",
            f"primera_infancia_uptime_seconds {snap['uptime_seconds']}",
            "# HELP primera_infancia_requests_total Solicitudes HTTP observadas.",
            "# TYPE primera_infancia_requests_total counter",
            f"primera_infancia_requests_total {snap['requests_total']}",
            "# HELP primera_infancia_errors_total Respuestas HTTP 5xx observadas.",
            "# TYPE primera_infancia_errors_total counter",
            f"primera_infancia_errors_total {snap['errors_total']}",
            "# HELP primera_infancia_request_duration_average_ms Duración media HTTP en milisegundos.",
            "# TYPE primera_infancia_request_duration_average_ms gauge",
            f"primera_infancia_request_duration_average_ms {snap['duration_average_ms']}",
            "# HELP primera_infancia_database_up Estado de conectividad de base de datos.",
            "# TYPE primera_infancia_database_up gauge",
            f"primera_infancia_database_up {1 if (snap.get('database') or {}).get('ok') else 0}",
        ]
        for status, count in sorted(snap["status_counts"].items()):
            lines.append(f'primera_infancia_http_status_total{{status="{status}"}} {count}')
        return "\n".join(lines) + "\n"


runtime_metrics = RuntimeMetrics()


def _safe_route() -> str:
    rule = getattr(request, "url_rule", None)
    return str(rule.rule if rule is not None else request.path)[:180]


def configure_observability(app, database_manager) -> RuntimeMetrics:
    """Instala correlación y métricas; es idempotente por aplicación."""
    if app.extensions.get("primera_infancia_observability"):
        return runtime_metrics

    logger = logging.getLogger("primera_infancia.http")

    @app.before_request
    def _observe_start():
        incoming = str(request.headers.get("X-Request-ID") or "").strip()
        g.request_id = incoming[:96] if incoming else uuid.uuid4().hex
        g.request_started_perf = time.perf_counter()

    @app.after_request
    def _observe_finish(response):
        request_id = str(getattr(g, "request_id", "") or uuid.uuid4().hex)
        started = float(getattr(g, "request_started_perf", time.perf_counter()))
        duration_ms = (time.perf_counter() - started) * 1000
        route = _safe_route()
        runtime_metrics.observe(
            method=request.method,
            route=route,
            status=int(response.status_code),
            duration_ms=duration_ms,
            request_id=request_id,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.2f}"
        if response.status_code >= 500 or duration_ms >= float(app.config.get("OBSERVABILITY_SLOW_REQUEST_MS", 2000)):
            logger.warning(json.dumps({
                "event": "runtime_alert",
                "request_id": request_id,
                "route": route,
                "status": int(response.status_code),
                "duration_ms": round(duration_ms, 2),
            }, ensure_ascii=False))
        if os.getenv("STRUCTURED_HTTP_LOGS", "true").lower() in {"1", "true", "yes", "on"}:
            logger.info(json.dumps({
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status": int(response.status_code),
                "duration_ms": round(duration_ms, 2),
            }, ensure_ascii=False))
        return response

    app.extensions["primera_infancia_observability"] = runtime_metrics
    app.extensions["primera_infancia_database_manager"] = database_manager
    return runtime_metrics
