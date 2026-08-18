from __future__ import annotations

import csv
import io
import json
import os
from modules.dbapi_compat import sqlite3
import zipfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .schema import DEFAULT_PLANS, SCHEMA_SQL, SCHEMA_VERSION
from .integrations import UCAIntegrationEngine
from .services import (
    COMPLETED_STATES,
    MODULE_LINKS,
    PHASES,
    ROUTE_CATALOG,
    completion_percentage,
    file_sha256,
    json_dump,
    normalize_text,
    now_iso,
    parse_json,
    route_catalog_hash,
    safe_state,
    semaphore,
    unit_key,
    valid_date,
)


class GestionIntegralRepository:
    def __init__(self, database_path: str, data_dir: str, output_folder: str):
        self.database_path = str(database_path)
        self.data_dir = Path(data_dir).resolve()
        self.output_folder = Path(output_folder).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.integration_engine = UCAIntegrationEngine(self.database_path, str(self.data_dir))

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path, timeout=60)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=60000")
        return conn

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
        if not GestionIntegralRepository._table_exists(conn, table):
            return set()
        return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    def init_schema(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA_SQL)
            self._seed_catalog(conn)
            self._seed_library(conn)
            self._seed_library_sources(conn)
            conn.execute(
                "INSERT INTO giu_schema_version(id, version, catalogo_hash, fecha_actualizacion) VALUES(1,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET version=excluded.version, catalogo_hash=excluded.catalogo_hash, fecha_actualizacion=excluded.fecha_actualizacion",
                (SCHEMA_VERSION, route_catalog_hash(), now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def _seed_catalog(self, conn: sqlite3.Connection) -> None:
        now = now_iso()
        for item in ROUTE_CATALOG:
            definition_hash = route_catalog_hash()[:16] + ":" + item["codigo"]
            conn.execute(
                """
                INSERT INTO giu_ruta_catalogo
                (codigo,fase,orden,titulo,descripcion,componente,obligatoria,requiere_evidencia,roles_json,evidencias_json,activo,hash_definicion,fecha_creacion,fecha_actualizacion)
                VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?)
                ON CONFLICT(codigo) DO UPDATE SET
                    fase=excluded.fase, orden=excluded.orden, titulo=excluded.titulo,
                    descripcion=excluded.descripcion, componente=excluded.componente,
                    obligatoria=excluded.obligatoria, requiere_evidencia=excluded.requiere_evidencia,
                    roles_json=excluded.roles_json, evidencias_json=excluded.evidencias_json,
                    activo=1, hash_definicion=excluded.hash_definicion,
                    fecha_actualizacion=excluded.fecha_actualizacion
                """,
                (
                    item["codigo"], item["fase"], item["orden"], item["titulo"], item["descripcion"],
                    item["componente"], int(item["obligatoria"]), int(item["requiere_evidencia"]),
                    json_dump(item["roles"]), json_dump(item["evidencias"]), definition_hash, now, now,
                ),
            )

    def _seed_library(self, conn: sqlite3.Connection) -> None:
        now = now_iso()
        seed = [
            ("MT3.PP", "Manual Técnico Modalidad Propia e Intercultural para la Atención a la Primera Infancia", "MANUAL_TECNICO", "Propia e Intercultural", "Transversal", "Documento rector para los componentes y la ruta operativa.", "MANUAL_CARGADO"),
            ("FORMATO_RAM", "Registro de Asistencia Mensual (RAM)", "FORMATO_OFICIAL", "Primera Infancia", "Administrativo y de Gestión", "Formato oficial de asistencia sujeto a control de versiones.", "REPOSITORIO_CONTROLADO"),
            ("FORMATO_RPP", "Ración Para Preparar (RPP)", "FORMATO_OFICIAL", "Primera Infancia", "Salud y Nutrición", "Formato oficial de raciones sujeto a minuta y periodo.", "REPOSITORIO_CONTROLADO"),
            ("FORMATO_BIENESTARINA", "Formato de Bienestarina", "FORMATO_OFICIAL", "Primera Infancia", "Salud y Nutrición", "Formato oficial para control de entregas de alimentos de alto valor nutricional.", "REPOSITORIO_CONTROLADO"),
        ]
        # Se inserta por fundación al inicializar una fundación, no aquí: este método
        # conserva la semilla en una tabla temporal de configuración mediante fundación 1.
        for fundacion_id in self._known_foundations(conn) or [1]:
            for code, name, doc_type, modality, component, description, source_type in seed:
                conn.execute(
                    """
                    INSERT INTO biblioteca_icbf_documentos
                    (fundacion_id,codigo,nombre,tipo_documento,modalidad,componente,descripcion,fuente_tipo,verificacion_automatica,activo,fecha_creacion,fecha_actualizacion)
                    VALUES (?,?,?,?,?,?,?,?,0,1,?,?)
                    ON CONFLICT(fundacion_id,codigo) DO UPDATE SET
                        nombre=excluded.nombre, tipo_documento=excluded.tipo_documento,
                        modalidad=excluded.modalidad, componente=excluded.componente,
                        descripcion=excluded.descripcion, fuente_tipo=excluded.fuente_tipo,
                        fecha_actualizacion=excluded.fecha_actualizacion
                    """,
                    (fundacion_id, code, name, doc_type, modality, component, description, source_type, now, now),
                )
                row = conn.execute(
                    "SELECT id FROM biblioteca_icbf_documentos WHERE fundacion_id=? AND codigo=?",
                    (fundacion_id, code),
                ).fetchone()
                if code == "MT3.PP" and row:
                    conn.execute(
                        """
                        INSERT INTO biblioteca_icbf_versiones
                        (fundacion_id,documento_id,version,fecha_documento,fecha_vigencia_desde,estado,fuente_url,notas_cambio,verificada,fecha_creacion,fecha_actualizacion)
                        VALUES (?,?,?,'2025-12-26','2025-12-26','VIGENTE',NULL,'Versión 2 registrada como referencia inicial.',1,?,?)
                        ON CONFLICT(fundacion_id,documento_id,version) DO NOTHING
                        """,
                        (fundacion_id, int(row["id"]), "2", now, now),
                    )

    def _seed_library_sources(self, conn: sqlite3.Connection) -> None:
        """Prepara fuentes controladas sin activar extracción remota por defecto."""
        now = now_iso()
        for fundacion_id in self._known_foundations(conn) or [1]:
            conn.execute(
                """
                INSERT INTO biblioteca_icbf_fuentes
                (fundacion_id,codigo,nombre,tipo_fuente,mecanismo,url_base,dominio_permitido,autorizada,habilitada,intervalo_horas,configuracion_json,fecha_creacion,fecha_actualizacion)
                VALUES(?,'ICBF_PORTAL_PUBLICO','Portal público del ICBF','REPOSITORIO_PUBLICO','MANUAL','https://www.icbf.gov.co/','icbf.gov.co',1,0,24,?, ?,?)
                ON CONFLICT(fundacion_id,codigo) DO UPDATE SET
                  nombre=excluded.nombre,tipo_fuente=excluded.tipo_fuente,dominio_permitido=excluded.dominio_permitido,fecha_actualizacion=excluded.fecha_actualizacion
                """,
                (fundacion_id, json_dump({"nota": "Fuente pública registrada. La verificación automática permanece deshabilitada hasta disponer de un catálogo/API oficial documentado."}), now, now),
            )

    def _known_foundations(self, conn: sqlite3.Connection) -> list[int]:
        if not self._table_exists(conn, "fundaciones"):
            return [1]
        return [int(row[0]) for row in conn.execute("SELECT id FROM fundaciones WHERE COALESCE(estado,'ACTIVO')<>'ELIMINADA'").fetchall()]

    def audit(self, fundacion_id: int, user: dict[str, Any], action: str, entity: str, entity_id: int | None, detail: dict[str, Any] | None = None) -> None:
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO giu_auditoria(fundacion_id,usuario_id,usuario,accion,entidad,entidad_id,detalle_json,fecha) VALUES(?,?,?,?,?,?,?,?)",
                (fundacion_id, user.get("id"), user.get("username") or user.get("email") or "sistema", action, entity, entity_id, json_dump(detail or {}), now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def list_units(self, fundacion_id: int, allowed_units: list[str] | None = None) -> list[dict[str, Any]]:
        """Obtiene las UCA/UDS disponibles sin asumir una versión única de Base Maestra."""
        allowed_keys = None if allowed_units is None else {unit_key(value) for value in allowed_units if value}
        conn = self.connect()
        units: dict[str, dict[str, Any]] = {}

        def expression(columns: set[str], column: str, alias: str | None = None, default: str = "NULL") -> str:
            target = alias or column
            return f'"{column}" AS "{target}"' if column in columns else f'{default} AS "{target}"'

        try:
            if self._table_exists(conn, "master_unidades"):
                cols = self._columns(conn, "master_unidades")
                if "nombre" in cols:
                    where = []
                    params: list[Any] = []
                    if "activo" in cols:
                        where.append("COALESCE(activo,1)=1")
                    if "fundacion_id" in cols:
                        where.append("fundacion_id=?")
                        params.append(fundacion_id)
                    select = [
                        expression(cols, "id", default="NULL"),
                        expression(cols, "nombre"),
                        expression(cols, "codigo_unidad"),
                        expression(cols, "coordinador"),
                        expression(cols, "total_ninos", default="0"),
                        expression(cols, "total_talento", default="0"),
                        expression(cols, "modalidad"),
                    ]
                    sql = f"SELECT {','.join(select)} FROM master_unidades"
                    if where:
                        sql += " WHERE " + " AND ".join(where)
                    sql += " ORDER BY nombre"
                    rows = conn.execute(sql, params).fetchall()
                    for row in rows:
                        key = unit_key(row["nombre"])
                        if not key or (allowed_keys is not None and key not in allowed_keys):
                            continue
                        units[key] = {
                            "id": row["id"], "nombre": row["nombre"], "codigo": row["codigo_unidad"],
                            "coordinador": row["coordinador"], "total_participantes": int(row["total_ninos"] or 0),
                            "total_talento": int(row["total_talento"] or 0), "modalidad": row["modalidad"],
                            "fuente": "master_unidades", "unidad_clave": key,
                        }

            if not units and self._table_exists(conn, "master_ninos"):
                cols = self._columns(conn, "master_ninos")
                unit_column = "unidad_servicio" if "unidad_servicio" in cols else ("unidad" if "unidad" in cols else None)
                if unit_column:
                    where = [f'COALESCE("{unit_column}", \'\') <> \'\'']
                    params = []
                    if "activo" in cols:
                        where.append("COALESCE(activo,1)=1")
                    if "fundacion_id" in cols:
                        where.append("fundacion_id=?")
                        params.append(fundacion_id)
                    code_expr = 'MAX("codigo_unidad")' if "codigo_unidad" in cols else "NULL"
                    coord_expr = 'MAX("coordinador")' if "coordinador" in cols else "NULL"
                    rows = conn.execute(
                        f'SELECT "{unit_column}" AS nombre, {code_expr} AS codigo, {coord_expr} AS coordinador, COUNT(*) AS total '
                        f'FROM master_ninos WHERE {" AND ".join(where)} GROUP BY "{unit_column}" ORDER BY "{unit_column}"',
                        params,
                    ).fetchall()
                    for row in rows:
                        key = unit_key(row["nombre"])
                        if not key or (allowed_keys is not None and key not in allowed_keys):
                            continue
                        units[key] = {
                            "id": None, "nombre": row["nombre"], "codigo": row["codigo"], "coordinador": row["coordinador"],
                            "total_participantes": int(row["total"] or 0), "total_talento": 0, "modalidad": None,
                            "fuente": "master_ninos", "unidad_clave": key,
                        }
        finally:
            conn.close()
        return sorted(units.values(), key=lambda item: normalize_text(item["nombre"]))

    def ensure_expediente(self, fundacion_id: int, unit: dict[str, Any], vigencia: str, contrato: str, user: dict[str, Any], servicio_modalidad: str | None = None) -> dict[str, Any]:
        vigencia = str(vigencia or date.today().year).strip()[:20]
        contrato = str(contrato or "").strip()[:150]
        now = now_iso()
        conn = self.connect()
        try:
            self._ensure_library_for_foundation(conn, fundacion_id)
            conn.execute(
                """
                INSERT INTO giu_expedientes_uca
                (fundacion_id,unidad_id,unidad_nombre,unidad_clave,codigo_unidad,contrato,vigencia,servicio_modalidad,fase_actual,estado,coordinador_nombre,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion)
                VALUES (?,?,?,?,?,?,?,?, 'PREPARATORIA','ACTIVO',?,?,?,?,?)
                ON CONFLICT(fundacion_id,unidad_clave,vigencia,contrato) DO UPDATE SET
                    unidad_id=COALESCE(excluded.unidad_id,giu_expedientes_uca.unidad_id),
                    unidad_nombre=excluded.unidad_nombre,
                    codigo_unidad=COALESCE(excluded.codigo_unidad,giu_expedientes_uca.codigo_unidad),
                    servicio_modalidad=COALESCE(excluded.servicio_modalidad,giu_expedientes_uca.servicio_modalidad),
                    coordinador_nombre=COALESCE(excluded.coordinador_nombre,giu_expedientes_uca.coordinador_nombre),
                    actualizado_por=excluded.actualizado_por, fecha_actualizacion=excluded.fecha_actualizacion
                """,
                (
                    fundacion_id, unit.get("id"), unit.get("nombre"), unit.get("unidad_clave") or unit_key(unit.get("nombre")),
                    unit.get("codigo"), contrato, vigencia, servicio_modalidad or unit.get("modalidad"),
                    unit.get("coordinador"), user.get("id"), user.get("id"), now, now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM giu_expedientes_uca WHERE fundacion_id=? AND unidad_clave=? AND vigencia=? AND contrato=?",
                (fundacion_id, unit.get("unidad_clave") or unit_key(unit.get("nombre")), vigencia, contrato),
            ).fetchone()
            expediente_id = int(row["id"])
            self._sync_route_instances(conn, fundacion_id, expediente_id, user.get("id"))
            self._sync_default_plans(conn, fundacion_id, expediente_id, user.get("id"))
            conn.commit()
        finally:
            conn.close()
        self.recalculate_expediente(expediente_id, fundacion_id)
        return self.get_expediente(expediente_id, fundacion_id) or {}

    def _ensure_library_for_foundation(self, conn: sqlite3.Connection, fundacion_id: int) -> None:
        now = now_iso()
        seed = [
            ("MT3.PP", "Manual Técnico Modalidad Propia e Intercultural para la Atención a la Primera Infancia", "MANUAL_TECNICO", "Propia e Intercultural", "Transversal", "Documento rector para componentes y ruta operativa.", "MANUAL_CARGADO"),
            ("FORMATO_RAM", "Registro de Asistencia Mensual (RAM)", "FORMATO_OFICIAL", "Primera Infancia", "Administrativo y de Gestión", "Control de versión del formato RAM.", "REPOSITORIO_CONTROLADO"),
            ("FORMATO_RPP", "Ración Para Preparar (RPP)", "FORMATO_OFICIAL", "Primera Infancia", "Salud y Nutrición", "Control de versión del formato RPP.", "REPOSITORIO_CONTROLADO"),
            ("FORMATO_BIENESTARINA", "Formato de Bienestarina", "FORMATO_OFICIAL", "Primera Infancia", "Salud y Nutrición", "Control de versión del formato de Bienestarina.", "REPOSITORIO_CONTROLADO"),
        ]
        for code, name, doc_type, modality, component, description, source_type in seed:
            conn.execute(
                """
                INSERT INTO biblioteca_icbf_documentos
                (fundacion_id,codigo,nombre,tipo_documento,modalidad,componente,descripcion,fuente_tipo,verificacion_automatica,activo,fecha_creacion,fecha_actualizacion)
                VALUES (?,?,?,?,?,?,?,?,0,1,?,?)
                ON CONFLICT(fundacion_id,codigo) DO NOTHING
                """,
                (fundacion_id, code, name, doc_type, modality, component, description, source_type, now, now),
            )

    def _sync_route_instances(self, conn: sqlite3.Connection, fundacion_id: int, expediente_id: int, user_id: int | None) -> None:
        now = now_iso()
        rows = conn.execute("SELECT id,codigo FROM giu_ruta_catalogo WHERE activo=1 ORDER BY orden").fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO giu_ruta_instancias
                (fundacion_id,expediente_id,catalogo_id,actividad_codigo,estado,porcentaje,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion)
                VALUES (?,?,?,?, 'PENDIENTE',0,?,?,?,?)
                ON CONFLICT(expediente_id,actividad_codigo) DO UPDATE SET catalogo_id=excluded.catalogo_id
                """,
                (fundacion_id, expediente_id, int(row["id"]), row["codigo"], user_id, user_id, now, now),
            )

    def _sync_default_plans(self, conn: sqlite3.Connection, fundacion_id: int, expediente_id: int, user_id: int | None) -> None:
        now = now_iso()
        for code, name in DEFAULT_PLANS:
            conn.execute(
                """
                INSERT INTO giu_planes_uca
                (fundacion_id,expediente_id,codigo,nombre,estado,progreso,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion)
                VALUES (?,?,?,?, 'BORRADOR',0,?,?,?,?)
                ON CONFLICT(expediente_id,codigo) DO UPDATE SET nombre=excluded.nombre, fecha_actualizacion=excluded.fecha_actualizacion
                """,
                (fundacion_id, expediente_id, code, name, user_id, user_id, now, now),
            )

    def sync_all_units(self, fundacion_id: int, vigencia: str, contrato: str, user: dict[str, Any], allowed_units: list[str] | None = None) -> list[dict[str, Any]]:
        result = []
        for unit in self.list_units(fundacion_id, allowed_units):
            result.append(self.ensure_expediente(fundacion_id, unit, vigencia, contrato, user))
        return result

    def list_expedientes(self, fundacion_id: int, vigencia: str | None = None, allowed_units: list[str] | None = None) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            where = ["fundacion_id=?", "estado<>'ELIMINADO'"]
            params: list[Any] = [fundacion_id]
            if vigencia:
                where.append("vigencia=?")
                params.append(str(vigencia))
            rows = conn.execute(
                f"SELECT * FROM giu_expedientes_uca WHERE {' AND '.join(where)} ORDER BY unidad_nombre, vigencia DESC, contrato",
                params,
            ).fetchall()
        finally:
            conn.close()
        allowed_keys = None if allowed_units is None else {unit_key(value) for value in allowed_units if value}
        result = []
        for row in rows:
            data = dict(row)
            if allowed_keys is not None and data.get("unidad_clave") not in allowed_keys:
                continue
            # El tablero usa únicamente el avance persistido de la Ruta Operativa.
            # La vista integrada completa se calcula bajo demanda al abrir una UCA,
            # evitando ejecutar consultas transversales por cada tarjeta del listado.
            result.append(data)
        return result

    def get_expediente(self, expediente_id: int, fundacion_id: int) -> dict[str, Any] | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM giu_expedientes_uca WHERE id=? AND fundacion_id=? AND estado<>'ELIMINADO'", (expediente_id, fundacion_id)).fetchone()
            if not row:
                return None
            data = dict(row)
            route_rows = conn.execute(
                """
                SELECT i.*, c.fase,c.orden,c.titulo,c.descripcion,c.componente,c.obligatoria,c.requiere_evidencia,c.roles_json,c.evidencias_json,
                       (SELECT COUNT(*) FROM giu_ruta_evidencias e WHERE e.instancia_id=i.id AND e.fundacion_id=i.fundacion_id AND e.activo=1) AS evidencias_total
                FROM giu_ruta_instancias i JOIN giu_ruta_catalogo c ON c.id=i.catalogo_id
                WHERE i.expediente_id=? AND i.fundacion_id=? AND c.activo=1
                ORDER BY c.orden
                """,
                (expediente_id, fundacion_id),
            ).fetchall()
            plans = conn.execute("SELECT * FROM giu_planes_uca WHERE expediente_id=? AND fundacion_id=? ORDER BY codigo", (expediente_id, fundacion_id)).fetchall()
        finally:
            conn.close()
        route = []
        by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in route_rows:
            d = dict(item)
            d["roles"] = parse_json(d.pop("roles_json", None), [])
            d["evidencias_requeridas"] = parse_json(d.pop("evidencias_json", None), [])
            route.append(d)
            by_phase[d["fase"]].append(d)
        phase_summaries = []
        for code, title, order in PHASES:
            items = by_phase.get(code, [])
            phase_summaries.append({
                "codigo": code,
                "titulo": title,
                "orden": order,
                "total": len(items),
                "obligatorias": sum(1 for item in items if int(item.get("obligatoria") or 0) == 1),
                "completas": sum(1 for item in items if safe_state(item.get("estado")) in COMPLETED_STATES),
                "porcentaje": completion_percentage(items),
            })
        data["ruta"] = route
        data["fases"] = phase_summaries
        data["planes"] = [dict(row) for row in plans]
        data["integracion"] = self.integration_summary(fundacion_id, data["unidad_nombre"], data.get("codigo_unidad"), expediente_id)
        data["enlaces_modulos"] = MODULE_LINKS
        data["biblioteca"] = self.list_library_documents(fundacion_id, include_versions=True)
        return data

    def integrated_view(self, fundacion_id: int, expediente_id: int) -> dict[str, Any]:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT * FROM giu_expedientes_uca WHERE id=? AND fundacion_id=? AND estado<>'ELIMINADO'",
                (expediente_id, fundacion_id),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            raise LookupError("Expediente operativo no encontrado.")
        expediente = dict(row)
        view = self.integration_engine.build_view(expediente)
        self.sync_document_links(fundacion_id, expediente_id, view.get("documentos") or [])
        view["documentos"] = self.list_document_links(fundacion_id, expediente_id)
        return view

    def integration_summary(self, fundacion_id: int, unit_name: str, unit_code: str | None = None, expediente_id: int | None = None) -> dict[str, Any]:
        if expediente_id is not None:
            view = self.integrated_view(fundacion_id, expediente_id)
        else:
            view = self.integration_engine.build_view({
                "id": None,
                "fundacion_id": fundacion_id,
                "unidad_nombre": unit_name,
                "codigo_unidad": unit_code,
                "vigencia": str(date.today().year),
                "contrato": "",
                "servicio_modalidad": None,
                "fase_actual": "PREPARATORIA",
            })
        return {
            item["codigo"]: dict(item.get("metricas") or {})
            for item in view.get("componentes") or []
        }

    def sync_document_links(self, fundacion_id: int, expediente_id: int, documents: list[dict[str, Any]]) -> int:
        now = now_iso()
        conn = self.connect()
        try:
            conn.execute(
                "UPDATE giu_vinculos_documentales SET activo=0,fecha_sincronizacion=? "
                "WHERE fundacion_id=? AND expediente_id=? AND origen='AUTOMATICO'",
                (now, fundacion_id, expediente_id),
            )
            count = 0
            for document in documents:
                table = str(document.get("source_table") or "").strip()
                source_id = int(document.get("source_id") or 0)
                title = str(document.get("titulo") or "").strip()
                if not table or source_id <= 0 or not title:
                    continue
                metadata = {
                    key: value for key, value in document.items()
                    if key not in {"file_path", "sha256"}
                }
                conn.execute(
                    """
                    INSERT INTO giu_vinculos_documentales
                    (fundacion_id,expediente_id,source_module,source_table,source_id,categoria,titulo,estado,fecha_documento,file_name,file_path,mime_type,sha256,version,metadata_json,origen,activo,fecha_sincronizacion)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'AUTOMATICO',1,?)
                    ON CONFLICT(fundacion_id,expediente_id,source_table,source_id) DO UPDATE SET
                        source_module=excluded.source_module,categoria=excluded.categoria,titulo=excluded.titulo,
                        estado=excluded.estado,fecha_documento=excluded.fecha_documento,file_name=excluded.file_name,
                        file_path=excluded.file_path,mime_type=excluded.mime_type,sha256=COALESCE(excluded.sha256,giu_vinculos_documentales.sha256),
                        version=excluded.version,metadata_json=excluded.metadata_json,activo=1,fecha_sincronizacion=excluded.fecha_sincronizacion
                    """,
                    (
                        fundacion_id, expediente_id, document.get("source_module") or "desconocido", table, source_id,
                        document.get("categoria"), title, document.get("estado"), document.get("fecha_documento"),
                        document.get("file_name"), document.get("file_path"), document.get("mime_type"),
                        document.get("sha256"), document.get("version"), json_dump(metadata), now,
                    ),
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def list_document_links(self, fundacion_id: int, expediente_id: int) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM giu_vinculos_documentales WHERE fundacion_id=? AND expediente_id=? AND activo=1 "
                "ORDER BY COALESCE(fecha_documento,'') DESC,categoria,titulo",
                (fundacion_id, expediente_id),
            ).fetchall()
        finally:
            conn.close()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = parse_json(item.pop("metadata_json", None), {})
            path = Path(str(item.get("file_path") or ""))
            downloadable = False
            if item.get("file_path"):
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(self.data_dir)
                    downloadable = resolved.is_file()
                except (OSError, ValueError):
                    downloadable = False
            item["descargable"] = downloadable
            item.pop("file_path", None)
            result.append(item)
        return result

    def linked_document_path(self, fundacion_id: int, expediente_id: int, link_id: int) -> tuple[str, str] | None:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT file_path,file_name FROM giu_vinculos_documentales "
                "WHERE id=? AND fundacion_id=? AND expediente_id=? AND activo=1",
                (link_id, fundacion_id, expediente_id),
            ).fetchone()
        finally:
            conn.close()
        if not row or not row["file_path"]:
            return None
        path = Path(str(row["file_path"])).resolve()
        try:
            path.relative_to(self.data_dir)
        except ValueError:
            return None
        if not path.is_file():
            return None
        return str(path), str(row["file_name"] or path.name)

    def supervision_preview(self, fundacion_id: int, expediente_id: int) -> dict[str, Any]:
        view = self.integrated_view(fundacion_id, expediente_id)
        return {
            "expediente_id": expediente_id,
            "unidad": view.get("unidad"),
            "preparacion": view.get("preparacion_supervision"),
            "indicadores": view.get("indicadores"),
            "alertas_total": len(view.get("alertas") or []),
            "documentos_total": len(view.get("documentos") or []),
            "cronograma_total": len(view.get("cronograma") or []),
            "generado_en": view.get("generado_en"),
        }

    def recalculate_expediente(self, expediente_id: int, fundacion_id: int) -> dict[str, Any] | None:
        conn = self.connect()
        try:
            rows = conn.execute(
                """
                SELECT i.estado,i.fecha_limite,c.obligatoria,c.fase
                FROM giu_ruta_instancias i JOIN giu_ruta_catalogo c ON c.id=i.catalogo_id
                WHERE i.expediente_id=? AND i.fundacion_id=? AND c.activo=1
                """,
                (expediente_id, fundacion_id),
            ).fetchall()
            items = [dict(row) for row in rows]
            progress = completion_percentage(items)
            today = date.today().isoformat()
            overdue = sum(1 for item in items if item.get("fecha_limite") and item["fecha_limite"] < today and safe_state(item.get("estado")) not in COMPLETED_STATES)
            blocked = sum(1 for item in items if safe_state(item.get("estado")) in {"DEVUELTA", "PENDIENTE_EVIDENCIA"})
            phase_order = [code for code, _title, _order in PHASES if code != "TRANSVERSAL"]
            phase_actual = "PREPARATORIA"
            for phase in phase_order:
                phase_rows = [item for item in items if item.get("fase") == phase and int(item.get("obligatoria") or 0) == 1]
                if phase_rows and not all(safe_state(item.get("estado")) in COMPLETED_STATES for item in phase_rows):
                    phase_actual = phase
                    break
            else:
                phase_actual = "CIERRE"
            light = semaphore(progress, overdue, blocked)
            conn.execute(
                "UPDATE giu_expedientes_uca SET porcentaje_global=?,semaforo=?,fase_actual=?,fecha_actualizacion=? WHERE id=? AND fundacion_id=?",
                (progress, light, phase_actual, now_iso(), expediente_id, fundacion_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_expediente(expediente_id, fundacion_id)

    def update_route_instance(self, fundacion_id: int, expediente_id: int, instance_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        conn = self.connect()
        try:
            row = conn.execute(
                """
                SELECT i.*,c.obligatoria,c.requiere_evidencia,c.titulo,c.fase
                FROM giu_ruta_instancias i JOIN giu_ruta_catalogo c ON c.id=i.catalogo_id
                WHERE i.id=? AND i.expediente_id=? AND i.fundacion_id=?
                """,
                (instance_id, expediente_id, fundacion_id),
            ).fetchone()
            if not row:
                raise LookupError("Actividad de ruta no encontrada.")
            state = safe_state(payload.get("estado") or row["estado"])
            evidence_count = int(conn.execute(
                "SELECT COUNT(*) AS total FROM giu_ruta_evidencias WHERE instancia_id=? AND fundacion_id=? AND activo=1",
                (instance_id, fundacion_id),
            ).fetchone()["total"] or 0)
            if state in {"APROBADA", "CERRADA"} and int(row["requiere_evidencia"] or 0) == 1 and evidence_count == 0:
                raise ValueError("Esta actividad exige al menos una evidencia antes de aprobarla o cerrarla.")
            justification = str(payload.get("justificacion_no_aplica") or row["justificacion_no_aplica"] or "").strip()
            if state == "NO_APLICA" and len(justification) < 10:
                raise ValueError("Para marcar No aplica debes registrar una justificación de al menos 10 caracteres.")
            start_date = valid_date(payload.get("fecha_inicio")) or row["fecha_inicio"]
            due_date = valid_date(payload.get("fecha_limite")) or row["fecha_limite"]
            finish_date = valid_date(payload.get("fecha_finalizacion")) or row["fecha_finalizacion"]
            if state in COMPLETED_STATES and not finish_date:
                finish_date = date.today().isoformat()
            progress = float(payload.get("porcentaje") if payload.get("porcentaje") is not None else row["porcentaje"] or 0)
            if state in COMPLETED_STATES:
                progress = 100.0
            progress = max(0.0, min(100.0, progress))
            conn.execute(
                """
                UPDATE giu_ruta_instancias SET estado=?,responsable_id=?,responsable_nombre=?,fecha_inicio=?,fecha_limite=?,fecha_finalizacion=?,porcentaje=?,observaciones=?,justificacion_no_aplica=?,revisado_por=?,aprobado_por=?,actualizado_por=?,fecha_actualizacion=?
                WHERE id=? AND expediente_id=? AND fundacion_id=?
                """,
                (
                    state,
                    payload.get("responsable_id") if payload.get("responsable_id") is not None else row["responsable_id"],
                    str(payload.get("responsable_nombre") or row["responsable_nombre"] or "").strip() or None,
                    start_date, due_date, finish_date, progress,
                    str(payload.get("observaciones") if payload.get("observaciones") is not None else row["observaciones"] or "").strip() or None,
                    justification or None,
                    user.get("id") if state in {"PENDIENTE_REVISION", "DEVUELTA", "APROBADA", "CERRADA"} else row["revisado_por"],
                    user.get("id") if state in {"APROBADA", "CERRADA"} else row["aprobado_por"],
                    user.get("id"), now_iso(), instance_id, expediente_id, fundacion_id,
                ),
            )
            self._sync_calendar_entregable(conn, fundacion_id, expediente_id, instance_id, user)
            conn.commit()
            updated = conn.execute(
                """
                SELECT i.*,c.fase,c.orden,c.titulo,c.descripcion,c.componente,c.obligatoria,c.requiere_evidencia,
                       (SELECT COUNT(*) FROM giu_ruta_evidencias e WHERE e.instancia_id=i.id AND e.fundacion_id=i.fundacion_id AND e.activo=1) AS evidencias_total
                FROM giu_ruta_instancias i JOIN giu_ruta_catalogo c ON c.id=i.catalogo_id WHERE i.id=?
                """,
                (instance_id,),
            ).fetchone()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "ACTUALIZAR_RUTA", "giu_ruta_instancias", instance_id, {"estado": state, "expediente_id": expediente_id})
        self.recalculate_expediente(expediente_id, fundacion_id)
        return dict(updated)

    def _sync_calendar_entregable(self, conn: sqlite3.Connection, fundacion_id: int, expediente_id: int, instance_id: int, user: dict[str, Any]) -> None:
        if not self._table_exists(conn, "calendario_entregables"):
            return
        row = conn.execute(
            """
            SELECT i.*,c.fase,c.titulo,c.componente,e.unidad_nombre,e.contrato,e.vigencia
            FROM giu_ruta_instancias i
            JOIN giu_ruta_catalogo c ON c.id=i.catalogo_id
            JOIN giu_expedientes_uca e ON e.id=i.expediente_id
            WHERE i.id=? AND i.fundacion_id=?
            """,
            (instance_id, fundacion_id),
        ).fetchone()
        if not row or not row["fecha_limite"]:
            return
        cols = self._columns(conn, "calendario_entregables")
        key = f"GIU:{fundacion_id}:{expediente_id}:{row['actividad_codigo']}"
        values = {
            "titulo": row["titulo"],
            "descripcion": f"Ruta operativa · {row['componente']} · {row['contrato'] or row['vigencia']}",
            "fecha_inicio": row["fecha_inicio"] or row["fecha_limite"],
            "fecha_limite": row["fecha_limite"],
            "modulo": "Expediente Operativo UCA",
            "tipo_formato": "Ruta operativa",
            "responsable_id": row["responsable_id"],
            "responsable_nombre": row["responsable_nombre"],
            "unidad": row["unidad_nombre"],
            "estado": str(row["estado"] or "pendiente").lower(),
            "prioridad": "Alta" if str(row["fase"]) in {"PREPARATORIA", "CIERRE"} else "Media",
            "requiere_evidencia": 1,
            "observaciones": row["observaciones"],
            "creado_por": user.get("username") or user.get("email") or "sistema",
            "fecha_creacion": now_iso(),
            "actualizado_en": now_iso(),
            "fundacion_id": fundacion_id,
            "usuario_creador_id": user.get("id"),
            "clave_unica": key,
            "origen": "gestion_integral_uca",
        }
        available = [column for column in values if column in cols]
        if "clave_unica" not in cols:
            return
        existing = conn.execute("SELECT id FROM calendario_entregables WHERE fundacion_id=? AND clave_unica=?", (fundacion_id, key)).fetchone() if "fundacion_id" in cols else conn.execute("SELECT id FROM calendario_entregables WHERE clave_unica=?", (key,)).fetchone()
        if existing:
            mutable = [column for column in available if column not in {"fundacion_id", "usuario_creador_id", "clave_unica", "fecha_creacion"}]
            conn.execute(
                f"UPDATE calendario_entregables SET {','.join(column+'=?' for column in mutable)} WHERE id=?",
                [values[column] for column in mutable] + [existing["id"]],
            )
        else:
            conn.execute(
                f"INSERT INTO calendario_entregables({','.join(available)}) VALUES({','.join('?' for _ in available)})",
                [values[column] for column in available],
            )

    def add_evidence(self, fundacion_id: int, expediente_id: int, instance_id: int, file_meta: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        conn = self.connect()
        try:
            instance = conn.execute(
                "SELECT id FROM giu_ruta_instancias WHERE id=? AND expediente_id=? AND fundacion_id=?",
                (instance_id, expediente_id, fundacion_id),
            ).fetchone()
            if not instance:
                raise LookupError("Actividad de ruta no encontrada.")
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS version FROM giu_ruta_evidencias WHERE instancia_id=? AND fundacion_id=?",
                (instance_id, fundacion_id),
            ).fetchone()["version"] or 1)
            source_path = Path(str(file_meta.get("ruta_archivo") or "")).resolve()
            if not source_path.is_file() or source_path.stat().st_size <= 0:
                raise ValueError("La evidencia no existe o está vacía.")
            file_meta = dict(file_meta)
            file_meta["tamano_bytes"] = source_path.stat().st_size
            file_meta["sha256"] = file_sha256(str(source_path))
            file_meta["ruta_archivo"] = str(source_path)
            conn.execute(
                """
                INSERT INTO giu_ruta_evidencias
                (fundacion_id,expediente_id,instancia_id,nombre_original,nombre_guardado,ruta_archivo,mime_type,tamano_bytes,sha256,version,activo,observaciones,cargado_por,fecha_carga)
                VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?)
                """,
                (
                    fundacion_id, expediente_id, instance_id, file_meta["nombre_original"], file_meta["nombre_guardado"],
                    file_meta["ruta_archivo"], file_meta.get("mime_type"), file_meta.get("tamano_bytes", 0),
                    file_meta["sha256"], version, file_meta.get("observaciones"), user.get("id"), now_iso(),
                ),
            )
            evidence_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                "UPDATE giu_ruta_instancias SET estado=CASE WHEN estado='PENDIENTE' THEN 'EN_PROCESO' ELSE estado END, actualizado_por=?,fecha_actualizacion=? WHERE id=?",
                (user.get("id"), now_iso(), instance_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM giu_ruta_evidencias WHERE id=?", (evidence_id,)).fetchone()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "CARGAR_EVIDENCIA_RUTA", "giu_ruta_evidencias", evidence_id, {"expediente_id": expediente_id, "instancia_id": instance_id, "sha256": file_meta["sha256"]})
        return dict(row)

    def list_evidence(self, fundacion_id: int, instance_id: int) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT id,nombre_original,nombre_guardado,mime_type,tamano_bytes,sha256,version,observaciones,cargado_por,fecha_carga FROM giu_ruta_evidencias WHERE fundacion_id=? AND instancia_id=? AND activo=1 ORDER BY version DESC,id DESC",
                (fundacion_id, instance_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def evidence_path(self, fundacion_id: int, evidence_id: int) -> tuple[str, str] | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT ruta_archivo,nombre_original FROM giu_ruta_evidencias WHERE id=? AND fundacion_id=? AND activo=1", (evidence_id, fundacion_id)).fetchone()
            if not row:
                return None
            path = str(row["ruta_archivo"])
            return (path, str(row["nombre_original"])) if os.path.isfile(path) else None
        finally:
            conn.close()

    def update_plan(self, fundacion_id: int, expediente_id: int, plan_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM giu_planes_uca WHERE id=? AND expediente_id=? AND fundacion_id=?", (plan_id, expediente_id, fundacion_id)).fetchone()
            if not row:
                raise LookupError("Plan no encontrado.")
            data = dict(row)
            state = normalize_text(payload.get("estado") or data.get("estado") or "BORRADOR").replace(" ", "_")
            if state not in {"BORRADOR", "EN_EJECUCION", "PENDIENTE_REVISION", "APROBADO", "CERRADO"}:
                state = "BORRADOR"
            progress = max(0.0, min(100.0, float(payload.get("progreso") if payload.get("progreso") is not None else data.get("progreso") or 0)))
            if state in {"APROBADO", "CERRADO"}:
                progress = 100.0
            conn.execute(
                """
                UPDATE giu_planes_uca SET responsable_id=?,responsable_nombre=?,estado=?,fecha_inicio=?,fecha_fin=?,progreso=?,objetivos_json=?,actividades_json=?,indicadores_json=?,observaciones=?,actualizado_por=?,fecha_actualizacion=?
                WHERE id=? AND expediente_id=? AND fundacion_id=?
                """,
                (
                    payload.get("responsable_id") if payload.get("responsable_id") is not None else data.get("responsable_id"),
                    payload.get("responsable_nombre") if payload.get("responsable_nombre") is not None else data.get("responsable_nombre"),
                    state, valid_date(payload.get("fecha_inicio")) or data.get("fecha_inicio"), valid_date(payload.get("fecha_fin")) or data.get("fecha_fin"), progress,
                    json_dump(payload.get("objetivos") if payload.get("objetivos") is not None else parse_json(data.get("objetivos_json"), [])),
                    json_dump(payload.get("actividades") if payload.get("actividades") is not None else parse_json(data.get("actividades_json"), [])),
                    json_dump(payload.get("indicadores") if payload.get("indicadores") is not None else parse_json(data.get("indicadores_json"), [])),
                    payload.get("observaciones") if payload.get("observaciones") is not None else data.get("observaciones"),
                    user.get("id"), now_iso(), plan_id, expediente_id, fundacion_id,
                ),
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM giu_planes_uca WHERE id=?", (plan_id,)).fetchone()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "ACTUALIZAR_PLAN_UCA", "giu_planes_uca", plan_id, {"expediente_id": expediente_id, "estado": state})
        return dict(updated)

    def list_library_documents(self, fundacion_id: int, include_versions: bool = False) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            self._ensure_library_for_foundation(conn, fundacion_id)
            conn.commit()
            docs = conn.execute("SELECT * FROM biblioteca_icbf_documentos WHERE fundacion_id=? AND activo=1 ORDER BY componente,nombre", (fundacion_id,)).fetchall()
            result = []
            for doc in docs:
                data = dict(doc)
                versions = conn.execute(
                    "SELECT * FROM biblioteca_icbf_versiones WHERE fundacion_id=? AND documento_id=? ORDER BY CASE estado WHEN 'VIGENTE' THEN 0 WHEN 'APROBADA' THEN 1 ELSE 2 END,fecha_documento DESC,id DESC",
                    (fundacion_id, doc["id"]),
                ).fetchall()
                data["version_vigente"] = next((dict(row) for row in versions if row["estado"] == "VIGENTE"), None)
                data["versiones_total"] = len(versions)
                if include_versions:
                    data["versiones"] = [dict(row) for row in versions]
                result.append(data)
            return result
        finally:
            conn.close()

    def list_library_relations(self, fundacion_id: int, document_id: int) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM biblioteca_icbf_relaciones WHERE fundacion_id=? AND documento_id=? ORDER BY modulo,tipo_relacion,id",
                (fundacion_id, document_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def set_library_relations(self, fundacion_id: int, document_id: int, relations: list[dict[str, Any]], user: dict[str, Any]) -> list[dict[str, Any]]:
        allowed_modules = {item["seccion"] for item in MODULE_LINKS.values()} | {"expediente-operativo-uca", "ruta-operativa-uca", "biblioteca-icbf", "motor-gestion-proyecto"}
        conn = self.connect()
        try:
            doc = conn.execute("SELECT id FROM biblioteca_icbf_documentos WHERE id=? AND fundacion_id=? AND activo=1", (document_id, fundacion_id)).fetchone()
            if not doc:
                raise LookupError("Documento de biblioteca no encontrado.")
            conn.execute("DELETE FROM biblioteca_icbf_relaciones WHERE fundacion_id=? AND documento_id=?", (fundacion_id, document_id))
            now = now_iso()
            for relation in relations or []:
                module = str(relation.get("modulo") or "").strip()
                if module not in allowed_modules:
                    continue
                relation_type = normalize_text(relation.get("tipo_relacion") or "REFERENCIA").replace(" ", "_")[:50]
                version_id = int(relation.get("version_id") or 0) or None
                if version_id:
                    version = conn.execute("SELECT id FROM biblioteca_icbf_versiones WHERE id=? AND fundacion_id=? AND documento_id=?", (version_id, fundacion_id, document_id)).fetchone()
                    if not version:
                        version_id = None
                conn.execute(
                    "INSERT OR IGNORE INTO biblioteca_icbf_relaciones(fundacion_id,documento_id,version_id,modulo,tipo_relacion,obligatorio,observaciones,creado_por,fecha_creacion) VALUES(?,?,?,?,?,?,?,?,?)",
                    (fundacion_id, document_id, version_id, module, relation_type, int(bool(relation.get("obligatorio"))), str(relation.get("observaciones") or "")[:1000] or None, user.get("id"), now),
                )
            conn.commit()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "ACTUALIZAR_RELACIONES_BIBLIOTECA", "biblioteca_icbf_documentos", document_id, {"relaciones": len(relations or [])})
        return self.list_library_relations(fundacion_id, document_id)

    def create_library_document(self, fundacion_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        code = normalize_text(payload.get("codigo")).replace(" ", "_")[:80]
        name = str(payload.get("nombre") or "").strip()
        if not code or not name:
            raise ValueError("Código y nombre son obligatorios.")
        now = now_iso()
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO biblioteca_icbf_documentos
                (fundacion_id,codigo,nombre,tipo_documento,modalidad,componente,descripcion,fuente_tipo,fuente_url,verificacion_automatica,activo,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion)
                VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)
                ON CONFLICT(fundacion_id,codigo) DO UPDATE SET
                    nombre=excluded.nombre,tipo_documento=excluded.tipo_documento,modalidad=excluded.modalidad,
                    componente=excluded.componente,descripcion=excluded.descripcion,fuente_tipo=excluded.fuente_tipo,
                    fuente_url=excluded.fuente_url,verificacion_automatica=excluded.verificacion_automatica,
                    actualizado_por=excluded.actualizado_por,fecha_actualizacion=excluded.fecha_actualizacion
                """,
                (
                    fundacion_id, code, name, str(payload.get("tipo_documento") or "DOCUMENTO_TECNICO")[:50],
                    str(payload.get("modalidad") or "")[:150] or None, str(payload.get("componente") or "")[:150] or None,
                    str(payload.get("descripcion") or "")[:2000] or None, str(payload.get("fuente_tipo") or "MANUAL")[:50],
                    str(payload.get("fuente_url") or "")[:1000] or None, int(bool(payload.get("verificacion_automatica"))),
                    user.get("id"), user.get("id"), now, now,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM biblioteca_icbf_documentos WHERE fundacion_id=? AND codigo=?", (fundacion_id, code)).fetchone()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "GUARDAR_DOCUMENTO_BIBLIOTECA", "biblioteca_icbf_documentos", row["id"], {"codigo": code})
        self.library_history_event(fundacion_id, user, "GUARDAR_DOCUMENTO", document_id=int(row["id"]), detail={"codigo": code})
        self.apply_suggested_library_relations(fundacion_id, int(row["id"]), user)
        return dict(row)

    def add_library_version(self, fundacion_id: int, document_id: int, payload: dict[str, Any], file_meta: dict[str, Any] | None, user: dict[str, Any]) -> dict[str, Any]:
        version = str(payload.get("version") or "").strip()[:80]
        if not version:
            raise ValueError("La versión es obligatoria.")
        now = now_iso()
        conn = self.connect()
        try:
            doc = conn.execute("SELECT * FROM biblioteca_icbf_documentos WHERE id=? AND fundacion_id=? AND activo=1", (document_id, fundacion_id)).fetchone()
            if not doc:
                raise LookupError("Documento de biblioteca no encontrado.")
            state = normalize_text(payload.get("estado") or "BORRADOR").replace(" ", "_")
            if state not in {"BORRADOR", "APROBADA", "VIGENTE", "HISTORICA", "RETIRADA"}:
                state = "BORRADOR"
            if state == "VIGENTE":
                conn.execute("UPDATE biblioteca_icbf_versiones SET estado='HISTORICA',fecha_actualizacion=? WHERE fundacion_id=? AND documento_id=? AND estado='VIGENTE'", (now, fundacion_id, document_id))
            if file_meta:
                source_path = Path(str(file_meta.get("ruta_archivo") or "")).resolve()
                if not source_path.is_file() or source_path.stat().st_size <= 0:
                    raise ValueError("El archivo de la versión no existe o está vacío.")
                file_meta = dict(file_meta)
                file_meta["ruta_archivo"] = str(source_path)
                file_meta["tamano_bytes"] = source_path.stat().st_size
                file_meta["sha256"] = file_sha256(str(source_path))
            values = {
                "nombre_original": file_meta.get("nombre_original") if file_meta else None,
                "nombre_guardado": file_meta.get("nombre_guardado") if file_meta else None,
                "ruta_archivo": file_meta.get("ruta_archivo") if file_meta else None,
                "mime_type": file_meta.get("mime_type") if file_meta else None,
                "tamano_bytes": file_meta.get("tamano_bytes", 0) if file_meta else 0,
                "sha256": file_meta.get("sha256") if file_meta else None,
            }
            conn.execute(
                """
                INSERT INTO biblioteca_icbf_versiones
                (fundacion_id,documento_id,version,fecha_documento,fecha_vigencia_desde,fecha_vigencia_hasta,estado,nombre_original,nombre_guardado,ruta_archivo,mime_type,tamano_bytes,sha256,fuente_url,notas_cambio,verificada,aprobada_por,fecha_aprobacion,creado_por,fecha_creacion,fecha_actualizacion)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(fundacion_id,documento_id,version) DO UPDATE SET
                    fecha_documento=excluded.fecha_documento,fecha_vigencia_desde=excluded.fecha_vigencia_desde,
                    fecha_vigencia_hasta=excluded.fecha_vigencia_hasta,estado=excluded.estado,
                    nombre_original=COALESCE(excluded.nombre_original,biblioteca_icbf_versiones.nombre_original),
                    nombre_guardado=COALESCE(excluded.nombre_guardado,biblioteca_icbf_versiones.nombre_guardado),
                    ruta_archivo=COALESCE(excluded.ruta_archivo,biblioteca_icbf_versiones.ruta_archivo),
                    mime_type=COALESCE(excluded.mime_type,biblioteca_icbf_versiones.mime_type),
                    tamano_bytes=CASE WHEN excluded.tamano_bytes>0 THEN excluded.tamano_bytes ELSE biblioteca_icbf_versiones.tamano_bytes END,
                    sha256=COALESCE(excluded.sha256,biblioteca_icbf_versiones.sha256),fuente_url=excluded.fuente_url,
                    notas_cambio=excluded.notas_cambio,verificada=excluded.verificada,
                    aprobada_por=excluded.aprobada_por,fecha_aprobacion=excluded.fecha_aprobacion,
                    fecha_actualizacion=excluded.fecha_actualizacion
                """,
                (
                    fundacion_id, document_id, version, valid_date(payload.get("fecha_documento")), valid_date(payload.get("fecha_vigencia_desde")),
                    valid_date(payload.get("fecha_vigencia_hasta")), state, values["nombre_original"], values["nombre_guardado"], values["ruta_archivo"],
                    values["mime_type"], values["tamano_bytes"], values["sha256"], str(payload.get("fuente_url") or "")[:1000] or None,
                    str(payload.get("notas_cambio") or "")[:4000] or None, int(bool(payload.get("verificada") or state in {"APROBADA", "VIGENTE"})),
                    user.get("id") if state in {"APROBADA", "VIGENTE"} else None, now if state in {"APROBADA", "VIGENTE"} else None,
                    user.get("id"), now, now,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM biblioteca_icbf_versiones WHERE fundacion_id=? AND documento_id=? AND version=?", (fundacion_id, document_id, version)).fetchone()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "GUARDAR_VERSION_BIBLIOTECA", "biblioteca_icbf_versiones", row["id"], {"documento_id": document_id, "version": version, "estado": state})
        self.library_history_event(fundacion_id, user, "GUARDAR_VERSION", document_id=document_id, version_id=int(row["id"]), new_state=state, detail={"version": version, "archivo": bool(file_meta)})
        self.notify_library(fundacion_id, "Nueva versión documental registrada", f"Se registró la versión {version}. Requiere revisión antes de quedar vigente.", level="INFO", document_id=document_id, version_id=int(row["id"]), action_url="#biblioteca-icbf")
        return dict(row)

    def activate_library_version(self, fundacion_id: int, version_id: int, user: dict[str, Any]) -> dict[str, Any]:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM biblioteca_icbf_versiones WHERE id=? AND fundacion_id=?", (version_id, fundacion_id)).fetchone()
            if not row:
                raise LookupError("Versión no encontrada.")
            # Una detección de metadatos nunca se vuelve vigente por sí sola.
            # Exigimos verificación y una fuente comprobable: archivo íntegro en
            # almacenamiento autorizado o URL HTTPS del dominio institucional.
            if not int(row["verificada"] or 0):
                raise ValueError("La versión debe verificarse antes de activarla.")
            raw_path = str(row["ruta_archivo"] or "").strip()
            verified_source = False
            if raw_path:
                candidate_path = Path(raw_path).resolve()
                if candidate_path.is_file() and (not row["sha256"] or file_sha256(candidate_path) == row["sha256"]):
                    verified_source = True
            if not verified_source:
                parsed = urlparse(str(row["fuente_url"] or "").strip())
                host = str(parsed.hostname or "").lower()
                verified_source = parsed.scheme == "https" and (host == "icbf.gov.co" or host.endswith(".icbf.gov.co"))
            if not verified_source:
                raise ValueError("Carga y verifica el archivo oficial o registra una URL HTTPS institucional antes de activar la versión.")
            now = now_iso()
            conn.execute("UPDATE biblioteca_icbf_versiones SET estado='HISTORICA',fecha_actualizacion=? WHERE fundacion_id=? AND documento_id=? AND estado='VIGENTE' AND id<>?", (now, fundacion_id, row["documento_id"], version_id))
            conn.execute("UPDATE biblioteca_icbf_versiones SET estado='VIGENTE',verificada=1,aprobada_por=?,fecha_aprobacion=?,fecha_actualizacion=? WHERE id=?", (user.get("id"), now, now, version_id))
            conn.commit()
            updated = conn.execute("SELECT * FROM biblioteca_icbf_versiones WHERE id=?", (version_id,)).fetchone()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "ACTIVAR_VERSION_BIBLIOTECA", "biblioteca_icbf_versiones", version_id, {"documento_id": row["documento_id"], "version": row["version"]})
        self.library_history_event(fundacion_id, user, "ACTIVAR_VERSION", document_id=int(row["documento_id"]), version_id=version_id, previous_state=str(row["estado"] or ""), new_state="VIGENTE", detail={"version": row["version"]})
        relations = self.list_library_relations(fundacion_id, int(row["documento_id"]))
        if not relations:
            relations = self.apply_suggested_library_relations(fundacion_id, int(row["documento_id"]), user)
        modules = sorted({str(item.get("modulo") or "") for item in relations if item.get("modulo")})
        for module in modules or [None]:
            self.notify_library(fundacion_id, "Documento oficial actualizado", f"La versión {row['version']} quedó vigente. Revise los productos y formatos relacionados antes de utilizarlos.", level="ADVERTENCIA", document_id=int(row["documento_id"]), version_id=version_id, module=module, action_url="#biblioteca-icbf")
        return dict(updated)

    def library_version_path(self, fundacion_id: int, version_id: int) -> tuple[str, str] | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT ruta_archivo,nombre_original FROM biblioteca_icbf_versiones WHERE id=? AND fundacion_id=?", (version_id, fundacion_id)).fetchone()
            if not row or not row["ruta_archivo"]:
                return None
            path = str(row["ruta_archivo"])
            return (path, str(row["nombre_original"] or os.path.basename(path))) if os.path.isfile(path) else None
        finally:
            conn.close()

    def dashboard(self, fundacion_id: int, vigencia: str | None = None, allowed_units: list[str] | None = None) -> dict[str, Any]:
        expedientes = self.list_expedientes(fundacion_id, vigencia, allowed_units)
        counts = {"total": len(expedientes), "verde": 0, "amarillo": 0, "rojo": 0, "promedio": 0.0}
        if expedientes:
            for item in expedientes:
                light = str(item.get("semaforo") or "ROJO").lower()
                if light in counts:
                    counts[light] += 1
            counts["promedio"] = round(sum(float(item.get("porcentaje_global") or 0) for item in expedientes) / len(expedientes), 2)
        return {
            "resumen": counts,
            "expedientes": expedientes,
            "fases": [{"codigo": code, "titulo": title, "orden": order} for code, title, order in PHASES],
            "biblioteca": self.list_library_documents(fundacion_id, include_versions=False),
            "modulos": MODULE_LINKS,
        }

    def build_supervision_package(self, fundacion_id: int, expediente_id: int, user: dict[str, Any]) -> str:
        expediente = self.get_expediente(expediente_id, fundacion_id)
        if not expediente:
            raise LookupError("Expediente no encontrado.")
        integrated = self.integrated_view(fundacion_id, expediente_id)
        safe_unit = "_".join(normalize_text(expediente["unidad_nombre"]).split())[:80] or "UCA"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_dir = self.data_dir / "tenants" / str(fundacion_id) / "archivos_actualizados" / "gestion_integral_uca"
        package_dir.mkdir(parents=True, exist_ok=True)
        out_path = package_dir / f"PAQUETE_SUPERVISION_{safe_unit}_{expediente['vigencia']}_{timestamp}.zip"
        conn = self.connect()
        try:
            evidence_rows = conn.execute(
                """
                SELECT e.*,c.fase,c.codigo AS actividad_codigo,c.titulo AS actividad_titulo
                FROM giu_ruta_evidencias e
                JOIN giu_ruta_instancias i ON i.id=e.instancia_id
                JOIN giu_ruta_catalogo c ON c.id=i.catalogo_id
                WHERE e.fundacion_id=? AND e.expediente_id=? AND e.activo=1
                ORDER BY c.orden,e.version
                """,
                (fundacion_id, expediente_id),
            ).fetchall()
            audit_rows = conn.execute(
                "SELECT accion,entidad,entidad_id,detalle_json,fecha,usuario FROM giu_auditoria "
                "WHERE fundacion_id=? AND (entidad_id=? OR detalle_json LIKE ?) ORDER BY fecha",
                (fundacion_id, expediente_id, f'%"expediente_id":{expediente_id}%'),
            ).fetchall()
        finally:
            conn.close()

        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            summary = dict(expediente)
            summary["biblioteca"] = [
                {key: doc.get(key) for key in ("codigo", "nombre", "componente", "version_vigente", "versiones_total")}
                for doc in expediente.get("biblioteca", [])
            ]
            summary["centro_operativo"] = {
                "unidad": integrated.get("unidad"),
                "preparacion_supervision": integrated.get("preparacion_supervision"),
                "generado_en": integrated.get("generado_en"),
            }
            archive.writestr("00_RESUMEN_EXPEDIENTE.json", json.dumps(summary, ensure_ascii=False, indent=2, default=str))

            route_buffer = io.StringIO()
            route_writer = csv.writer(route_buffer)
            route_writer.writerow(["Fase", "Código", "Actividad", "Componente", "Obligatoria", "Estado", "Responsable", "Fecha límite", "Evidencias", "Observaciones"])
            for item in expediente.get("ruta", []):
                route_writer.writerow([
                    item.get("fase"), item.get("actividad_codigo"), item.get("titulo"), item.get("componente"), item.get("obligatoria"),
                    item.get("estado"), item.get("responsable_nombre"), item.get("fecha_limite"), item.get("evidencias_total"), item.get("observaciones"),
                ])
            archive.writestr("01_RUTA_OPERATIVA.csv", route_buffer.getvalue().encode("utf-8-sig"))

            plans_buffer = io.StringIO()
            plans_writer = csv.writer(plans_buffer)
            plans_writer.writerow(["Código", "Plan", "Estado", "Progreso", "Responsable", "Fecha inicio", "Fecha fin", "Observaciones"])
            for plan in expediente.get("planes", []):
                plans_writer.writerow([plan.get("codigo"), plan.get("nombre"), plan.get("estado"), plan.get("progreso"), plan.get("responsable_nombre"), plan.get("fecha_inicio"), plan.get("fecha_fin"), plan.get("observaciones")])
            archive.writestr("02_OCHO_PLANES.csv", plans_buffer.getvalue().encode("utf-8-sig"))

            evidence_buffer = io.StringIO()
            evidence_writer = csv.writer(evidence_buffer)
            evidence_writer.writerow(["Fase", "Actividad", "Archivo", "Versión", "SHA-256", "Fecha", "Incluido"])
            for row in evidence_rows:
                source = Path(str(row["ruta_archivo"] or ""))
                included = False
                archive_name = f"evidencias/{row['fase']}/{row['actividad_codigo']}/{row['version']}_{row['nombre_guardado']}"
                if source.is_file():
                    try:
                        source.resolve().relative_to(self.data_dir)
                        archive.write(source, archive_name)
                        included = True
                    except ValueError:
                        included = False
                evidence_writer.writerow([row["fase"], row["actividad_titulo"], row["nombre_original"], row["version"], row["sha256"], row["fecha_carga"], "SI" if included else "NO"])
            archive.writestr("03_MANIFIESTO_EVIDENCIAS.csv", evidence_buffer.getvalue().encode("utf-8-sig"))

            audit_buffer = io.StringIO()
            audit_writer = csv.writer(audit_buffer)
            audit_writer.writerow(["Fecha", "Usuario", "Acción", "Entidad", "Entidad ID", "Detalle"])
            for row in audit_rows:
                audit_writer.writerow([row["fecha"], row["usuario"], row["accion"], row["entidad"], row["entidad_id"], row["detalle_json"]])
            archive.writestr("04_TRAZABILIDAD.csv", audit_buffer.getvalue().encode("utf-8-sig"))

            indicators_buffer = io.StringIO()
            indicators_writer = csv.writer(indicators_buffer)
            indicators_writer.writerow(["Código", "Indicador", "Valor", "Unidad", "Semáforo", "Fuente"])
            for item in integrated.get("indicadores") or []:
                indicators_writer.writerow([item.get("codigo"), item.get("nombre"), item.get("valor"), item.get("unidad"), item.get("semaforo"), item.get("fuente")])
            archive.writestr("05_INDICADORES_UCA.csv", indicators_buffer.getvalue().encode("utf-8-sig"))

            alerts_buffer = io.StringIO()
            alerts_writer = csv.writer(alerts_buffer)
            alerts_writer.writerow(["Componente", "Tipo", "Nivel", "Mensaje", "Fecha", "Fuente"])
            for item in integrated.get("alertas") or []:
                alerts_writer.writerow([item.get("componente"), item.get("tipo"), item.get("nivel"), item.get("mensaje"), item.get("fecha"), item.get("source_table")])
            archive.writestr("06_ALERTAS_UCA.csv", alerts_buffer.getvalue().encode("utf-8-sig"))

            calendar_buffer = io.StringIO()
            calendar_writer = csv.writer(calendar_buffer)
            calendar_writer.writerow(["Fecha", "Título", "Estado", "Prioridad", "Responsable", "Vencida", "Fuente"])
            for item in integrated.get("cronograma") or []:
                calendar_writer.writerow([item.get("fecha"), item.get("titulo"), item.get("estado"), item.get("prioridad"), item.get("responsable"), "SI" if item.get("vencida") else "NO", item.get("source_table")])
            archive.writestr("07_CRONOGRAMA_UCA.csv", calendar_buffer.getvalue().encode("utf-8-sig"))

            docs_buffer = io.StringIO()
            docs_writer = csv.writer(docs_buffer)
            docs_writer.writerow(["ID vínculo", "Módulo", "Tabla", "ID fuente", "Categoría", "Título", "Estado", "Fecha", "Archivo", "Versión", "Incluido"])
            for document in integrated.get("documentos") or []:
                included = False
                link_id = int(document.get("id") or 0)
                found = self.linked_document_path(fundacion_id, expediente_id, link_id) if link_id else None
                if found:
                    raw_path, download_name = found
                    source_name = Path(download_name)
                    safe_name = "_".join(normalize_text(source_name.stem).split())[:100] or f"documento_{link_id}"
                    extension = source_name.suffix
                    archive.write(raw_path, f"documentos_vinculados/{link_id}_{safe_name}{extension}")
                    included = True
                docs_writer.writerow([
                    link_id, document.get("source_module"), document.get("source_table"), document.get("source_id"),
                    document.get("categoria"), document.get("titulo"), document.get("estado"), document.get("fecha_documento"),
                    document.get("file_name"), document.get("version"), "SI" if included else "NO",
                ])
            archive.writestr("08_DOCUMENTOS_VINCULADOS.csv", docs_buffer.getvalue().encode("utf-8-sig"))

            archive.writestr("09_ESTADO_COMPONENTES.json", json.dumps(integrated.get("componentes") or [], ensure_ascii=False, indent=2, default=str))
            archive.writestr("10_PREPARACION_SUPERVISION.json", json.dumps(integrated.get("preparacion_supervision") or {}, ensure_ascii=False, indent=2, default=str))
            archive.writestr("11_FUENTES_INTEGRADAS.json", json.dumps(integrated.get("fuentes") or [], ensure_ascii=False, indent=2, default=str))

            archive.writestr(
                "LEEME.txt",
                (
                    "Paquete de supervisión generado por Primera Infancia.\n"
                    f"UCA: {expediente['unidad_nombre']}\nVigencia: {expediente['vigencia']}\n"
                    f"Progreso Ruta Operativa: {expediente['porcentaje_global']}%\nSemáforo Ruta: {expediente['semaforo']}\n"
                    f"Preparación consolidada para supervisión: {integrated.get('preparacion_supervision', {}).get('porcentaje', 0)}%\n"
                    "El paquete integra referencias y productos existentes; no crea una segunda Base Maestra ni sustituye la revisión del supervisor o interventor.\n"
                ).encode("utf-8"),
            )

        digest = file_sha256(str(out_path))
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO giu_paquetes_supervision(fundacion_id,expediente_id,nombre_archivo,ruta_archivo,sha256,tamano_bytes,resumen_json,generado_por,fecha_generacion) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    fundacion_id, expediente_id, out_path.name, str(out_path), digest, out_path.stat().st_size,
                    json_dump(integrated.get("preparacion_supervision") or {}), user.get("id"), now_iso(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.audit(fundacion_id, user, "GENERAR_PAQUETE_SUPERVISION", "giu_expedientes_uca", expediente_id, {"archivo": out_path.name, "sha256": digest, "documentos_vinculados": len(integrated.get("documentos") or [])})
        return str(out_path)

    # ------------------------------------------------------------------
    # Biblioteca Oficial ICBF 2.5.3: fuentes, detección, aprobación e historial
    # ------------------------------------------------------------------
    def library_history_event(
        self,
        fundacion_id: int,
        user: dict[str, Any],
        action: str,
        *,
        document_id: int | None = None,
        version_id: int | None = None,
        candidate_id: int | None = None,
        previous_state: str | None = None,
        new_state: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO biblioteca_icbf_historial
                (fundacion_id,documento_id,version_id,candidato_id,usuario_id,usuario,accion,estado_anterior,estado_nuevo,detalle_json,fecha)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    fundacion_id, document_id, version_id, candidate_id, user.get("id"),
                    user.get("username") or user.get("email") or "sistema", action,
                    previous_state, new_state, json_dump(detail or {}), now_iso(),
                ),
            )

    def notify_library(
        self,
        fundacion_id: int,
        title: str,
        message: str,
        *,
        level: str = "INFO",
        document_id: int | None = None,
        version_id: int | None = None,
        candidate_id: int | None = None,
        module: str | None = None,
        action_url: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO biblioteca_icbf_notificaciones
                (fundacion_id,documento_id,version_id,candidato_id,modulo,nivel,titulo,mensaje,accion_url,leida,creada_en)
                VALUES(?,?,?,?,?,?,?,?,?,0,?)
                """,
                (
                    fundacion_id, document_id, version_id, candidate_id, module,
                    normalize_text(level).replace(" ", "_")[:30] or "INFO", title[:500], message[:3000],
                    str(action_url or "")[:1000] or None, now_iso(),
                ),
            )
            return int(cur.lastrowid)

    @staticmethod
    def _version_tokens(value: Any) -> tuple[Any, ...]:
        import re
        raw = str(value or "").strip().lower()
        parts = re.findall(r"\d+|[a-z]+", raw)
        return tuple(int(part) if part.isdigit() else part for part in parts) or (raw,)

    def suggest_library_relations(self, fundacion_id: int, document_id: int) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT * FROM biblioteca_icbf_documentos WHERE id=? AND fundacion_id=? AND activo=1",
                (document_id, fundacion_id),
            ).fetchone()
            if not row:
                raise LookupError("Documento de biblioteca no encontrado.")
            doc = dict(row)
        finally:
            conn.close()
        haystack = normalize_text(" ".join(str(doc.get(key) or "") for key in ("codigo", "nombre", "tipo_documento", "componente", "descripcion")))
        mapping = [
            (("RAM", "ASISTENCIA"), "formatos", "PLANTILLA", True),
            (("RPP", "RACION PARA PREPARAR"), "formatos", "PLANTILLA", True),
            (("BIENESTARINA", "ALTO VALOR NUTRICIONAL"), "formatos", "PLANTILLA", True),
            (("SALUD", "NUTRICION", "ANTROPOMETR", "CAPTURE", "VACUN"), "salud-nutricion", "REFERENCIA_TECNICA", True),
            (("PEDAGOG", "DESARROLLO INFANTIL", "PLANEACION"), "gestion-pedagogica", "REFERENCIA_TECNICA", True),
            (("TALENTO HUMANO", "INDUCCION", "CUALIFICACION"), "talento", "REFERENCIA_TECNICA", True),
            (("AMBIENTES", "RIESGO", "DOTACION", "SANEAMIENTO"), "expediente-operativo-uca", "REFERENCIA_TECNICA", False),
            (("FAMILIA", "COMUNIDAD", "REDES", "PSICOSOCIAL"), "gestion-coordinador", "REFERENCIA_TECNICA", False),
            (("SUPERVISION", "INTERVENTORIA", "MONITOREO", "INDICADOR"), "reportes-gerenciales", "REFERENCIA_TECNICA", False),
            (("CRONOGRAMA", "TAREA", "ENTREGABLE", "PLAZO", "CIERRE", "SEGUIMIENTO"), "motor-gestion-proyecto", "REFERENCIA_TECNICA", False),
            (("MANUAL", "TRANSVERSAL", "MT3 PP"), "expediente-operativo-uca", "DOCUMENTO_RECTOR", True),
            (("MANUAL", "TRANSVERSAL", "MT3 PP"), "biblioteca-icbf", "DOCUMENTO_RECTOR", True),
        ]
        suggestions: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for keywords, module, relation_type, required in mapping:
            if any(keyword in haystack for keyword in keywords):
                key = (module, relation_type)
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append({
                    "modulo": module,
                    "tipo_relacion": relation_type,
                    "obligatorio": required,
                    "observaciones": "Relación sugerida automáticamente por código, componente y descripción; requiere revisión administrativa.",
                })
        if not suggestions:
            suggestions.append({
                "modulo": "biblioteca-icbf", "tipo_relacion": "REFERENCIA", "obligatorio": False,
                "observaciones": "Relación general sugerida; requiere revisión administrativa.",
            })
        return suggestions

    def apply_suggested_library_relations(self, fundacion_id: int, document_id: int, user: dict[str, Any]) -> list[dict[str, Any]]:
        suggestions = self.suggest_library_relations(fundacion_id, document_id)
        current = self.list_library_relations(fundacion_id, document_id)
        combined = current + [item for item in suggestions if not any(
            row.get("modulo") == item.get("modulo") and row.get("tipo_relacion") == item.get("tipo_relacion") for row in current
        )]
        result = self.set_library_relations(fundacion_id, document_id, combined, user)
        self.library_history_event(fundacion_id, user, "APLICAR_RELACIONES_SUGERIDAS", document_id=document_id, detail={"total": len(result)})
        return result

    def list_library_sources(self, fundacion_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            self._seed_library_sources(conn)
            conn.commit()
            rows = conn.execute(
                "SELECT * FROM biblioteca_icbf_fuentes WHERE fundacion_id=? ORDER BY habilitada DESC,nombre",
                (fundacion_id,),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["configuracion"] = parse_json(item.pop("configuracion_json", None), {})
                result.append(item)
            return result

    def save_library_source(self, fundacion_id: int, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        code = normalize_text(payload.get("codigo")).replace(" ", "_")[:80]
        name = str(payload.get("nombre") or "").strip()
        if not code or not name:
            raise ValueError("Código y nombre de la fuente son obligatorios.")
        mechanism = normalize_text(payload.get("mecanismo") or "MANUAL").replace(" ", "_")
        user_role = normalize_text(user.get("rol"))
        if user_role not in {"SUPERADMIN", "GERENTE"} and (payload.get("autorizada") or payload.get("habilitada") or mechanism == "CATALOGO_JSON"):
            raise ValueError("Solo SUPERADMIN o GERENTE puede autorizar o habilitar una fuente remota.")
        if mechanism not in {"MANUAL", "CATALOGO_JSON"}:
            raise ValueError("Mecanismo no permitido. Usa MANUAL o CATALOGO_JSON.")
        url = str(payload.get("url_base") or "").strip()[:1000] or None
        now = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO biblioteca_icbf_fuentes
                (fundacion_id,codigo,nombre,tipo_fuente,mecanismo,url_base,dominio_permitido,autorizada,habilitada,intervalo_horas,configuracion_json,
                 creado_por,actualizado_por,fecha_creacion,fecha_actualizacion)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(fundacion_id,codigo) DO UPDATE SET
                  nombre=excluded.nombre,tipo_fuente=excluded.tipo_fuente,mecanismo=excluded.mecanismo,url_base=excluded.url_base,
                  dominio_permitido=excluded.dominio_permitido,autorizada=excluded.autorizada,habilitada=excluded.habilitada,
                  intervalo_horas=excluded.intervalo_horas,configuracion_json=excluded.configuracion_json,
                  actualizado_por=excluded.actualizado_por,fecha_actualizacion=excluded.fecha_actualizacion
                """,
                (
                    fundacion_id, code, name, str(payload.get("tipo_fuente") or "REPOSITORIO_PUBLICO")[:80], mechanism, url,
                    str(payload.get("dominio_permitido") or "")[:255] or None, int(bool(payload.get("autorizada"))),
                    int(bool(payload.get("habilitada"))), max(1, min(720, int(payload.get("intervalo_horas") or 24))),
                    json_dump(payload.get("configuracion") or {}), user.get("id"), user.get("id"), now, now,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM biblioteca_icbf_fuentes WHERE fundacion_id=? AND codigo=?", (fundacion_id, code)).fetchone()
        self.library_history_event(fundacion_id, user, "GUARDAR_FUENTE", detail={"codigo": code, "mecanismo": mechanism})
        item = dict(row)
        item["configuracion"] = parse_json(item.pop("configuracion_json", None), {})
        return item

    def get_library_source(self, fundacion_id: int, source_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM biblioteca_icbf_fuentes WHERE id=? AND fundacion_id=?", (source_id, fundacion_id)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["configuracion"] = parse_json(item.get("configuracion_json"), {})
        return item

    def update_source_check_status(self, fundacion_id: int, source_id: int, *, status: str, detail: str, etag: str | None = None, last_modified: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE biblioteca_icbf_fuentes SET fecha_ultima_revision=?,estado_ultima_revision=?,detalle_ultima_revision=?,
                  ultimo_etag=COALESCE(?,ultimo_etag),ultima_modificacion=COALESCE(?,ultima_modificacion),fecha_actualizacion=?
                WHERE id=? AND fundacion_id=?
                """,
                (now_iso(), status[:60], detail[:2000], etag, last_modified, now_iso(), source_id, fundacion_id),
            )

    def import_library_candidates(self, fundacion_id: int, source_id: int | None, items: list[dict[str, Any]], user: dict[str, Any]) -> dict[str, Any]:
        import hashlib
        if len(items or []) > 5000:
            raise ValueError("El catálogo supera el máximo de 5000 elementos.")
        detected = 0
        unchanged = 0
        invalid = 0
        ids: list[int] = []
        now = now_iso()
        conn = self.connect()
        try:
            for raw in items or []:
                if not isinstance(raw, dict):
                    invalid += 1
                    continue
                code = normalize_text(raw.get("codigo") or raw.get("codigo_documento")).replace(" ", "_")[:80]
                version = str(raw.get("version") or raw.get("version_detectada") or "").strip()[:80]
                name = str(raw.get("nombre") or raw.get("nombre_documento") or code).strip()[:500]
                if not code or not version:
                    invalid += 1
                    continue
                document = conn.execute(
                    "SELECT * FROM biblioteca_icbf_documentos WHERE fundacion_id=? AND codigo=? AND activo=1",
                    (fundacion_id, code),
                ).fetchone()
                document_id = int(document["id"]) if document else None
                current = None
                if document_id:
                    current = conn.execute(
                        "SELECT version,sha256 FROM biblioteca_icbf_versiones WHERE fundacion_id=? AND documento_id=? AND estado='VIGENTE' ORDER BY id DESC LIMIT 1",
                        (fundacion_id, document_id),
                    ).fetchone()
                expected_sha = str(raw.get("sha256") or raw.get("sha256_esperado") or "").strip().lower()[:64] or None
                if current and self._version_tokens(current["version"]) == self._version_tokens(version) and (not expected_sha or expected_sha == str(current["sha256"] or "").lower()):
                    unchanged += 1
                    continue
                canonical = {
                    "codigo": code, "nombre": name, "version": version,
                    "fecha_documento": valid_date(raw.get("fecha_documento")),
                    "fecha_vigencia_desde": valid_date(raw.get("fecha_vigencia_desde")),
                    "fuente_url": str(raw.get("fuente_url") or raw.get("url") or "")[:1000] or None,
                    "sha256": expected_sha, "componente": raw.get("componente"), "modalidad": raw.get("modalidad"),
                    "tipo_documento": raw.get("tipo_documento"), "notas_cambio": raw.get("notas_cambio"),
                }
                candidate_hash = hashlib.sha256(json_dump(canonical).encode("utf-8")).hexdigest()
                cursor = conn.execute(
                    """
                    INSERT INTO biblioteca_icbf_candidatos
                    (fundacion_id,fuente_id,documento_id,codigo_documento,nombre_documento,version_detectada,fecha_documento,
                     fecha_vigencia_desde,fuente_url,sha256_esperado,etag,ultima_modificacion,candidato_hash,payload_json,estado,detectado_por,fecha_deteccion)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'DETECTADA',?,?)
                    ON CONFLICT(fundacion_id,candidato_hash) DO UPDATE SET
                      fuente_id=excluded.fuente_id,documento_id=excluded.documento_id,payload_json=excluded.payload_json,
                      fuente_url=excluded.fuente_url,fecha_deteccion=excluded.fecha_deteccion,
                      estado=CASE WHEN biblioteca_icbf_candidatos.estado IN ('RECHAZADA','APLICADA') THEN biblioteca_icbf_candidatos.estado ELSE 'DETECTADA' END
                    """,
                    (
                        fundacion_id, source_id, document_id, code, name, version, canonical["fecha_documento"],
                        canonical["fecha_vigencia_desde"], canonical["fuente_url"], expected_sha,
                        str(raw.get("etag") or "")[:500] or None, str(raw.get("ultima_modificacion") or "")[:500] or None,
                        candidate_hash, json_dump(canonical), user.get("id"), now,
                    ),
                )
                row = conn.execute("SELECT id FROM biblioteca_icbf_candidatos WHERE fundacion_id=? AND candidato_hash=?", (fundacion_id, candidate_hash)).fetchone()
                candidate_id = int(row[0])
                ids.append(candidate_id)
                detected += 1
            conn.commit()
        finally:
            conn.close()
        for candidate_id in ids:
            self.notify_library(
                fundacion_id, "Actualización documental detectada",
                "Se detectó una versión candidata. Debe revisarse y aprobarse manualmente antes de aplicarla.",
                level="ADVERTENCIA", candidate_id=candidate_id, action_url="#biblioteca-icbf",
            )
        result = {"detectadas": detected, "sin_cambios": unchanged, "invalidas": invalid, "candidatos": ids}
        self.library_history_event(fundacion_id, user, "IMPORTAR_CANDIDATOS", detail=result)
        return result

    def list_library_candidates(self, fundacion_id: int, status: str | None = None) -> list[dict[str, Any]]:
        where = ["c.fundacion_id=?"]
        params: list[Any] = [fundacion_id]
        if status:
            where.append("c.estado=?")
            params.append(normalize_text(status).replace(" ", "_"))
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT c.*,f.nombre AS fuente_nombre,d.nombre AS documento_nombre,
                       (SELECT v.version FROM biblioteca_icbf_versiones v WHERE v.fundacion_id=c.fundacion_id AND v.documento_id=c.documento_id AND v.estado='VIGENTE' ORDER BY v.id DESC LIMIT 1) AS version_actual
                FROM biblioteca_icbf_candidatos c
                LEFT JOIN biblioteca_icbf_fuentes f ON f.id=c.fuente_id AND f.fundacion_id=c.fundacion_id
                LEFT JOIN biblioteca_icbf_documentos d ON d.id=c.documento_id AND d.fundacion_id=c.fundacion_id
                WHERE {' AND '.join(where)} ORDER BY c.fecha_deteccion DESC,c.id DESC
                """,
                params,
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["payload"] = parse_json(item.pop("payload_json", None), {})
                result.append(item)
            return result

    def decide_library_candidate(self, fundacion_id: int, candidate_id: int, action: str, user: dict[str, Any], observations: str | None = None) -> dict[str, Any]:
        normalized = normalize_text(action).replace(" ", "_")
        if normalized not in {"APROBAR", "RECHAZAR", "APLICAR"}:
            raise ValueError("Acción de candidato no permitida.")
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM biblioteca_icbf_candidatos WHERE id=? AND fundacion_id=?", (candidate_id, fundacion_id)).fetchone()
            if not row:
                raise LookupError("Candidato no encontrado.")
            candidate = dict(row)
            previous = candidate.get("estado")
            payload = parse_json(candidate.get("payload_json"), {}) or {}
            now = now_iso()
            document_id = candidate.get("documento_id")
            version_id = None
            if normalized in {"APROBAR", "APLICAR"}:
                if not document_id:
                    code = candidate["codigo_documento"]
                    conn.execute(
                        """
                        INSERT INTO biblioteca_icbf_documentos
                        (fundacion_id,codigo,nombre,tipo_documento,modalidad,componente,descripcion,fuente_tipo,fuente_url,verificacion_automatica,activo,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion)
                        VALUES(?,?,?,?,?,?,?,'FUENTE_AUTORIZADA',?,0,1,?,?,?,?)
                        ON CONFLICT(fundacion_id,codigo) DO UPDATE SET
                          nombre=excluded.nombre,modalidad=COALESCE(excluded.modalidad,biblioteca_icbf_documentos.modalidad),
                          componente=COALESCE(excluded.componente,biblioteca_icbf_documentos.componente),
                          tipo_documento=COALESCE(excluded.tipo_documento,biblioteca_icbf_documentos.tipo_documento),
                          fuente_url=COALESCE(excluded.fuente_url,biblioteca_icbf_documentos.fuente_url),fecha_actualizacion=excluded.fecha_actualizacion
                        """,
                        (
                            fundacion_id, code, candidate.get("nombre_documento") or code,
                            str(payload.get("tipo_documento") or "DOCUMENTO_TECNICO")[:80],
                            str(payload.get("modalidad") or "")[:150] or None,
                            str(payload.get("componente") or "")[:150] or None,
                            "Documento creado desde una actualización candidata aprobada.", candidate.get("fuente_url"),
                            user.get("id"), user.get("id"), now, now,
                        ),
                    )
                    document_id = conn.execute("SELECT id FROM biblioteca_icbf_documentos WHERE fundacion_id=? AND codigo=?", (fundacion_id, code)).fetchone()[0]
                    conn.execute("UPDATE biblioteca_icbf_candidatos SET documento_id=? WHERE id=?", (document_id, candidate_id))
                conn.execute(
                    """
                    INSERT INTO biblioteca_icbf_versiones
                    (fundacion_id,documento_id,version,fecha_documento,fecha_vigencia_desde,estado,sha256,fuente_url,notas_cambio,verificada,aprobada_por,fecha_aprobacion,creado_por,fecha_creacion,fecha_actualizacion)
                    VALUES(?,?,?,?,?,'APROBADA',?,?,?,0,?,?,?, ?,?)
                    ON CONFLICT(fundacion_id,documento_id,version) DO UPDATE SET
                      fecha_documento=excluded.fecha_documento,fecha_vigencia_desde=excluded.fecha_vigencia_desde,
                      sha256=COALESCE(excluded.sha256,biblioteca_icbf_versiones.sha256),fuente_url=excluded.fuente_url,
                      notas_cambio=excluded.notas_cambio,estado=CASE WHEN biblioteca_icbf_versiones.estado='VIGENTE' THEN 'VIGENTE' ELSE 'APROBADA' END,
                      aprobada_por=excluded.aprobada_por,fecha_aprobacion=excluded.fecha_aprobacion,fecha_actualizacion=excluded.fecha_actualizacion
                    """,
                    (
                        fundacion_id, document_id, candidate["version_detectada"], candidate.get("fecha_documento"),
                        candidate.get("fecha_vigencia_desde"), candidate.get("sha256_esperado"), candidate.get("fuente_url"),
                        str(payload.get("notas_cambio") or observations or "Versión candidata aprobada; archivo oficial pendiente de carga y verificación.")[:4000],
                        user.get("id"), now, user.get("id"), now, now,
                    ),
                )
                version_id = conn.execute(
                    "SELECT id FROM biblioteca_icbf_versiones WHERE fundacion_id=? AND documento_id=? AND version=?",
                    (fundacion_id, document_id, candidate["version_detectada"]),
                ).fetchone()[0]
            new_status = {"APROBAR": "APROBADA", "RECHAZAR": "RECHAZADA", "APLICAR": "APLICADA"}[normalized]
            conn.execute(
                """
                UPDATE biblioteca_icbf_candidatos SET estado=?,observaciones=?,revisado_por=?,aprobado_por=?,fecha_revision=?,fecha_aprobacion=?,fecha_aplicacion=?
                WHERE id=? AND fundacion_id=?
                """,
                (
                    new_status, str(observations or "")[:2000] or None, user.get("id"),
                    user.get("id") if normalized in {"APROBAR", "APLICAR"} else None, now,
                    now if normalized in {"APROBAR", "APLICAR"} else None, now if normalized == "APLICAR" else None,
                    candidate_id, fundacion_id,
                ),
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM biblioteca_icbf_candidatos WHERE id=?", (candidate_id,)).fetchone()
        finally:
            conn.close()
        if normalized in {"APROBAR", "APLICAR"} and document_id:
            self.apply_suggested_library_relations(fundacion_id, int(document_id), user)
        self.library_history_event(
            fundacion_id, user, f"{normalized}_CANDIDATO", document_id=int(document_id) if document_id else None,
            version_id=int(version_id) if version_id else None, candidate_id=candidate_id,
            previous_state=previous, new_state=new_status, detail={"observaciones": observations},
        )
        self.notify_library(
            fundacion_id, f"Candidato {new_status.lower()}",
            f"La versión {candidate.get('version_detectada')} de {candidate.get('codigo_documento')} cambió a {new_status}.",
            level="INFO" if normalized != "RECHAZAR" else "ADVERTENCIA", document_id=int(document_id) if document_id else None,
            version_id=int(version_id) if version_id else None, candidate_id=candidate_id, action_url="#biblioteca-icbf",
        )
        item = dict(updated)
        item["payload"] = parse_json(item.pop("payload_json", None), {})
        return item

    def list_library_notifications(self, fundacion_id: int, unread_only: bool = False) -> list[dict[str, Any]]:
        where = ["fundacion_id=?"]
        params: list[Any] = [fundacion_id]
        if unread_only:
            where.append("leida=0")
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM biblioteca_icbf_notificaciones WHERE {' AND '.join(where)} ORDER BY leida ASC,creada_en DESC,id DESC LIMIT 1000",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_library_notification_read(self, fundacion_id: int, notification_id: int, user: dict[str, Any]) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "UPDATE biblioteca_icbf_notificaciones SET leida=1,fecha_lectura=? WHERE id=? AND fundacion_id=?",
                (now_iso(), notification_id, fundacion_id),
            )
        self.library_history_event(fundacion_id, user, "LEER_NOTIFICACION", detail={"notificacion_id": notification_id})
        return bool(cur.rowcount)

    def list_library_history(self, fundacion_id: int, document_id: int | None = None, limit: int = 500) -> list[dict[str, Any]]:
        where = ["fundacion_id=?"]
        params: list[Any] = [fundacion_id]
        if document_id:
            where.append("documento_id=?")
            params.append(document_id)
        params.append(max(1, min(2000, int(limit))))
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM biblioteca_icbf_historial WHERE {' AND '.join(where)} ORDER BY fecha DESC,id DESC LIMIT ?",
                params,
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["detalle"] = parse_json(item.pop("detalle_json", None), {})
                result.append(item)
            return result
