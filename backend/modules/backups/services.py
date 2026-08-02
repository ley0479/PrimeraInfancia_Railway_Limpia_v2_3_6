from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BACKUPS_SCHEMA_SQL


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def safe_slug(value: str) -> str:
    text = ''.join(ch if ch.isalnum() else '_' for ch in str(value or '').upper())
    return '_'.join([p for p in text.split('_') if p])[:80] or 'BACKUP'


class BackupService:
    """Servicio central de backups para PrimeraInfancia.

    Los backups se guardan como ZIP con una copia consistente de database.sqlite3
    y un manifest JSON. No modifica formatos ICBF ni carpetas de salida.
    """

    def __init__(self, database_path: str, backups_folder: str):
        self.database_path = os.path.abspath(database_path)
        self.backups_folder = os.path.abspath(backups_folder)
        os.makedirs(self.backups_folder, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        conn = self.connect()
        conn.executescript(BACKUPS_SCHEMA_SQL)
        conn.commit()
        conn.close()

    def audit(self, accion: str, backup_id: int | None = None, detalle: str | None = None, user: dict | None = None, ip: str | None = None) -> None:
        try:
            self.init()
            user = user or {}
            conn = self.connect()
            conn.execute(
                """
                INSERT INTO backups_auditoria
                (backup_id, accion, detalle, usuario_id, username, fundacion_id, fecha, ip)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    backup_id,
                    accion,
                    detalle,
                    user.get('id'),
                    user.get('username') or user.get('email') or user.get('nombre_completo') or 'sistema',
                    user.get('fundacion_id') or 1,
                    now_iso(),
                    ip,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    @staticmethod
    def sha256_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()

    def sqlite_integrity_check(self, sqlite_path: str) -> tuple[bool, str]:
        try:
            conn = sqlite3.connect(sqlite_path)
            result = conn.execute('PRAGMA integrity_check').fetchone()
            conn.close()
            value = result[0] if result else 'sin resultado'
            return str(value).lower() == 'ok', str(value)
        except Exception as exc:
            return False, str(exc)

    def _copy_database_consistent(self, destination: str) -> None:
        """Copia database.sqlite3 usando la API backup de SQLite."""
        source = sqlite3.connect(self.database_path)
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

    def create_backup(self, motivo: str = 'MANUAL', descripcion: str = '', user: dict | None = None, ip: str | None = None) -> dict[str, Any]:
        self.init()
        if not os.path.exists(self.database_path):
            raise FileNotFoundError('No existe database.sqlite3 para respaldar.')

        motivo = safe_slug(motivo)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}_{motivo}.zip'
        output_path = os.path.join(self.backups_folder, filename)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_copy = os.path.join(tmpdir, 'database.sqlite3')
            self._copy_database_consistent(db_copy)
            ok, integrity = self.sqlite_integrity_check(db_copy)
            if not ok:
                raise RuntimeError(f'La base actual no pasó validación antes de backup: {integrity}')
            db_hash = self.sha256_file(db_copy)
            manifest = {
                'app': 'PrimeraInfancia',
                'tipo': 'BACKUP_DATABASE_SQLITE',
                'motivo': motivo,
                'descripcion': descripcion,
                'fecha_creacion': now_iso(),
                'database_file': 'database.sqlite3',
                'database_sha256': db_hash,
                'database_size': os.path.getsize(db_copy),
                'usuario': {
                    'id': (user or {}).get('id'),
                    'username': (user or {}).get('username'),
                    'fundacion_id': (user or {}).get('fundacion_id') or 1,
                },
            }
            manifest_path = os.path.join(tmpdir, 'manifest.json')
            with open(manifest_path, 'w', encoding='utf-8') as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(db_copy, 'database.sqlite3')
                zf.write(manifest_path, 'manifest.json')

        zip_hash = self.sha256_file(output_path)
        size = os.path.getsize(output_path)
        conn = self.connect()
        cur = conn.execute(
            """
            INSERT INTO backups_sistema
            (archivo, ruta_archivo, motivo, descripcion, sha256, tamano_bytes, estado, integridad,
             creado_por_id, creado_por, fundacion_id, fecha_creacion, fecha_validacion)
            VALUES (?, ?, ?, ?, ?, ?, 'VALIDO', ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                output_path,
                motivo,
                descripcion,
                zip_hash,
                size,
                'OK',
                (user or {}).get('id'),
                (user or {}).get('username') or (user or {}).get('email') or 'sistema',
                (user or {}).get('fundacion_id') or 1,
                now_iso(),
                now_iso(),
            ),
        )
        backup_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
        self.audit('BACKUP_CREADO', backup_id, f'{motivo}: {descripcion}', user, ip)
        return self.get_backup(backup_id) or {}

    def create_daily_if_needed(self, user: dict | None = None) -> dict[str, Any] | None:
        self.init()
        today = datetime.now().date().isoformat()
        conn = self.connect()
        row = conn.execute(
            """
            SELECT * FROM backups_sistema
            WHERE motivo = 'AUTO_DIARIO' AND substr(fecha_creacion, 1, 10) = ? AND estado = 'VALIDO'
            ORDER BY fecha_creacion DESC LIMIT 1
            """,
            (today,),
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return self.create_backup('AUTO_DIARIO', 'Backup automático diario al iniciar la plataforma.', user=user or {'username': 'sistema', 'fundacion_id': 1})

    def list_backups(self, limit: int = 100) -> list[dict[str, Any]]:
        self.init()
        conn = self.connect()
        rows = conn.execute(
            """
            SELECT id, archivo, ruta_archivo, motivo, descripcion, sha256, tamano_bytes, estado,
                   integridad, creado_por_id, creado_por, fundacion_id, fecha_creacion, fecha_validacion
            FROM backups_sistema
            ORDER BY fecha_creacion DESC LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_backup(self, backup_id: int) -> dict[str, Any] | None:
        self.init()
        conn = self.connect()
        row = conn.execute('SELECT * FROM backups_sistema WHERE id=?', (backup_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def validate_backup(self, backup_id: int) -> dict[str, Any]:
        backup = self.get_backup(backup_id)
        if not backup:
            raise FileNotFoundError('Backup no encontrado.')
        path = backup['ruta_archivo']
        if not path or not os.path.exists(path):
            self._update_status(backup_id, 'ERROR', 'ARCHIVO_NO_EXISTE')
            raise FileNotFoundError('El archivo físico del backup no existe.')
        current_hash = self.sha256_file(path)
        if current_hash != backup['sha256']:
            self._update_status(backup_id, 'ERROR', 'HASH_INVALIDO')
            raise RuntimeError('El hash del backup no coincide. El archivo pudo modificarse.')
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(path, 'r') as zf:
                names = set(zf.namelist())
                if 'database.sqlite3' not in names or 'manifest.json' not in names:
                    self._update_status(backup_id, 'ERROR', 'CONTENIDO_INCOMPLETO')
                    raise RuntimeError('Backup incompleto: faltan database.sqlite3 o manifest.json.')
                zf.extract('database.sqlite3', tmpdir)
                zf.extract('manifest.json', tmpdir)
            manifest_path = os.path.join(tmpdir, 'manifest.json')
            with open(manifest_path, 'r', encoding='utf-8') as fh:
                manifest = json.load(fh)
            db_path = os.path.join(tmpdir, 'database.sqlite3')
            expected_db_hash = manifest.get('database_sha256')
            actual_db_hash = self.sha256_file(db_path)
            if expected_db_hash and expected_db_hash != actual_db_hash:
                self._update_status(backup_id, 'ERROR', 'DB_HASH_INVALIDO')
                raise RuntimeError('El hash interno de database.sqlite3 no coincide.')
            ok, integrity = self.sqlite_integrity_check(db_path)
            if not ok:
                self._update_status(backup_id, 'ERROR', f'INTEGRIDAD_{integrity}')
                raise RuntimeError(f'La base dentro del backup no es íntegra: {integrity}')
        self._update_status(backup_id, 'VALIDO', 'OK')
        return {**backup, 'estado': 'VALIDO', 'integridad': 'OK', 'validado': True}

    def _update_status(self, backup_id: int, estado: str, integridad: str) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE backups_sistema SET estado=?, integridad=?, fecha_validacion=? WHERE id=?",
            (estado, integridad[:500], now_iso(), backup_id),
        )
        conn.commit()
        conn.close()

    def restore_backup(self, backup_id: int, user: dict | None = None, ip: str | None = None) -> dict[str, Any]:
        backup = self.validate_backup(backup_id)
        # Backup de seguridad antes de sobrescribir la base actual.
        pre_restore = self.create_backup('ANTES_RESTAURAR_BACKUP', f"Backup automático antes de restaurar el backup #{backup_id}.", user=user, ip=ip)
        path = backup['ruta_archivo']
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(path, 'r') as zf:
                zf.extract('database.sqlite3', tmpdir)
            restored_db = os.path.join(tmpdir, 'database.sqlite3')
            ok, integrity = self.sqlite_integrity_check(restored_db)
            if not ok:
                raise RuntimeError(f'No se puede restaurar. Integridad inválida: {integrity}')
            # Copia atómica básica: primero .tmp y luego replace.
            temp_target = f'{self.database_path}.restore_tmp'
            shutil.copy2(restored_db, temp_target)
            os.replace(temp_target, self.database_path)
        # La DB restaurada puede no tener las tablas de backups si es muy antigua. Asegurarlas y auditar.
        self.init()
        self.audit('BACKUP_RESTAURADO', backup_id, f'Restaurado. Backup preventivo: {pre_restore.get("archivo")}', user, ip)
        return {
            'restaurado': True,
            'backup': backup,
            'backup_previo_restauracion': pre_restore,
            'message': 'Backup restaurado correctamente. Reinicia el backend para recargar todas las conexiones.'
        }

    def status(self) -> dict[str, Any]:
        self.init()
        conn = self.connect()
        total = conn.execute('SELECT COUNT(*) AS c FROM backups_sistema').fetchone()['c']
        validos = conn.execute("SELECT COUNT(*) AS c FROM backups_sistema WHERE estado='VALIDO'").fetchone()['c']
        errores = conn.execute("SELECT COUNT(*) AS c FROM backups_sistema WHERE estado!='VALIDO'").fetchone()['c']
        ultimo = conn.execute('SELECT * FROM backups_sistema ORDER BY fecha_creacion DESC LIMIT 1').fetchone()
        hoy = datetime.now().date().isoformat()
        diario = conn.execute("SELECT * FROM backups_sistema WHERE motivo='AUTO_DIARIO' AND substr(fecha_creacion,1,10)=? ORDER BY fecha_creacion DESC LIMIT 1", (hoy,)).fetchone()
        conn.close()
        return {
            'total': int(total or 0),
            'validos': int(validos or 0),
            'errores': int(errores or 0),
            'ultimo': dict(ultimo) if ultimo else None,
            'backup_diario_hoy': dict(diario) if diario else None,
            'carpeta': self.backups_folder,
            'database': self.database_path,
        }
