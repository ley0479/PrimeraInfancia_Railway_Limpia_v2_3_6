from __future__ import annotations

import json
from modules.dbapi_compat import sqlite3
from datetime import datetime
from typing import Any

from .schema import CALIDAD_DATOS_SCHEMA_SQL


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


class CalidadDatosRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        conn = self.connect()
        cur = conn.cursor()
        cur.executescript(CALIDAD_DATOS_SCHEMA_SQL)
        conn.commit()
        conn.close()

    def guardar_analisis(self, metadata: dict[str, Any], resumen: dict[str, Any], errores: list[dict[str, Any]], hallazgos: list[dict[str, Any]]) -> int:
        conn = self.connect()
        cur = conn.cursor()
        fecha = now_iso()
        resumen_counts = resumen.get('conteos', {})
        cur.execute(
            """
            INSERT INTO cd_analisis (
                fundacion_id, usuario_id, usuario, tipo_fuente, nombre_archivo, ruta_archivo,
                mes, anio, total_registros, total_hallazgos, hallazgos_criticos,
                hallazgos_altos, hallazgos_medios, hallazgos_bajos, estado,
                resumen_json, errores_json, fecha_analisis, fecha_actualizacion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.get('fundacion_id') or 1,
                metadata.get('usuario_id'),
                metadata.get('usuario') or 'sistema',
                metadata.get('tipo_fuente') or 'ARCHIVO',
                metadata.get('nombre_archivo'),
                metadata.get('ruta_archivo'),
                metadata.get('mes'),
                metadata.get('anio'),
                int(resumen.get('total_registros') or 0),
                len(hallazgos),
                int(resumen_counts.get('CRITICA') or 0),
                int(resumen_counts.get('ALTA') or 0),
                int(resumen_counts.get('MEDIA') or 0),
                int(resumen_counts.get('BAJA') or 0),
                'GENERADO',
                json.dumps(resumen, ensure_ascii=False),
                json.dumps(errores, ensure_ascii=False),
                fecha,
                fecha,
            ),
        )
        analisis_id = int(cur.lastrowid)

        for item in hallazgos:
            cur.execute(
                """
                INSERT INTO cd_hallazgos (
                    analisis_id, fundacion_id, tipo, categoria, severidad, documento,
                    nombre, unidad, docente, campo, valor_actual, valor_esperado,
                    descripcion, fila, hoja, datos_json, estado, fecha_creacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analisis_id,
                    metadata.get('fundacion_id') or 1,
                    item.get('tipo'),
                    item.get('categoria'),
                    item.get('severidad') or 'MEDIA',
                    item.get('documento'),
                    item.get('nombre'),
                    item.get('unidad'),
                    item.get('docente'),
                    item.get('campo'),
                    item.get('valor_actual'),
                    item.get('valor_esperado'),
                    item.get('descripcion'),
                    item.get('fila'),
                    item.get('hoja'),
                    json.dumps(item.get('datos') or {}, ensure_ascii=False),
                    item.get('estado') or 'ABIERTO',
                    fecha,
                ),
            )

        cur.execute(
            """
            INSERT INTO cd_auditoria (analisis_id, accion, detalle, usuario_id, usuario, fundacion_id, fecha, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analisis_id,
                'ANALISIS_CALIDAD_GENERADO',
                f"Hallazgos: {len(hallazgos)}",
                metadata.get('usuario_id'),
                metadata.get('usuario') or 'sistema',
                metadata.get('fundacion_id') or 1,
                fecha,
                metadata.get('ip'),
            ),
        )
        conn.commit()
        conn.close()
        return analisis_id

    def actualizar_reportes(self, analisis_id: int, excel: str | None = None, pdf: str | None = None) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE cd_analisis SET reporte_excel = COALESCE(?, reporte_excel), reporte_pdf = COALESCE(?, reporte_pdf), fecha_actualizacion = ? WHERE id = ?",
            (excel, pdf, now_iso(), analisis_id),
        )
        conn.commit()
        conn.close()

    def ultimo_analisis(self, fundacion_id: int, superadmin: bool = False) -> dict[str, Any] | None:
        conn = self.connect()
        if superadmin:
            row = conn.execute("SELECT * FROM cd_analisis ORDER BY fecha_analisis DESC, id DESC LIMIT 1").fetchone()
        else:
            row = conn.execute("SELECT * FROM cd_analisis WHERE fundacion_id = ? ORDER BY fecha_analisis DESC, id DESC LIMIT 1", (fundacion_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def historial(self, fundacion_id: int, superadmin: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        conn = self.connect()
        if superadmin:
            rows = conn.execute("SELECT * FROM cd_analisis ORDER BY fecha_analisis DESC, id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM cd_analisis WHERE fundacion_id = ? ORDER BY fecha_analisis DESC, id DESC LIMIT ?", (fundacion_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def obtener_analisis(self, analisis_id: int) -> dict[str, Any] | None:
        conn = self.connect()
        row = conn.execute("SELECT * FROM cd_analisis WHERE id = ?", (analisis_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def hallazgos(self, analisis_id: int, tipo: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
        conn = self.connect()
        if tipo and tipo != 'todos':
            rows = conn.execute(
                "SELECT * FROM cd_hallazgos WHERE analisis_id = ? AND tipo = ? ORDER BY severidad, id LIMIT ?",
                (analisis_id, tipo, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM cd_hallazgos WHERE analisis_id = ? ORDER BY severidad, tipo, id LIMIT ?",
                (analisis_id, limit),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def dashboard(self, fundacion_id: int, superadmin: bool = False) -> dict[str, Any]:
        ultimo = self.ultimo_analisis(fundacion_id, superadmin=superadmin)
        if not ultimo:
            return {
                'ultimo': None,
                'resumen': {},
                'conteos_tipo': {},
                'conteos_severidad': {},
                'criticos': [],
            }
        analisis_id = ultimo['id']
        conn = self.connect()
        params = (analisis_id,)
        tipo_rows = conn.execute(
            "SELECT tipo, COUNT(*) total FROM cd_hallazgos WHERE analisis_id = ? GROUP BY tipo ORDER BY total DESC",
            params,
        ).fetchall()
        sev_rows = conn.execute(
            "SELECT severidad, COUNT(*) total FROM cd_hallazgos WHERE analisis_id = ? GROUP BY severidad ORDER BY total DESC",
            params,
        ).fetchall()
        criticos = conn.execute(
            "SELECT * FROM cd_hallazgos WHERE analisis_id = ? AND severidad IN ('CRITICA','ALTA') ORDER BY id DESC LIMIT 20",
            params,
        ).fetchall()
        conn.close()
        resumen = {}
        try:
            resumen = json.loads(ultimo.get('resumen_json') or '{}')
        except Exception:
            resumen = {}
        return {
            'ultimo': ultimo,
            'resumen': resumen,
            'conteos_tipo': {r['tipo']: r['total'] for r in tipo_rows},
            'conteos_severidad': {r['severidad']: r['total'] for r in sev_rows},
            'criticos': [dict(r) for r in criticos],
        }

    def log(self, analisis_id: int | None, accion: str, detalle: str, user: dict[str, Any], ip: str | None = None) -> None:
        conn = self.connect()
        conn.execute(
            """
            INSERT INTO cd_auditoria (analisis_id, accion, detalle, usuario_id, usuario, fundacion_id, fecha, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analisis_id,
                accion,
                detalle,
                user.get('id') or user.get('usuario_id'),
                user.get('username') or user.get('email') or 'sistema',
                user.get('fundacion_id') or 1,
                now_iso(),
                ip,
            ),
        )
        conn.commit()
        conn.close()
