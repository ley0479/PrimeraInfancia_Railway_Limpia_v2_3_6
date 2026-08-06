"""Detección controlada de actualizaciones de la Biblioteca Oficial ICBF.

Las comprobaciones remotas están deshabilitadas por defecto. Solo se permiten
fuentes HTTPS explícitamente autorizadas y dominios declarados por el
administrador. No se almacenan credenciales en esta configuración.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
from typing import Any
from urllib.parse import urlparse

import requests


class LibraryUpdateError(RuntimeError):
    pass


def _allowed_domains(source: dict[str, Any]) -> set[str]:
    configured = str(source.get("dominio_permitido") or "").strip().lower()
    environment = str(os.environ.get("BIBLIOTECA_ALLOWED_DOMAINS") or "icbf.gov.co,www.icbf.gov.co").strip().lower()
    values = {item.strip().lstrip(".") for item in (configured + "," + environment).split(",") if item.strip()}
    return values


def _host_allowed(host: str, domains: set[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _reject_private_resolution(host: str) -> None:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise LibraryUpdateError(f"No se pudo resolver el dominio autorizado: {exc}") from exc
    if not addresses:
        raise LibraryUpdateError("El dominio no resolvió direcciones públicas.")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            raise LibraryUpdateError("La fuente resuelve a una red privada o no permitida.")


def validate_remote_source(source: dict[str, Any]) -> str:
    if str(os.environ.get("BIBLIOTECA_REMOTE_CHECKS_ENABLED") or "").lower() not in {"1", "true", "si", "sí"}:
        raise LibraryUpdateError("La verificación remota está deshabilitada. Activa BIBLIOTECA_REMOTE_CHECKS_ENABLED solo para una fuente oficial autorizada.")
    if not int(source.get("autorizada") or 0) or not int(source.get("habilitada") or 0):
        raise LibraryUpdateError("La fuente no está autorizada y habilitada.")
    mechanism = str(source.get("mecanismo") or "MANUAL").upper()
    if mechanism != "CATALOGO_JSON":
        raise LibraryUpdateError("La comprobación automática solo admite el contrato CATALOGO_JSON. Otras fuentes requieren importación manual.")
    raw_url = str(source.get("url_base") or "").strip()
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise LibraryUpdateError("La fuente debe ser una URL HTTPS sin credenciales embebidas.")
    domains = _allowed_domains(source)
    if not _host_allowed(parsed.hostname, domains):
        raise LibraryUpdateError("El dominio de la fuente no está en la lista permitida.")
    _reject_private_resolution(parsed.hostname)
    return raw_url


def _dig(payload: Any, path: str | None) -> Any:
    if not path:
        return payload
    current = payload
    for part in str(path).split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def fetch_authorized_catalog(source: dict[str, Any]) -> dict[str, Any]:
    url = validate_remote_source(source)
    config = source.get("configuracion") or source.get("configuracion_json") or {}
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except Exception:
            config = {}
    timeout = max(2, min(15, int(config.get("timeout_seconds") or 6)))
    headers = {"Accept": "application/json", "User-Agent": "PrimeraInfancia-Biblioteca/2.5.3"}
    if source.get("ultimo_etag"):
        headers["If-None-Match"] = str(source["ultimo_etag"])
    if source.get("ultima_modificacion"):
        headers["If-Modified-Since"] = str(source["ultima_modificacion"])
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
    except requests.RequestException as exc:
        raise LibraryUpdateError(f"No se pudo consultar la fuente: {exc}") from exc
    if response.status_code == 304:
        return {"not_modified": True, "items": [], "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
    if response.status_code != 200:
        raise LibraryUpdateError(f"La fuente respondió HTTP {response.status_code}.")
    content_type = str(response.headers.get("Content-Type") or "").lower()
    if "json" not in content_type and not response.text.lstrip().startswith(("{", "[")):
        raise LibraryUpdateError("La fuente autorizada no respondió un catálogo JSON.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise LibraryUpdateError("El catálogo remoto contiene JSON inválido.") from exc
    items = _dig(payload, config.get("items_path") or "documents")
    if items is None and isinstance(payload, list):
        items = payload
    if not isinstance(items, list):
        raise LibraryUpdateError("No se encontró una lista de documentos en el catálogo autorizado.")
    if len(items) > 5000:
        raise LibraryUpdateError("El catálogo supera el máximo permitido de 5000 elementos.")
    return {
        "not_modified": False,
        "items": [item for item in items if isinstance(item, dict)],
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
    }
