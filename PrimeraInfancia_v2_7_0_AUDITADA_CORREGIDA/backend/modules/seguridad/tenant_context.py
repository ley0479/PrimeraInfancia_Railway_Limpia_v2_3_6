"""Contexto multi-fundación y rutas de almacenamiento aisladas.

Este módulo no decide permisos de negocio. Su responsabilidad es mantener un
identificador de fundación confiable durante peticiones HTTP y trabajos en
segundo plano, y resolver carpetas físicas separadas por fundación.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterator

try:  # Flask no es requisito para las pruebas unitarias puras.
    from flask import current_app, g, has_request_context, request
except Exception:  # pragma: no cover - entorno sin Flask
    current_app = g = request = None

    def has_request_context() -> bool:
        return False


@dataclass(frozen=True)
class TenantContext:
    tenant_id: int | None
    role: str = "SYSTEM"
    username: str | None = None
    allow_global: bool = False
    source: str = "background"


_CONTEXT: ContextVar[TenantContext | None] = ContextVar("primera_infancia_tenant", default=None)


def _positive_int(value) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def current_tenant_context() -> TenantContext:
    """Obtiene el tenant autenticado; nunca confía en datos del formulario."""
    if has_request_context():
        user = getattr(g, "current_user", None) or {}
        tenant_id = _positive_int(getattr(g, "current_fundacion_id", None) or user.get("fundacion_id"))
        return TenantContext(
            tenant_id=tenant_id,
            role=str(user.get("rol") or "ANONYMOUS").upper(),
            username=user.get("username"),
            allow_global=bool(getattr(g, "allow_global_tenant_access", False)),
            source=f"http:{getattr(request, 'path', '')}",
        )
    return _CONTEXT.get() or TenantContext(None)


def current_tenant_id(default: int | None = None) -> int | None:
    return current_tenant_context().tenant_id or default


def is_superadmin() -> bool:
    return current_tenant_context().role == "SUPERADMIN"


def multi_tenant_enabled() -> bool:
    if has_request_context():
        return not bool(current_app.config.get("SINGLE_TENANT_MODE", True))
    raw = str(os.environ.get("SINGLE_TENANT_MODE", "true")).strip().lower()
    return raw not in {"1", "true", "yes", "si", "sí", "on"}


def strict_tenant_mode() -> bool:
    if has_request_context():
        return bool(current_app.config.get("MULTI_TENANT_STRICT", True)) and multi_tenant_enabled()
    raw = str(os.environ.get("MULTI_TENANT_STRICT", "true")).strip().lower()
    return raw in {"1", "true", "yes", "si", "sí", "on"} and multi_tenant_enabled()


@contextmanager
def tenant_context(
    tenant_id: int | None,
    role: str = "SYSTEM",
    username: str | None = None,
    allow_global: bool = False,
    source: str = "background",
) -> Iterator[TenantContext]:
    """Propaga el tenant a hilos/tareas que no conservan el contexto Flask."""
    context = TenantContext(_positive_int(tenant_id), str(role or "SYSTEM").upper(), username, allow_global, source)
    token = _CONTEXT.set(context)
    try:
        yield context
    finally:
        _CONTEXT.reset(token)


def capture_tenant_context() -> TenantContext:
    return current_tenant_context()


_SHARED_CATEGORIES = {"templates_originales", "official_templates", "seeds"}


def tenant_storage_root(data_dir: str | os.PathLike[str] | None = None, tenant_id: int | None = None) -> Path:
    """Raíz persistente de una fundación: ``DATA_DIR/tenants/<id>``."""
    if data_dir is None:
        if has_request_context():
            data_dir = current_app.config.get("DATA_DIR")
        else:
            data_dir = os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[3] / "data"
    tid = _positive_int(tenant_id) or current_tenant_id()
    if not tid:
        return Path(os.fspath(data_dir)).resolve()
    return Path(os.fspath(data_dir)).resolve() / "tenants" / str(tid)


def resolve_tenant_path(
    base_path: str | os.PathLike[str],
    *parts: str,
    tenant_id: int | None = None,
    create: bool = False,
    shared: bool = False,
) -> Path:
    """Convierte una carpeta global en una carpeta equivalente por fundación.

    ``/data/uploads`` se convierte en ``/data/tenants/2/uploads``. Fuera de
    contexto autenticado o en modo single-tenant conserva la ruta original.
    """
    base = Path(os.fspath(base_path)).resolve()
    tid = _positive_int(tenant_id) or current_tenant_id()
    if shared or not strict_tenant_mode() or not tid:
        result = base.joinpath(*parts)
    else:
        data_dir = current_app.config.get("DATA_DIR") if has_request_context() else None
        # En trabajos en segundo plano ``base`` ya contiene la ruta absoluta
        # configurada por Flask. No se debe volver a resolver DATA_DIR desde el
        # entorno: un valor relativo (por ejemplo ``data``) dependería del cwd
        # del proceso y desviaría los archivos a ``backend/data``.
        data_root = Path(os.fspath(data_dir or base.parent)).resolve()
        category = base.name
        if category in _SHARED_CATEGORIES:
            result = base.joinpath(*parts)
        else:
            result = data_root / "tenants" / str(tid) / category
            result = result.joinpath(*parts)
    if create:
        result.mkdir(parents=True, exist_ok=True)
    return result


class TenantPath(os.PathLike[str]):
    """PathLike que se resuelve en el momento de uso, no al iniciar Flask."""

    def __init__(self, base_path: str | os.PathLike[str], *parts: str, shared: bool = False):
        self._base_path = os.fspath(base_path)
        self._parts = tuple(str(p) for p in parts if str(p))
        self._shared = bool(shared)

    def child(self, *parts: str) -> "TenantPath":
        return TenantPath(self._base_path, *self._parts, *parts, shared=self._shared)

    def resolve(self, create: bool = False) -> Path:
        return resolve_tenant_path(self._base_path, *self._parts, create=create, shared=self._shared)

    def __fspath__(self) -> str:
        return str(self.resolve(create=True))

    def __str__(self) -> str:
        return os.fspath(self)

    def __repr__(self) -> str:
        return f"TenantPath(base={self._base_path!r}, parts={self._parts!r}, shared={self._shared!r})"


def tenant_path(base_path: str | os.PathLike[str], *parts: str, shared: bool = False) -> TenantPath:
    if isinstance(base_path, TenantPath):
        result = base_path.child(*parts)
        if shared and not result._shared:
            return TenantPath(result._base_path, *result._parts, shared=True)
        return result
    return TenantPath(base_path, *parts, shared=shared)


def ensure_tenant_directories(data_dir: str | os.PathLike[str], tenant_id: int) -> dict[str, str]:
    root = tenant_storage_root(data_dir, tenant_id)
    categories = (
        "uploads", "archivos_actualizados", "documentos_institucionales",
        "cuentas_cobro_plantillas", "backups", "logs", "storage",
        "institutional",
    )
    created: dict[str, str] = {}
    for category in categories:
        path = root / category
        path.mkdir(parents=True, exist_ok=True)
        created[category] = str(path)
    return created
