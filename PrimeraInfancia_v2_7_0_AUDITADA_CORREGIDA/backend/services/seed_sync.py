"""Sincronización segura de semillas hacia el volumen persistente.

Actualiza únicamente archivos que siguen coincidiendo con una versión gestionada
por el sistema. Los archivos personalizados por un usuario se preservan.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_FILENAME = ".primera_infancia_seed_state.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _manifest_hashes(seed_root: Path) -> dict[str, str]:
    manifest = _read_json(seed_root / "seed_manifest.json", {})
    result: dict[str, str] = {}
    for record in manifest.get("plantillas") or manifest.get("files") or []:
        name = str(record.get("archivo") or record.get("name") or "").replace("\\", "/").strip("/")
        digest = str(record.get("sha256") or "").lower().strip()
        if name and len(digest) == 64:
            result[name] = digest
    return result


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise RuntimeError(f"Ruta insegura en semillas: {relative}")
    return relative


def sync_managed_seed_tree(
    source: Path,
    destination: Path,
    *,
    data_dir: Path,
    backups_dir: Path,
    allow_updates: bool = True,
) -> dict[str, Any]:
    if not source.is_dir():
        raise RuntimeError(f"No existe el directorio de semillas: {source}")
    source = source.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)

    state_path = data_dir / STATE_FILENAME
    previous_state = _read_json(state_path, {})
    previous_files = previous_state.get("files") if isinstance(previous_state, dict) else {}
    if not isinstance(previous_files, dict):
        previous_files = {}

    # El manifiesto que ya vive en el volumen permite reconocer semillas de la
    # versión anterior incluso si esta es la primera ejecución con estado v2.
    old_declared_hashes = _manifest_hashes(destination)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = backups_dir / f"seed_sync_{timestamp}"

    report: dict[str, list[str]] = {
        "copied": [],
        "updated": [],
        "unchanged": [],
        "preserved_custom": [],
        "backups": [],
    }
    next_files: dict[str, Any] = {}

    for src in sorted(source.rglob("*")):
        if src.is_symlink():
            raise RuntimeError(f"No se permiten enlaces simbólicos en semillas: {src}")
        relative = _safe_relative(src, source)
        dst = destination / relative
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue

        source_hash = sha256_file(src)
        action = "unchanged"
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            report["copied"].append(relative)
            action = "copied"
        else:
            destination_hash = sha256_file(dst)
            if destination_hash == source_hash:
                report["unchanged"].append(relative)
            else:
                previous_entry = previous_files.get(relative) if isinstance(previous_files, dict) else None
                previous_deployed_hash = ""
                if isinstance(previous_entry, dict):
                    previous_deployed_hash = str(previous_entry.get("deployed_sha256") or "").lower()
                legacy_hash = old_declared_hashes.get(relative, "")
                control_file = relative == "seed_manifest.json"
                is_managed = control_file or destination_hash in {previous_deployed_hash, legacy_hash}
                if allow_updates and is_managed:
                    backup = backup_root / relative
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dst, backup)
                    shutil.copy2(src, dst)
                    report["updated"].append(relative)
                    report["backups"].append(backup.relative_to(backups_dir).as_posix())
                    action = "updated"
                else:
                    report["preserved_custom"].append(relative)
                    action = "preserved_custom"

        deployed_hash = sha256_file(dst)
        next_files[relative] = {
            "source_sha256": source_hash,
            "deployed_sha256": deployed_hash,
            "action": action,
            "managed": deployed_hash == source_hash,
        }

    state = {
        "schema_version": 2,
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(source),
        "destination": str(destination),
        "allow_updates": bool(allow_updates),
        "files": next_files,
        "last_report": {key: len(value) for key, value in report.items()},
    }
    temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, state_path)
    try:
        state_path.chmod(0o600)
    except OSError:
        pass

    return {
        **report,
        "state_file": str(state_path),
        "backup_root": str(backup_root) if report["backups"] else None,
    }
