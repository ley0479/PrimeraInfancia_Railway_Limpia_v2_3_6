from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from modules.dbapi_compat import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from database import database

from .schema import BACKUPS_SCHEMA_SQL


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def safe_slug(value: str) -> str:
    text = ''.join(ch if ch.isalnum() else '_' for ch in str(value or '').upper())
    return '_'.join([p for p in text.split('_') if p])[:80] or 'BACKUP'


class BackupService:
    """Servicio central de backups para SQLite y PostgreSQL.

    SQLite usa la API de backup. PostgreSQL usa ``pg_dump`` en formato custom.
    Los productos se envuelven en ZIP con manifiesto y SHA-256.
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

    @property
    def backend_name(self) -> str:
        return 'postgresql' if database.is_postgresql else 'sqlite'

    @staticmethod
    def _plain_postgres_url(url: str) -> str:
        return str(url or '').replace('postgresql+psycopg://', 'postgresql://', 1)

    def _create_postgresql_dump(self, destination: str) -> None:
        executable = shutil.which('pg_dump') or shutil.which('pg_dump.exe')
        if not executable:
            raise RuntimeError('No se encontró pg_dump. Instale PostgreSQL Client Tools.')
        url = self._plain_postgres_url(database.database_url or '')
        if not url.startswith('postgresql://'):
            raise RuntimeError('DATABASE_URL PostgreSQL no está configurada.')
        completed = subprocess.run(
            [executable, '--dbname', url, '--format=custom', '--no-owner', '--no-acl', '--file', destination],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError('pg_dump falló: ' + (completed.stderr or completed.stdout or 'sin detalle')[-1000:])

    def _validate_postgresql_dump(self, path: str) -> tuple[bool, str]:
        executable = shutil.which('pg_restore') or shutil.which('pg_restore.exe')
        if not executable:
            return False, 'No se encontró pg_restore para validar el archivo.'
        completed = subprocess.run(
            [executable, '--list', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=120, check=False,
        )
        if completed.returncode != 0:
            return False, (completed.stderr or completed.stdout or 'pg_restore --list falló')[-1000:]
        return True, 'OK'

    def create_backup(self, motivo: str = 'MANUAL', descripcion: str = '', user: dict | None = None, ip: str | None = None) -> dict[str, Any]:
        self.init()
        backend = self.backend_name
        if backend == 'sqlite' and not os.path.exists(self.database_path):
            raise FileNotFoundError('No existe database.sqlite3 para respaldar.')

        motivo = safe_slug(motivo)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}_{motivo}_{backend}.zip'
        output_path = os.path.join(self.backups_folder, filename)

        with tempfile.TemporaryDirectory() as tmpdir:
            if backend == 'postgresql':
                payload_name = 'database.dump'
                payload = os.path.join(tmpdir, payload_name)
                self._create_postgresql_dump(payload)
                ok, integrity = self._validate_postgresql_dump(payload)
                payload_type = 'BACKUP_DATABASE_POSTGRESQL'
            else:
                payload_name = 'database.sqlite3'
                payload = os.path.join(tmpdir, payload_name)
                self._copy_database_consistent(payload)
                ok, integrity = self.sqlite_integrity_check(payload)
                payload_type = 'BACKUP_DATABASE_SQLITE'
            if not ok:
                raise RuntimeError(f'La base actual no pasó validación antes de backup: {integrity}')
            payload_hash = self.sha256_file(payload)
            manifest = {
                'app': 'PrimeraInfancia', 'version': '2.6.0', 'tipo': payload_type,
                'backend': backend, 'motivo': motivo, 'descripcion': descripcion,
                'fecha_creacion': now_iso(), 'database_file': payload_name,
                'database_sha256': payload_hash, 'database_size': os.path.getsize(payload),
                'usuario': {'id': (user or {}).get('id'), 'username': (user or {}).get('username'),
                            'fundacion_id': (user or {}).get('fundacion_id') or 1},
            }
            manifest_path = os.path.join(tmpdir, 'manifest.json')
            with open(manifest_path, 'w', encoding='utf-8') as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(payload, payload_name); zf.write(manifest_path, 'manifest.json')

        zip_hash = self.sha256_file(output_path); size = os.path.getsize(output_path)
        conn = self.connect()
        cur = conn.execute(
            """INSERT INTO backups_sistema
            (archivo, ruta_archivo, motivo, descripcion, sha256, tamano_bytes, estado, integridad,
             creado_por_id, creado_por, fundacion_id, fecha_creacion, fecha_validacion)
            VALUES (?, ?, ?, ?, ?, ?, 'VALIDO', ?, ?, ?, ?, ?, ?)""",
            (filename, output_path, motivo, descripcion, zip_hash, size, f'{backend.upper()}:OK',
             (user or {}).get('id'), (user or {}).get('username') or (user or {}).get('email') or 'sistema',
             (user or {}).get('fundacion_id') or 1, now_iso(), now_iso()),
        )
        backup_id = int(cur.lastrowid); conn.commit(); conn.close()
        self.audit('BACKUP_CREADO', backup_id, f'{backend}:{motivo}: {descripcion}', user, ip)
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
        if self.sha256_file(path) != backup['sha256']:
            self._update_status(backup_id, 'ERROR', 'HASH_INVALIDO')
            raise RuntimeError('El hash del backup no coincide.')
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(path, 'r') as zf:
                names=set(zf.namelist())
                if 'manifest.json' not in names:
                    raise RuntimeError('Backup incompleto: falta manifest.json.')
                zf.extract('manifest.json', tmpdir)
                manifest=json.loads(Path(tmpdir,'manifest.json').read_text(encoding='utf-8'))
                payload_name=manifest.get('database_file')
                if not payload_name or payload_name not in names:
                    raise RuntimeError('Backup incompleto: falta el archivo de base declarado.')
                zf.extract(payload_name,tmpdir)
            payload=os.path.join(tmpdir,payload_name)
            expected=manifest.get('database_sha256')
            if expected and expected != self.sha256_file(payload):
                self._update_status(backup_id,'ERROR','DB_HASH_INVALIDO')
                raise RuntimeError('El hash interno de la base no coincide.')
            if manifest.get('backend') == 'postgresql' or payload_name.endswith('.dump'):
                ok, integrity=self._validate_postgresql_dump(payload)
            else:
                ok, integrity=self.sqlite_integrity_check(payload)
            if not ok:
                self._update_status(backup_id,'ERROR',f'INTEGRIDAD_{integrity}')
                raise RuntimeError(f'Backup inválido: {integrity}')
        self._update_status(backup_id,'VALIDO',f'{manifest.get("backend","sqlite").upper()}:OK')
        return {**backup,'estado':'VALIDO','integridad':'OK','validado':True,'backend':manifest.get('backend','sqlite')}

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
        if self.backend_name == 'postgresql' or backup.get('backend') == 'postgresql':
            raise RuntimeError(
                'Por seguridad PostgreSQL no se restaura con el servidor activo. '
                'Use RESTAURAR_POSTGRESQL.bat durante una ventana de mantenimiento.'
            )
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
