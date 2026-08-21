
from __future__ import annotations

import json
import os
from modules.dbapi_compat import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .services import connect, init_schema, now_iso


def row_to_dict(row):
    return dict(row) if row else None


class MotorPlantillasRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path

    def log(self, accion: str, plantilla_id=None, mapeo_id=None, usuario_id=None, fundacion_id=1, detalle=None):
        conn = connect(self.database_path)
        conn.execute("""
            INSERT INTO mp_auditoria
            (accion, plantilla_id, mapeo_id, usuario_id, fundacion_id, detalle_json, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (accion, plantilla_id, mapeo_id, usuario_id, fundacion_id, json.dumps(detalle or {}, ensure_ascii=False), now_iso()))
        conn.commit()
        conn.close()

    def create_template(self, data: dict) -> int:
        conn = connect(self.database_path)
        cur = conn.execute("""
            INSERT INTO mp_plantillas
            (nombre, tipo, nombre_original, nombre_guardado, ruta_archivo, version, estado,
             hoja_principal, total_hojas, metadata_json, fundacion_id, usuario_creador_id,
             fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('nombre') or data.get('nombre_original') or 'Plantilla oficial',
            data.get('tipo') or 'OTROS',
            data.get('nombre_original'),
            data.get('nombre_guardado'),
            data.get('ruta_archivo'),
            data.get('version') or '1.0',
            data.get('estado') or 'ACTIVA',
            data.get('hoja_principal'),
            int(data.get('total_hojas') or 0),
            json.dumps(data.get('metadata') or {}, ensure_ascii=False),
            int(data.get('fundacion_id') or 1),
            data.get('usuario_creador_id'),
            now_iso(),
            now_iso(),
        ))
        plantilla_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
        self.log('CREAR_PLANTILLA', plantilla_id=plantilla_id, usuario_id=data.get('usuario_creador_id'), fundacion_id=int(data.get('fundacion_id') or 1), detalle=data)
        return plantilla_id

    def list_templates(self, fundacion_id=None, include_all=False) -> list[dict]:
        conn = connect(self.database_path)
        if include_all or not fundacion_id:
            rows = conn.execute("SELECT * FROM mp_plantillas ORDER BY fecha_creacion DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM mp_plantillas WHERE fundacion_id=? ORDER BY fecha_creacion DESC", (fundacion_id,)).fetchall()
        conn.close()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item['metadata'] = json.loads(item.get('metadata_json') or '{}')
            except Exception:
                item['metadata'] = {}
            result.append(item)
        return result

    def get_template(self, plantilla_id: int, fundacion_id: int | None = None) -> dict | None:
        conn = connect(self.database_path)
        row = conn.execute("SELECT * FROM mp_plantillas WHERE id=? AND fundacion_id=?", (plantilla_id, fundacion_id)).fetchone() if fundacion_id is not None else conn.execute("SELECT * FROM mp_plantillas WHERE id=?", (plantilla_id,)).fetchone()
        conn.close()
        item = row_to_dict(row)
        if item:
            try:
                item['metadata'] = json.loads(item.get('metadata_json') or '{}')
            except Exception:
                item['metadata'] = {}
        return item

    def get_active_mapping(self, plantilla_id: int) -> dict | None:
        conn = connect(self.database_path)
        row = conn.execute("SELECT * FROM mp_mapeos WHERE plantilla_id=? AND activo=1 ORDER BY fecha_creacion DESC LIMIT 1", (plantilla_id,)).fetchone()
        conn.close()
        item = row_to_dict(row)
        if item:
            try:
                item['mapeo'] = json.loads(item.get('mapeo_json') or '[]')
            except Exception:
                item['mapeo'] = []
            try:
                item['validacion'] = json.loads(item.get('validacion_json') or '{}')
            except Exception:
                item['validacion'] = {}
        return item

    def save_test(self, plantilla_id: int, mapeo_id: int | None, unidad: str, result: dict, user: dict) -> int:
        conn = connect(self.database_path)
        cur = conn.execute("""
            INSERT INTO mp_pruebas
            (plantilla_id, mapeo_id, unidad, estado, total_usuarios, errores_json,
             archivo_generado, usuario_id, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plantilla_id, mapeo_id, unidad,
            'VALIDO' if result.get('ok') else 'ERROR',
            int(result.get('total_usuarios') or 0),
            json.dumps(result.get('validation') or {}, ensure_ascii=False),
            result.get('archivo'),
            user.get('usuario_id'),
            now_iso(),
        ))
        prueba_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
        self.log('PROBAR_UNIDAD', plantilla_id=plantilla_id, mapeo_id=mapeo_id, usuario_id=user.get('usuario_id'), fundacion_id=user.get('fundacion_id'), detalle={'unidad': unidad, 'ok': result.get('ok'), 'prueba_id': prueba_id})
        return prueba_id

    def get_test(self, prueba_id: int) -> dict | None:
        conn = connect(self.database_path)
        row = conn.execute("SELECT * FROM mp_pruebas WHERE id=?", (prueba_id,)).fetchone()
        conn.close()
        return row_to_dict(row)

    def dashboard(self, fundacion_id=None) -> dict:
        conn = connect(self.database_path)
        params = []
        where = ''
        if fundacion_id:
            where = 'WHERE fundacion_id=?'
            params = [fundacion_id]
        total = conn.execute(f"SELECT COUNT(*) AS c FROM mp_plantillas {where}", params).fetchone()['c']
        mapeadas = conn.execute("""
            SELECT COUNT(DISTINCT plantilla_id) AS c FROM mp_mapeos WHERE activo=1
        """).fetchone()['c']
        pruebas = conn.execute("SELECT COUNT(*) AS c FROM mp_pruebas").fetchone()['c']
        errores = conn.execute("SELECT COUNT(*) AS c FROM mp_pruebas WHERE estado='ERROR'").fetchone()['c']
        conn.close()
        return {
            'plantillas': total,
            'plantillas_mapeadas': mapeadas,
            'pruebas': pruebas,
            'pruebas_error': errores,
        }

    # ===== ALPHA52 — Motor de Plantillas Versionado =====
    def _ensure_oficial(self, conn, tipo_formato: str, codigo: str | None, nombre: str, fundacion_id: int) -> int:
        tipo = (tipo_formato or 'OTROS').upper()
        row = conn.execute("SELECT id FROM plantillas_oficiales WHERE tipo_formato=? AND COALESCE(codigo,'')=COALESCE(?, '') AND fundacion_id=? LIMIT 1", (tipo, codigo or '', fundacion_id)).fetchone()
        if row:
            return int(row['id'])
        cur = conn.execute("""
            INSERT INTO plantillas_oficiales (tipo_formato, codigo, nombre, descripcion, activo, fundacion_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
        """, (tipo, codigo or '', nombre or tipo, f'Plantilla oficial versionada para {tipo}', fundacion_id, now_iso(), now_iso()))
        return int(cur.lastrowid)

    def create_template_version_record(self, plantilla_id: int, data: dict, user: dict) -> int:
        conn = connect(self.database_path)
        fundacion_id=int(user.get('fundacion_id') or 1)
        plantilla = conn.execute("SELECT * FROM mp_plantillas WHERE id=? AND fundacion_id=?", (plantilla_id,fundacion_id)).fetchone()
        if not plantilla:
            conn.close()
            raise ValueError('Plantilla base no encontrada')
        p = dict(plantilla)
        tipo = (data.get('tipo_formato') or p.get('tipo') or 'OTROS').upper()
        codigo = data.get('codigo') or p.get('codigo') or ''
        nombre = data.get('nombre') or p.get('nombre') or p.get('nombre_original') or tipo
        oficial_id = self._ensure_oficial(conn, tipo, codigo, nombre, fundacion_id)
        cur = conn.execute("""
            INSERT INTO plantillas_oficiales_versiones
            (plantilla_oficial_id, mp_plantilla_id, tipo_formato, codigo, nombre, version,
             fecha_vigencia, fecha_vigencia_fin, estado, estado_publicacion,
             archivo_path, hash_sha256, manual_path, reglas_json, archivo_original,
             observaciones, mapeo_json, productos_json, usuario_carga, fundacion_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            oficial_id, plantilla_id, tipo, codigo, nombre, data.get('version') or p.get('version') or '1.0',
            data.get('fecha_vigencia') or p.get('fecha_vigencia') or '', data.get('fecha_vigencia_fin') or '',
            data.get('estado') or 'borrador', data.get('estado_publicacion') or data.get('estado') or 'borrador',
            p.get('ruta_archivo'), data.get('hash_sha256') or '', data.get('manual_path') or '',
            json.dumps(data.get('reglas') or data.get('reglas_json') or [], ensure_ascii=False) if not isinstance(data.get('reglas_json'), str) else data.get('reglas_json'),
            p.get('nombre_original'), data.get('observaciones') or p.get('observaciones') or '',
            json.dumps(data.get('mapeo') or [], ensure_ascii=False),
            json.dumps(data.get('productos') or [], ensure_ascii=False),
            user.get('usuario_id'), fundacion_id, now_iso(), now_iso()
        ))
        version_id = int(cur.lastrowid)
        conn.execute("UPDATE mp_plantillas SET plantilla_oficial_version_id=?, estado=?, codigo=?, fecha_vigencia=?, observaciones=?, fecha_actualizacion=? WHERE id=?", (
            version_id, data.get('estado') or 'BORRADOR', codigo, data.get('fecha_vigencia') or '', data.get('observaciones') or '', now_iso(), plantilla_id
        ))
        conn.commit()
        conn.close()
        self.log('CREAR_VERSION_PLANTILLA', plantilla_id=plantilla_id, usuario_id=user.get('usuario_id'), fundacion_id=user.get('fundacion_id'), detalle={'version_id': version_id, 'tipo': tipo, 'codigo': codigo})
        return version_id

    def get_version_by_template(self, plantilla_id: int) -> dict | None:
        conn = connect(self.database_path)
        row = conn.execute("SELECT * FROM plantillas_oficiales_versiones WHERE mp_plantilla_id=? ORDER BY id DESC LIMIT 1", (plantilla_id,)).fetchone()
        conn.close()
        item = row_to_dict(row)
        if item:
            try:
                item['mapeo'] = json.loads(item.get('mapeo_json') or '[]')
            except Exception:
                item['mapeo'] = []
            try:
                item['productos'] = json.loads(item.get('productos_json') or '[]')
            except Exception:
                item['productos'] = []
        return item

    def list_versions(self, tipo_formato: str | None = None, fundacion_id: int | None = None) -> list[dict]:
        conn = connect(self.database_path)
        if tipo_formato and fundacion_id is not None:
            rows = conn.execute("SELECT * FROM plantillas_oficiales_versiones WHERE tipo_formato=? AND fundacion_id=? ORDER BY created_at DESC", (tipo_formato.upper(),fundacion_id)).fetchall()
        elif tipo_formato:
            rows = conn.execute("SELECT * FROM plantillas_oficiales_versiones WHERE tipo_formato=? ORDER BY created_at DESC", (tipo_formato.upper(),)).fetchall()
        elif fundacion_id is not None:
            rows = conn.execute("SELECT * FROM plantillas_oficiales_versiones WHERE fundacion_id=? ORDER BY created_at DESC",(fundacion_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM plantillas_oficiales_versiones ORDER BY created_at DESC").fetchall()
        conn.close()
        return [row_to_dict(r) for r in rows]

    def save_products(self, version_id: int, productos: list[dict], user: dict | None = None) -> list[dict]:
        from .services import normalize_products, col_letter_to_index
        productos = normalize_products(productos)
        conn = connect(self.database_path)
        conn.execute("DELETE FROM plantillas_oficiales_productos WHERE version_id=?", (version_id,))
        for item in productos:
            conn.execute("""
                INSERT INTO plantillas_oficiales_productos
                (version_id, nombre_producto, columna, col_index, unidad_medida, cantidad, grupo_etario_aplica, orden, activo, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, item['nombre_producto'], item.get('columna') or '', int(item.get('col_index') or col_letter_to_index(item.get('columna') or '') or 0),
                item.get('unidad_medida') or '', item.get('cantidad') or '', item.get('grupo_etario_aplica') or 'todos',
                int(item.get('orden') or 0), int(item.get('activo', 1)), now_iso(), now_iso()
            ))
        conn.execute("UPDATE plantillas_oficiales_versiones SET productos_json=?, updated_at=? WHERE id=?", (json.dumps(productos, ensure_ascii=False), now_iso(), version_id))
        conn.commit()
        conn.close()
        self.log('GUARDAR_PRODUCTOS_RPP', usuario_id=(user or {}).get('usuario_id'), fundacion_id=(user or {}).get('fundacion_id', 1), detalle={'version_id': version_id, 'total': len(productos)})
        return productos

    def get_products(self, version_id: int) -> list[dict]:
        conn = connect(self.database_path)
        rows = conn.execute("SELECT * FROM plantillas_oficiales_productos WHERE version_id=? ORDER BY orden, id", (version_id,)).fetchall()
        if not rows:
            row = conn.execute("SELECT productos_json FROM plantillas_oficiales_versiones WHERE id=?", (version_id,)).fetchone()
            conn.close()
            if row:
                try:
                    return json.loads(row['productos_json'] or '[]')
                except Exception:
                    return []
            return []
        conn.close()
        return [row_to_dict(r) for r in rows]

    def save_mapping(self, plantilla_id: int, mapping: list[dict], validation: dict, user: dict, nombre='Mapeo principal', version='1.0') -> int:
        conn = connect(self.database_path)
        conn.execute("UPDATE mp_mapeos SET activo=0, fecha_actualizacion=? WHERE plantilla_id=? AND activo=1", (now_iso(), plantilla_id))
        cur = conn.execute("""
            INSERT INTO mp_mapeos
            (plantilla_id, nombre, version, mapeo_json, validacion_json, activo,
             usuario_creador_id, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (
            plantilla_id, nombre or 'Mapeo principal', version or '1.0',
            json.dumps(mapping, ensure_ascii=False),
            json.dumps(validation, ensure_ascii=False),
            user.get('usuario_id'), now_iso(), now_iso(),
        ))
        mapeo_id = int(cur.lastrowid)
        row = conn.execute("SELECT id FROM plantillas_oficiales_versiones WHERE mp_plantilla_id=? ORDER BY id DESC LIMIT 1", (plantilla_id,)).fetchone()
        if row:
            version_id = int(row['id'])
            conn.execute("DELETE FROM plantillas_oficiales_mapeos WHERE version_id=?", (version_id,))
            for item in mapping or []:
                conn.execute("""
                    INSERT INTO plantillas_oficiales_mapeos
                    (version_id, campo, hoja, columna, col_index, fila_inicio, fila_fin, obligatorio, config_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    version_id, item.get('field') or item.get('campo'), item.get('sheet') or item.get('hoja'), item.get('col_letter') or item.get('columna'),
                    int(item.get('col') or item.get('col_index') or 0), int(item.get('data_start_row') or item.get('fila_inicio') or 0),
                    item.get('fila_fin'), 1 if item.get('obligatorio') else 0, json.dumps(item, ensure_ascii=False), now_iso(), now_iso()
                ))
            conn.execute("UPDATE plantillas_oficiales_versiones SET mapeo_json=?, updated_at=? WHERE id=?", (json.dumps(mapping, ensure_ascii=False), now_iso(), version_id))
        conn.commit()
        conn.close()
        self.log('GUARDAR_MAPEO', plantilla_id=plantilla_id, mapeo_id=mapeo_id, usuario_id=user.get('usuario_id'), fundacion_id=user.get('fundacion_id'), detalle={'validacion': validation})
        return mapeo_id

    def get_vigente(self, tipo_formato: str, fundacion_id: int) -> dict | None:
        conn = connect(self.database_path)
        row = conn.execute("SELECT * FROM plantillas_oficiales_versiones WHERE tipo_formato=? AND fundacion_id=? AND LOWER(estado)='vigente' ORDER BY updated_at DESC, id DESC LIMIT 1", (tipo_formato.upper(),fundacion_id)).fetchone()
        if not row:
            row = conn.execute("SELECT * FROM mp_plantillas WHERE tipo=? AND fundacion_id=? AND UPPER(estado) IN ('VIGENTE','ACTIVA') ORDER BY fecha_actualizacion DESC, id DESC LIMIT 1", (tipo_formato.upper(),fundacion_id)).fetchone()
            if row:
                item = row_to_dict(row)
                conn.close()
                return item
        conn.close()
        item = row_to_dict(row)
        return item

    def get_applicable(self, tipo_formato: str, mes: int, anio: int, fundacion_id: int) -> dict | None:
        """Obtiene la versión aplicable al primer día del periodo solicitado."""
        tipo = (tipo_formato or '').upper()
        report_date = f"{int(anio):04d}-{int(mes):02d}-01"
        conn = connect(self.database_path)
        row = conn.execute("""
            SELECT * FROM plantillas_oficiales_versiones
            WHERE tipo_formato=? AND fundacion_id=?
              AND LOWER(COALESCE(estado,'')) IN ('vigente','programado','historico','activa')
              AND (COALESCE(fecha_vigencia,'')='' OR substr(fecha_vigencia,1,10)<=?)
              AND (COALESCE(fecha_vigencia_fin,'')='' OR substr(fecha_vigencia_fin,1,10)>=?)
            ORDER BY CASE WHEN COALESCE(fecha_vigencia,'')='' THEN 1 ELSE 0 END,
                     substr(fecha_vigencia,1,10) DESC, updated_at DESC, id DESC
            LIMIT 1
        """, (tipo,fundacion_id,report_date,report_date)).fetchone()
        conn.close()
        return row_to_dict(row)

    def mark_version_vigente(self, version_id: int, user: dict) -> dict:
        conn = connect(self.database_path)
        fundacion_id=int(user.get('fundacion_id') or 1)
        row = conn.execute("SELECT * FROM plantillas_oficiales_versiones WHERE id=? AND fundacion_id=?", (version_id,fundacion_id)).fetchone()
        if not row:
            conn.close()
            raise ValueError('Versión de plantilla no encontrada')
        item = dict(row)
        tipo = item.get('tipo_formato')
        conn.execute("UPDATE plantillas_oficiales_versiones SET estado='historico', updated_at=? WHERE tipo_formato=? AND fundacion_id=? AND id<>?", (now_iso(), tipo,fundacion_id,version_id))
        conn.execute("UPDATE plantillas_oficiales_versiones SET estado='vigente', updated_at=? WHERE id=? AND fundacion_id=?", (now_iso(),version_id,fundacion_id))
        conn.execute("UPDATE mp_plantillas SET estado='HISTORICO', fecha_actualizacion=? WHERE tipo=? AND fundacion_id=?", (now_iso(),tipo,fundacion_id))
        if item.get('mp_plantilla_id'):
            conn.execute("UPDATE mp_plantillas SET estado='VIGENTE', fecha_actualizacion=? WHERE id=?", (now_iso(), item['mp_plantilla_id']))
        conn.execute("""
            INSERT INTO plantillas_oficiales_auditoria
            (accion, tipo_formato, version_id, mp_plantilla_id, usuario_id, fundacion_id, detalle_json, created_at)
            VALUES ('MARCAR_VIGENTE', ?, ?, ?, ?, ?, ?, ?)
        """, (tipo,version_id,item.get('mp_plantilla_id'),user.get('usuario_id'),fundacion_id,json.dumps({'version':item.get('version')},ensure_ascii=False),now_iso()))
        conn.commit()
        conn.close()
        self.log('MARCAR_VERSION_VIGENTE', plantilla_id=item.get('mp_plantilla_id'), usuario_id=user.get('usuario_id'), fundacion_id=user.get('fundacion_id'), detalle={'version_id': version_id, 'tipo': tipo})
        return {'ok': True, 'tipo_formato': tipo, 'version_id': version_id}

    def rollback(self, tipo_formato: str, user: dict) -> dict:
        conn = connect(self.database_path)
        tipo = tipo_formato.upper()
        fundacion_id=int(user.get('fundacion_id') or 1)
        row = conn.execute("""
            SELECT * FROM plantillas_oficiales_versiones
            WHERE tipo_formato=? AND fundacion_id=? AND LOWER(estado) IN ('historico','activa','vigente')
            ORDER BY CASE WHEN LOWER(estado)='historico' THEN 0 ELSE 1 END, updated_at DESC, id DESC LIMIT 1
        """, (tipo,fundacion_id)).fetchone()
        conn.close()
        if not row:
            raise ValueError('No hay versión anterior para restaurar')
        return self.mark_version_vigente(int(row['id']), user)

