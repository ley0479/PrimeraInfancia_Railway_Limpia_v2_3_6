#!/usr/bin/env python3
"""Inicializa carpetas, semillas, esquema y administrador en el volumen runtime."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def copy_missing_tree(source: Path, destination: Path) -> list[str]:
    copied: list[str] = []
    if not source.exists():
        raise RuntimeError(f'No existe el directorio de semillas: {source}')
    for src in sorted(source.rglob('*')):
        if src.is_symlink():
            raise RuntimeError(f'No se permiten enlaces simbólicos en semillas: {src}')
        relative = src.relative_to(source)
        dst = destination / relative
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(str(relative))
    return copied


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'si', 'sí', 'on'}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_seed_manifest(seed_dir: Path) -> None:
    manifest_path = seed_dir / 'seed_manifest.json'
    if not manifest_path.is_file():
        raise RuntimeError(f'No existe el manifiesto de plantillas limpias: {manifest_path}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not manifest.get('sanitizada'):
        raise RuntimeError('El manifiesto de plantillas no confirma sanitización.')
    records = manifest.get('plantillas') or manifest.get('files') or []
    if not isinstance(records, list) or not records:
        raise RuntimeError('El manifiesto de plantillas está vacío o es inválido.')
    for record in records:
        name = record.get('archivo') or record.get('name') or record.get('filename')
        expected = (record.get('sha256') or '').lower().strip()
        if not name or not expected:
            raise RuntimeError('Registro incompleto en el manifiesto de plantillas.')
        candidate = (seed_dir / name).resolve()
        if seed_dir.resolve() not in candidate.parents:
            raise RuntimeError(f'Ruta insegura en manifiesto de plantillas: {name}')
        if not candidate.is_file():
            raise RuntimeError(f'Plantilla declarada y ausente: {name}')
        actual = sha256_file(candidate)
        if actual != expected:
            raise RuntimeError(f'Hash inválido para plantilla {name}.')


def main() -> int:
    os.environ.setdefault('APP_ENV', 'production')
    from config import get_config

    config_class = get_config(os.environ.get('APP_ENV'))
    runtime_dirs = [
        Path(config_class.DATA_DIR),
        Path(config_class.UPLOAD_FOLDER),
        Path(config_class.TEMPLATES_FOLDER),
        Path(config_class.OUTPUT_FOLDER),
        Path(config_class.BACKUPS_FOLDER),
        Path(config_class.DOCUMENTOS_FOLDER),
        Path(config_class.CUENTAS_COBRO_FOLDER),
        Path(config_class.LOCAL_STORAGE_PATH),
        Path(config_class.LOG_FOLDER),
    ]
    for directory in runtime_dirs:
        directory.mkdir(parents=True, exist_ok=True)

    database_path = Path(config_class.DATABASE_PATH)
    fresh_database = not database_path.exists()
    seed_dir = Path(config_class.SEED_TEMPLATES_FOLDER)
    verify_seed_manifest(seed_dir)
    copied = copy_missing_tree(seed_dir, Path(config_class.TEMPLATES_FOLDER))

    # Importar después de crear el volumen y copiar plantillas: varios módulos las inspeccionan al registrarse.
    import app as app_module
    from modules.seguridad.services import bootstrap_initial_admin, ensure_security_schema

    app_module.init_db()
    ensure_security_schema(config_class.DATABASE_PATH)
    admin_result = bootstrap_initial_admin(config_class.DATABASE_PATH, app_module.app.config)

    with sqlite3.connect(config_class.DATABASE_PATH, timeout=30) as conn:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        user_count = conn.execute('SELECT COUNT(*) FROM usuarios_app').fetchone()[0]
        superadmin_count = conn.execute("SELECT COUNT(*) FROM usuarios_app WHERE rol='SUPERADMIN' AND activo=1").fetchone()[0]
        beneficiary_count = conn.execute('SELECT COUNT(*) FROM beneficiarios').fetchone()[0]
    if integrity != 'ok':
        raise RuntimeError(f'Falló PRAGMA integrity_check: {integrity}')
    if user_count < 1 or superadmin_count < 1:
        raise RuntimeError('La base inicializada no contiene un SUPERADMIN activo.')
    if fresh_database and beneficiary_count != 0:
        raise RuntimeError('Una base nueva no puede contener beneficiarios precargados.')
    if beneficiary_count != 0 and not env_bool('ALLOW_EXISTING_RUNTIME_DATA', False):
        # Nunca se borra un volumen existente de manera automática.
        print('ADVERTENCIA: el volumen ya contenía beneficiarios; no se modificaron ni borraron.', flush=True)
    if admin_result.get('configuration_mismatch'):
        print(
            'ADVERTENCIA: INITIAL_ADMIN_* no coincide con el SUPERADMIN existente; '
            'no se creó ni modificó ninguna cuenta.',
            flush=True,
        )

    marker = Path(config_class.DATA_DIR) / '.primera_infancia_initialized.json'
    marker.write_text(json.dumps({
        'version': app_module.app.config.get('APP_VERSION'),
        'database': str(config_class.DATABASE_PATH),
        'templates_seeded': copied,
        'admin_created': bool(admin_result.get('created')),
        'users': user_count,
        'active_superadmins': superadmin_count,
        'beneficiaries': beneficiary_count,
        'integrity': integrity,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        marker.chmod(0o600)
    except OSError:
        pass

    print(
        f"Inicialización correcta: DB íntegra, {user_count} usuario(s), "
        f"{beneficiary_count} beneficiario(s), {len(copied)} plantilla(s) nueva(s).",
        flush=True,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
