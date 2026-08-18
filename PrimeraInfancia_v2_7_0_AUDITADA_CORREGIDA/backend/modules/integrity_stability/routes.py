"""API del Motor de Integridad, Supervisión y Estabilidad."""
from __future__ import annotations

import hmac
from flask import Blueprint, current_app, jsonify, request

from database import database
from modules.operational_jobs import start_job
from modules.seguridad.services import require_roles
from services.observability import runtime_metrics

from .service import IntegrityStabilityService

READ_ROLES = ("SUPERADMIN", "GERENTE", "COORDINADOR")
ADMIN_ROLES = ("SUPERADMIN", "GERENTE")


def register_routes(app, project_root: str, data_dir: str, database_path: str | None = None) -> None:
    service = IntegrityStabilityService(project_root, data_dir, database_path)
    bp = Blueprint("integrity_stability", __name__, url_prefix="/api/integrity")

    @bp.get("/health")
    def module_health():
        return jsonify({"status": "ok", "module": "integrity_stability", "version": "2.7.0"})

    @bp.get("/status")
    @require_roles(*READ_ROLES)
    def status():
        return jsonify({
            "gate": service.latest_gate_report(),
            "safe_repair": service.latest_repair_report(),
            "architecture": service.architecture_inventory(),
            "database": database.healthcheck(),
            "runtime": runtime_metrics.snapshot(database.healthcheck()),
            "monitor": service.runtime_monitor_status(),
        })

    @bp.post("/diagnostic")
    @require_roles(*READ_ROLES)
    def diagnostic():
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode") or "MANUAL").upper()
        if mode not in {"MANUAL", "QUICK", "FULL"}:
            return jsonify({"error": "Modo inválido. Usa MANUAL, QUICK o FULL."}), 400
        report = service.central_diagnostic(dict(current_app.config), mode=mode)
        return jsonify(report), 200

    @bp.get("/monitor")
    @require_roles(*READ_ROLES)
    def monitor():
        return jsonify(service.runtime_monitor_status()), 200

    @bp.get("/architecture")
    @require_roles(*READ_ROLES)
    def architecture():
        return jsonify(service.architecture_inventory())

    @bp.post("/run")
    @require_roles(*ADMIN_ROLES)
    def run_gate():
        payload = request.get_json(silent=True) or {}
        include_tests = bool(payload.get("include_tests", True))
        job = start_job(
            "integrity_gate",
            lambda update: service.run_gate(update, include_tests=include_tests),
            metadata={"global_operation": True},
            descripcion="Gate de integridad y regresión",
        )
        return jsonify({"message": "Gate iniciado. No se modifican datos de negocio.", "job": job}), 202

    @bp.post("/safe-repair")
    @require_roles("SUPERADMIN")
    def safe_repair():
        payload = request.get_json(silent=True) or {}
        apply = bool(payload.get("apply", False))
        job = start_job(
            "integrity_safe_repair",
            lambda update: service.safe_repair(update, apply=apply),
            metadata={"global_operation": True, "apply": apply},
            descripcion="Plan o aplicación de reparaciones seguras",
        )
        return jsonify({
            "message": "Reparación segura iniciada." if apply else "Plan de reparación segura iniciado.",
            "job": job,
            "business_rules_modified": False,
        }), 202

    @bp.get("/metrics")
    def metrics():
        configured = str(current_app.config.get("METRICS_TOKEN") or "")
        supplied = str(request.headers.get("X-Metrics-Token") or "")
        # Sin token configurado, solo usuarios autenticados de coordinación pueden entrar.
        if configured:
            if not supplied or not hmac.compare_digest(configured, supplied):
                return jsonify({"error": "No autorizado."}), 401
        else:
            from flask import g
            user = getattr(g, "current_user", None) or {}
            if str(user.get("rol") or "").upper() not in READ_ROLES:
                return jsonify({"error": "No autorizado."}), 401
        return current_app.response_class(runtime_metrics.prometheus(database.healthcheck()), mimetype="text/plain; version=0.0.4")

    app.register_blueprint(bp)

    @app.get("/api/ready")
    def readiness():
        health = database.healthcheck()
        max_latency = float(current_app.config.get("READINESS_MAX_DB_LATENCY_MS", 2000))
        ready = bool(health.get("ok")) and float(health.get("latency_ms") or 999999) <= max_latency
        return jsonify({
            "status": "ready" if ready else "not_ready",
            "database": health,
            "version": current_app.config.get("APP_VERSION"),
        }), 200 if ready else 503
