from __future__ import annotations

import json
import os
import re
from modules.dbapi_compat import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .services import normalize_text, now_iso, parse_json

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COMPLETE_STATES = {
    "APROBADO", "APROBADA", "CERRADO", "CERRADA", "ENTREGADO", "ENTREGADA",
    "COMPLETADO", "COMPLETADA", "REALIZADO", "REALIZADA", "VALIDADO", "VALIDADA",
    "GENERADO", "GENERADA", "VIGENTE", "ATENDIDA", "RESUELTA", "NO_APLICA",
}
_OPEN_STATES = {"PENDIENTE", "ABIERTO", "ABIERTA", "ACTIVA", "EN_PROCESO", "BORRADOR", "DEVUELTA"}


def _ident(value: str) -> str:
    if not _IDENTIFIER.fullmatch(str(value or "")):
        raise ValueError(f"Identificador SQL no permitido: {value!r}")
    return f'"{value}"'


def _state(value: Any) -> str:
    return normalize_text(value).replace(" ", "_")


def _date_value(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def _truthy_text(value: Any) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    return normalized not in {"NO", "N", "0", "FALSO", "PENDIENTE", "SIN DATO", "NO APLICA"}


@dataclass(frozen=True)
class ComponentDefinition:
    key: str
    label: str
    section: str
    description: str


COMPONENTS: tuple[ComponentDefinition, ...] = (
    ComponentDefinition("base_maestra", "Base Maestra y población", "base-maestra", "Participantes, cupos, calidad y novedades."),
    ComponentDefinition("pedagogico", "Proceso pedagógico", "gestion-pedagogica", "Planeaciones, encuentros, informes, actas y evidencias."),
    ComponentDefinition("salud_nutricion", "Salud y Nutrición", "salud-nutricion", "Valoraciones, cobertura documental, alertas y entregables."),
    ComponentDefinition("ram_rpp_bienestarina", "RAM · RPP · Bienestarina", "formatos", "Disponibilidad y estado de productos oficiales por periodo."),
    ComponentDefinition("talento_humano", "Talento Humano", "talento", "Personas, asignaciones y cobertura del equipo por UCA."),
    ComponentDefinition("familias_redes", "Familia, Comunidad y Redes Sociales", "familias-redes", "Acompañamiento familiar, actividades, compromisos, alertas y redes territoriales."),
    ComponentDefinition("supervision_calidad", "Supervisión, Auditoría y Calidad", "supervision-calidad", "Verificaciones, hallazgos, planes de mejora, seguimientos y productos de supervisión."),
    ComponentDefinition("planeacion_operativa", "Planeación y Calendario Operativo", "centro-planeacion", "Agenda transversal, dependencias, recordatorios y productos operativos sin duplicación."),
    ComponentDefinition("psicosocial", "Componente Psicosocial", "componente-psicosocial", "Caracterización, planes, acciones y seguimiento profesional sobre expedientes familiares referenciales."),
    ComponentDefinition("documentos_evidencias", "Documentos y evidencias", "expediente-operativo-uca", "Índice único de referencias documentales sin copiar archivos."),
    ComponentDefinition("cronograma", "Cronograma y calendario", "calendario-inteligente", "Actividades, entregables, vencimientos y próximos compromisos."),
    ComponentDefinition("reportes_indicadores", "Reportes e indicadores", "reportes-gerenciales", "Productos de seguimiento, paquetes e indicadores derivados."),
)


class UCAIntegrationEngine:
    """Construye una vista de lectura sobre módulos existentes.

    No replica participantes, valoraciones, actividades ni documentos. Las consultas
    se realizan en vivo y el índice documental conserva solamente referencias.
    """

    def __init__(self, database_path: str, data_dir: str):
        self.database_path = str(database_path)
        self.data_dir = Path(data_dir).resolve()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=20000")
        return conn

    @staticmethod
    def table_exists(conn: sqlite3.Connection, table: str) -> bool:
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())

    @staticmethod
    def columns(conn: sqlite3.Connection, table: str) -> set[str]:
        if not UCAIntegrationEngine.table_exists(conn, table):
            return set()
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({_ident(table)})").fetchall()}

    def _foundation_rows(
        self,
        conn: sqlite3.Connection,
        table: str,
        *,
        fields: Iterable[str] | None = None,
        extra_where: str | None = None,
        params: Iterable[Any] = (),
        fundacion_id: int,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        if not self.table_exists(conn, table):
            return []
        cols = self.columns(conn, table)
        requested = [field for field in (fields or cols) if field in cols]
        if not requested:
            return []
        select = ",".join(_ident(field) for field in requested)
        where: list[str] = []
        values: list[Any] = []
        if "fundacion_id" in cols:
            where.append('"fundacion_id"=?')
            values.append(int(fundacion_id))
        if "activo" in cols:
            where.append("COALESCE(\"activo\",1)=1")
        if extra_where:
            where.append(f"({extra_where})")
            values.extend(params)
        sql = f"SELECT {select} FROM {_ident(table)}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" LIMIT {max(1, min(int(limit), 50000))}"
        try:
            return [dict(row) for row in conn.execute(sql, values).fetchall()]
        except sqlite3.Error:
            return []

    @staticmethod
    def _unit_values(row: dict[str, Any], columns: Iterable[str]) -> list[str]:
        return [str(row.get(col) or "").strip() for col in columns if row.get(col) not in (None, "")]

    @staticmethod
    def _matches_unit(row: dict[str, Any], unit_name: str, unit_code: str | None, unit_columns: Iterable[str]) -> bool:
        expected = {normalize_text(unit_name), normalize_text(unit_code)} - {""}
        values = {normalize_text(value) for value in UCAIntegrationEngine._unit_values(row, unit_columns)} - {""}
        if not values:
            return False
        if values & expected:
            return True
        return bool(values & {"TODAS", "TODOS", "GENERAL", "TODAS LAS UCA", "TODAS LAS UDS"})

    def _scoped_rows(
        self,
        conn: sqlite3.Connection,
        table: str,
        *,
        fundacion_id: int,
        unit_name: str,
        unit_code: str | None = None,
        unit_columns: tuple[str, ...] = ("unidad", "unidad_servicio", "uds", "uca", "codigo_unidad"),
        fields: Iterable[str] | None = None,
        extra_where: str | None = None,
        params: Iterable[Any] = (),
        allow_foundation_scope: bool = False,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        rows = self._foundation_rows(
            conn,
            table,
            fields=fields,
            extra_where=extra_where,
            params=params,
            fundacion_id=fundacion_id,
            limit=limit,
        )
        cols = self.columns(conn, table)
        available = tuple(column for column in unit_columns if column in cols)
        if not available:
            return rows if allow_foundation_scope else []
        return [row for row in rows if self._matches_unit(row, unit_name, unit_code, available)]

    @staticmethod
    def _count_states(rows: list[dict[str, Any]], state_columns: tuple[str, ...] = ("estado",)) -> dict[str, int]:
        result = {"total": len(rows), "completos": 0, "pendientes": 0, "otros": 0}
        for row in rows:
            value = next((row.get(col) for col in state_columns if row.get(col) not in (None, "")), "")
            state = _state(value)
            if state in _COMPLETE_STATES:
                result["completos"] += 1
            elif not state or state in _OPEN_STATES or "PENDIENT" in state or "PROCESO" in state:
                result["pendientes"] += 1
            else:
                result["otros"] += 1
        return result

    @staticmethod
    def _semaphore(value: float, *, inverse: bool = False) -> str:
        score = max(0.0, min(100.0, float(value)))
        if inverse:
            score = 100.0 - score
        if score >= 85:
            return "VERDE"
        if score >= 60:
            return "AMARILLO"
        return "ROJO"

    def _participants(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        fields = (
            "id", "documento", "nombre_completo", "unidad_servicio", "codigo_unidad", "activo", "estado",
            "carne_salud", "control_crecimiento", "carne_crecimiento", "vacunas", "alertas_json",
            "estado_validacion", "fecha_actualizacion", "fecha_consolidacion",
        )
        rows = self._scoped_rows(conn, "master_ninos", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=fields)
        total = len(rows)
        missing_health = sum(1 for row in rows if not _truthy_text(row.get("carne_salud")))
        missing_vaccines = sum(1 for row in rows if not _truthy_text(row.get("vacunas")))
        with_alerts = sum(1 for row in rows if parse_json(row.get("alertas_json"), []))
        valid = sum(1 for row in rows if _state(row.get("estado_validacion")) in {"VALIDADO", "VALIDADA", "OK", "APROBADO", "APROBADA"})
        inconsistencies = self._scoped_rows(
            conn,
            "master_inconsistencias",
            fundacion_id=fundacion_id,
            unit_name=unit_name,
            unit_code=unit_code,
            fields=("id", "unidad_servicio", "severidad", "tipo", "descripcion", "resuelta", "fecha_creacion"),
            extra_where="COALESCE(resuelta,0)=0" if "resuelta" in self.columns(conn, "master_inconsistencias") else None,
        )
        quality = round((valid / total) * 100, 2) if total else 0.0
        return {
            "total_participantes": total,
            "registros_validados": valid,
            "calidad_porcentaje": quality,
            "documentos_salud_pendientes": missing_health,
            "vacunacion_pendiente": missing_vaccines,
            "participantes_con_alertas": with_alerts,
            "inconsistencias_abiertas": len(inconsistencies),
            "semaforo": self._semaphore(quality) if total else "GRIS",
            "fuentes": ["master_ninos", "master_inconsistencias"],
        }

    def _pedagogy(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        deliverables = self._scoped_rows(conn, "gp_entregables", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "unidad", "tipo", "titulo", "periodo", "fecha_limite", "estado", "prioridad", "activo"))
        pp = self._scoped_rows(conn, "pp_planeaciones", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "unidad", "periodo", "tema", "estado", "fecha_programada", "fecha_actualizacion", "activo"))
        evidence = self._scoped_rows(conn, "gp_evidencias", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "unidad", "titulo", "estado", "fecha_creacion", "ruta_archivo"))
        reports = self._scoped_rows(conn, "informes_pedagogicos", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "unidad", "año", "mes", "tema_mes", "fecha_creacion"))
        states = self._count_states(deliverables + pp)
        compliance = round((states["completos"] / states["total"]) * 100, 2) if states["total"] else 0.0
        return {
            "planeaciones": len(pp),
            "entregables": len(deliverables),
            "entregables_completos": states["completos"],
            "entregables_pendientes": states["pendientes"],
            "evidencias": len(evidence),
            "informes": len(reports),
            "cumplimiento_porcentaje": compliance,
            "semaforo": self._semaphore(compliance) if states["total"] else "GRIS",
            "fuentes": ["gp_entregables", "pp_planeaciones", "gp_evidencias", "informes_pedagogicos"],
        }

    def _health(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None, participant_total: int) -> dict[str, Any]:
        valuations = self._scoped_rows(
            conn, "master_ninos", fundacion_id=fundacion_id, unit_name=unit_name,
            unit_code=unit_code, fields=("id", "documento", "unidad_servicio",
            "fecha_carga", "diagnostico_nutricional", "estado_nutricional",
            "alertas_json", "activo")
        )
        valuations = [row for row in valuations if any(row.get(field) not in (None, '', '[]') for field in (
            'diagnostico_nutricional', 'estado_nutricional', 'alertas_json'
        ))]
        alerts = self._scoped_rows(conn, "sn_alertas", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "documento", "unidad", "tipo", "nivel", "mensaje", "fecha_alerta", "atendida"), extra_where="COALESCE(atendida,0)=0" if "atendida" in self.columns(conn, "sn_alertas") else None)
        deliverables = self._scoped_rows(conn, "sn_entregables_mes", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "codigo", "mes", "anio", "uds", "estado", "porcentaje", "fecha_actualizacion"))
        records = self._scoped_rows(conn, "sn_expedientes_integrales", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre",), fields=("id", "documento", "unidad_nombre", "estado"), limit=10000)
        record_ids = {int(row.get("id") or 0) for row in records}
        documents = self._foundation_rows(conn, "sn_documentos_salud", fundacion_id=fundacion_id, fields=("id", "expediente_id", "tipo_documento", "estado", "fecha_vencimiento", "activo"), limit=20000)
        documents = [row for row in documents if int(row.get("expediente_id") or 0) in record_ids and int(row.get("activo") if row.get("activo") is not None else 1) == 1]
        activities = self._scoped_rows(conn, "sn_actividades_integrales", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre",), fields=("id", "unidad_nombre", "linea_componente", "estado", "fecha_programada", "requiere_evidencias"), limit=10000)
        channels = self._scoped_rows(conn, "sn_canalizaciones", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre",), fields=("id", "unidad_nombre", "estado", "prioridad", "fecha_limite"), limit=10000)
        unique_valued = len({str(row.get("documento") or row.get("id")) for row in valuations})
        coverage = round((unique_valued / participant_total) * 100, 2) if participant_total else 0.0
        overdue_controls = 0
        pending_docs = sum(1 for row in documents if _state(row.get("estado")) not in {"VIGENTE", "VALIDADO", "NO_APLICA"})
        open_channels = [row for row in channels if _state(row.get("estado")) not in _COMPLETE_STATES]
        score = coverage
        if records:
            doc_score = round((len(documents) - pending_docs) / len(documents) * 100, 2) if documents else 0.0
            activity_complete = sum(1 for row in activities if _state(row.get("estado")) in _COMPLETE_STATES)
            activity_score = round(activity_complete / len(activities) * 100, 2) if activities else 0.0
            score = round((coverage + doc_score + activity_score) / 3, 2)
        return {
            "valoraciones": len(valuations),
            "participantes_valorados": unique_valued,
            "cobertura_valoracion_porcentaje": coverage,
            "expedientes_integrales": len(records),
            "documentos_pendientes": pending_docs,
            "actividades": len(activities),
            "canalizaciones_abiertas": len(open_channels),
            "alertas_abiertas": len(alerts),
            "controles_vencidos": overdue_controls,
            "entregables": len(deliverables),
            "cumplimiento_porcentaje": score,
            "semaforo": "ROJO" if alerts or overdue_controls or any(_state(row.get("prioridad")) in {"CRITICA", "CRITICO", "ALTA", "ALTO"} for row in open_channels) else (self._semaphore(score) if participant_total or records else "GRIS"),
            "fuentes": ["master_ninos", "master_salud_nutricion", "sn_alertas", "sn_entregables_mes", "sn_expedientes_integrales", "sn_documentos_salud", "sn_actividades_integrales", "sn_canalizaciones"],
        }

    def _formats(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        deliverables = self._scoped_rows(conn, "sn_entregables_mes", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "codigo", "mes", "anio", "uds", "estado", "porcentaje", "fecha_actualizacion"))
        grouped = {"RAM": 0, "RPP": 0, "BIENESTARINA": 0, "OTROS": 0}
        pending = 0
        for row in deliverables:
            code = normalize_text(row.get("codigo"))
            key = "RAM" if "RAM" in code else ("RPP" if "RPP" in code else ("BIENESTARINA" if "BIENEST" in code else "OTROS"))
            grouped[key] += 1
            if _state(row.get("estado")) not in _COMPLETE_STATES:
                pending += 1
        templates = self._foundation_rows(conn, "plantillas_oficiales_versiones", fundacion_id=fundacion_id, fields=("id", "tipo_formato", "codigo", "version", "estado", "fecha_vigencia"), limit=1000)
        template_types = {normalize_text(row.get("tipo_formato") or row.get("codigo")) for row in templates if _state(row.get("estado")) in {"VIGENTE", "ACTIVO", "PUBLICADO", "APROBADO"}}
        availability = {
            "ram": any("RAM" in value for value in template_types),
            "rpp": any("RPP" in value for value in template_types),
            "bienestarina": any("BIENEST" in value for value in template_types),
        }
        score = 100.0 if all(availability.values()) else round(sum(1 for value in availability.values() if value) / 3 * 100, 2)
        return {
            "ram_registros": grouped["RAM"],
            "rpp_registros": grouped["RPP"],
            "bienestarina_registros": grouped["BIENESTARINA"],
            "entregables_pendientes": pending,
            "plantillas_disponibles": availability,
            "disponibilidad_porcentaje": score,
            "semaforo": self._semaphore(score),
            "fuentes": ["sn_entregables_mes", "plantillas_oficiales_versiones"],
        }

    def _talent(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        """Resume el talento humano de la UCA sin duplicar fuentes.

        La base maestra de talento es prioritaria cuando existe. Las versiones
        actuales del módulo de Talento Humano utilizan ``th_personas`` y
        ``th_asignaciones``; por eso se usa ese par como fuente canónica de
        respaldo. Esta compatibilidad evita que el expediente central muestre
        cero personas en instalaciones migradas que ya no conservan
        ``master_talento_humano``.
        """
        legacy_rows = self._scoped_rows(
            conn,
            "master_talento_humano",
            fundacion_id=fundacion_id,
            unit_name=unit_name,
            unit_code=unit_code,
            unit_columns=("unidad_servicio",),
            fields=("id", "documento", "unidad_servicio", "nombre_completo", "rol_normalizado", "cargo", "estado", "activo"),
        )
        if legacy_rows:
            people = {str(row.get("documento") or row.get("id")): row for row in legacy_rows}
            active_people = sum(
                1 for row in people.values()
                if int(row.get("activo") if row.get("activo") is not None else 1) == 1
                and _state(row.get("estado")) not in {"INACTIVO", "SUSPENDIDO", "RETIRADO", "ELIMINADO"}
            )
            active_assignments = sum(
                1 for row in legacy_rows
                if int(row.get("activo") if row.get("activo") is not None else 1) == 1
                and _state(row.get("estado")) not in {"INACTIVO", "SUSPENDIDO", "RETIRADO", "ELIMINADO"}
            )
            return {
                "personas": len(people),
                "personas_activas": active_people,
                "asignaciones": len(legacy_rows),
                "asignaciones_activas": active_assignments,
                "semaforo": "VERDE" if active_people and active_assignments else ("AMARILLO" if active_people else "ROJO"),
                "fuentes": ["master_talento_humano"],
            }

        people_rows = self._scoped_rows(
            conn,
            "th_personas",
            fundacion_id=fundacion_id,
            unit_name=unit_name,
            unit_code=unit_code,
            unit_columns=("unidad", "unidad_servicio", "uds", "uca", "codigo_unidad"),
            fields=("id", "documento", "nombre", "nombre_completo", "unidad", "unidad_servicio", "rol_normalizado", "cargo", "estado", "activo"),
        )
        assignment_rows = self._scoped_rows(
            conn,
            "th_asignaciones",
            fundacion_id=fundacion_id,
            unit_name=unit_name,
            unit_code=unit_code,
            unit_columns=("unidad", "unidad_servicio", "uds", "uca", "codigo_unidad"),
            fields=("id", "persona_id", "unidad", "unidad_servicio", "rol", "cargo", "estado", "fecha_inicio", "fecha_fin", "activo"),
        )
        people = {str(row.get("id") or row.get("documento")): row for row in people_rows}
        active_people = sum(
            1 for row in people.values()
            if int(row.get("activo") if row.get("activo") is not None else 1) == 1
            and _state(row.get("estado")) not in {"INACTIVO", "SUSPENDIDO", "RETIRADO", "ELIMINADO"}
        )
        active_assignments = sum(
            1 for row in assignment_rows
            if int(row.get("activo") if row.get("activo") is not None else 1) == 1
            and _state(row.get("estado")) not in {"INACTIVO", "SUSPENDIDO", "RETIRADO", "ELIMINADO", "FINALIZADO", "VENCIDO"}
        )
        # Algunas bases históricas tienen personas con unidad pero aún no poseen
        # filas de asignación. Se informa la cobertura real sin crear registros.
        assignment_count = len(assignment_rows)
        if people and not assignment_rows:
            active_assignments = active_people
            assignment_count = len(people)
        return {
            "personas": len(people),
            "personas_activas": active_people,
            "asignaciones": assignment_count,
            "asignaciones_activas": active_assignments,
            "semaforo": "VERDE" if active_people and active_assignments else ("AMARILLO" if active_people else "ROJO"),
            "fuentes": ["th_personas", "th_asignaciones"],
        }

    def _families_networks(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        records = self._scoped_rows(conn, "fcr_expedientes_familiares", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "estado"), limit=10000)
        activities = self._scoped_rows(conn, "fcr_actividades", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "tipo", "titulo", "estado", "fecha_programada", "fecha_limite_cierre"), limit=10000)
        commitments = self._scoped_rows(conn, "fcr_compromisos", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "estado", "fecha_limite", "prioridad"), limit=10000)
        alerts = self._scoped_rows(conn, "fcr_alertas", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "estado", "nivel", "fecha_proximo_seguimiento"), limit=10000)
        networks = self._foundation_rows(conn, "fcr_redes_apoyo", fundacion_id=fundacion_id, fields=("id", "activo", "tipo_actor", "fecha_verificacion"), limit=10000)
        open_commitments = [r for r in commitments if _state(r.get("estado")) not in _COMPLETE_STATES]
        open_alerts = [r for r in alerts if _state(r.get("estado")) not in _COMPLETE_STATES]
        critical = sum(1 for r in open_alerts if _state(r.get("nivel")) in {"CRITICO", "CRITICA", "ALTO", "ALTA"})
        completed_activities = sum(1 for r in activities if _state(r.get("estado")) in _COMPLETE_STATES)
        activity_score = round((completed_activities / len(activities)) * 100, 2) if activities else 0.0
        score = max(0.0, min(100.0, activity_score - min(40.0, len(open_commitments) * 5.0 + critical * 10.0)))
        return {
            "expedientes_familiares": len(records),
            "actividades": len(activities),
            "actividades_completas": completed_activities,
            "compromisos_abiertos": len(open_commitments),
            "alertas_abiertas": len(open_alerts),
            "alertas_prioritarias": critical,
            "redes_activas": sum(1 for r in networks if int(r.get("activo") if r.get("activo") is not None else 1) == 1),
            "cumplimiento_porcentaje": score,
            "semaforo": self._semaphore(score) if records or activities else "AMARILLO",
            "fuentes": ["fcr_expedientes_familiares", "fcr_actividades", "fcr_compromisos", "fcr_alertas", "fcr_redes_apoyo"],
        }

    def _supervision_quality(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        supervisions = self._scoped_rows(conn, "csc_supervisiones", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "estado", "porcentaje_cumplimiento", "fecha_programada"), limit=10000)
        findings = self._scoped_rows(conn, "csc_hallazgos", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "estado", "nivel_riesgo", "fecha_limite"), limit=10000)
        plans = self._scoped_rows(conn, "csc_planes_mejora", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "estado", "progreso", "fecha_limite"), limit=10000)
        open_findings = [r for r in findings if _state(r.get("estado")) not in {"CERRADO", "DESCARTADO"}]
        critical = sum(1 for r in open_findings if _state(r.get("nivel_riesgo")) in {"CRITICO", "CRITICA"})
        active_plans = [r for r in plans if _state(r.get("estado")) not in {"CERRADO", "CANCELADO"}]
        compliance_values = [_number(r.get("porcentaje_cumplimiento")) for r in supervisions if r.get("porcentaje_cumplimiento") not in (None, "")]
        average = round(sum(compliance_values) / len(compliance_values), 2) if compliance_values else (100.0 if not open_findings else 50.0)
        score = max(0.0, average - min(50.0, critical * 15.0 + max(0, len(open_findings) - critical) * 5.0))
        return {
            "supervisiones": len(supervisions),
            "hallazgos_abiertos": len(open_findings),
            "hallazgos_criticos": critical,
            "planes_activos": len(active_plans),
            "cumplimiento_promedio": average,
            "cumplimiento_porcentaje": score,
            "semaforo": self._semaphore(score),
            "fuentes": ["csc_supervisiones", "csc_hallazgos", "csc_planes_mejora", "csc_acciones_mejora"],
        }

    def _planning_center(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        rows = self._scoped_rows(
            conn, "cpo_actividad_metadata", fundacion_id=fundacion_id,
            unit_name=unit_name, unit_code=unit_code,
            unit_columns=("unidad_nombre", "unidad_clave"),
            fields=("id", "unidad_nombre", "unidad_clave", "estado_flujo", "bloqueada", "requiere_evidencias"),
            limit=10000,
        )
        total = len(rows)
        completed = sum(1 for row in rows if _state(row.get("estado_flujo")) in _COMPLETE_STATES)
        blocked = sum(1 for row in rows if int(row.get("bloqueada") or 0) == 1)
        pending = max(0, total - completed)
        score = round((completed / total) * 100, 2) if total else 100.0
        score = max(0.0, score - min(40.0, blocked * 10.0))
        return {
            "actividades": total, "completas": completed, "pendientes": pending,
            "bloqueadas": blocked, "cumplimiento_porcentaje": score,
            "semaforo": self._semaphore(score),
            "fuentes": ["cpo_actividad_metadata", "calendario_entregables", "cpo_dependencias", "cpo_notificaciones"],
        }

    def _psychosocial(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        cases = self._scoped_rows(
            conn, "ps_expedientes", fundacion_id=fundacion_id,
            unit_name=unit_name, unit_code=unit_code,
            unit_columns=("unidad_nombre", "unidad_clave"),
            fields=("id", "unidad_nombre", "unidad_clave", "estado"), limit=10000,
        )
        case_ids = [int(row["id"]) for row in cases if row.get("id")]
        plans: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        characterized = 0
        if case_ids:
            marks = ",".join("?" for _ in case_ids)
            plans = [dict(row) for row in conn.execute(
                f"SELECT id,expediente_id,estado,porcentaje FROM ps_planes_acompanamiento WHERE fundacion_id=? AND expediente_id IN ({marks})",
                [fundacion_id] + case_ids,
            ).fetchall()] if self.table_exists(conn, "ps_planes_acompanamiento") else []
            characterized = int(conn.execute(
                f"SELECT COUNT(DISTINCT expediente_id) FROM ps_caracterizaciones WHERE fundacion_id=? AND activo=1 AND expediente_id IN ({marks})",
                [fundacion_id] + case_ids,
            ).fetchone()[0] or 0) if self.table_exists(conn, "ps_caracterizaciones") else 0
            plan_ids = [int(row["id"]) for row in plans if row.get("id")]
            if plan_ids and self.table_exists(conn, "ps_acciones_plan"):
                pmarks = ",".join("?" for _ in plan_ids)
                actions = [dict(row) for row in conn.execute(
                    f"SELECT id,plan_id,estado,porcentaje,fecha_limite FROM ps_acciones_plan WHERE fundacion_id=? AND plan_id IN ({pmarks})",
                    [fundacion_id] + plan_ids,
                ).fetchall()]
        open_plans = sum(1 for row in plans if _state(row.get("estado")) not in {"CERRADO", "CANCELADO"})
        pending_actions = sum(1 for row in actions if _state(row.get("estado")) not in _COMPLETE_STATES)
        coverage = round((characterized / len(cases)) * 100, 2) if cases else 100.0
        score = max(0.0, coverage - min(40.0, pending_actions * 4.0))
        return {
            "expedientes": len(cases), "caracterizados": characterized,
            "planes_abiertos": open_plans, "acciones_pendientes": pending_actions,
            "cumplimiento_porcentaje": score, "semaforo": self._semaphore(score),
            "fuentes": ["ps_expedientes", "ps_caracterizaciones", "ps_planes_acompanamiento", "ps_acciones_plan", "ps_seguimientos"],
        }

    def schedule(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None, limit: int = 100) -> list[dict[str, Any]]:
        today = date.today().isoformat()
        items: list[dict[str, Any]] = []
        specs = [
            ("calendario_entregables", ("unidad",), "titulo", "descripcion", "fecha_limite", "estado", "prioridad", "calendario-inteligente"),
            ("calendario_actividades", ("unidad",), "titulo", "descripcion", "fecha", "estado", "prioridad", "calendario-inteligente"),
            ("gp_calendario_eventos", ("unidad",), "titulo", "descripcion", "fecha", "estado", "prioridad", "gestion-pedagogica"),
            ("sn_calendario", ("unidad", "uds"), "titulo", "descripcion", "fecha", "estado", "prioridad", "salud-nutricion"),
            ("sn_actividades_integrales", ("unidad_nombre",), "titulo", "objetivo", "fecha_programada", "estado", "linea_componente", "salud-nutricion"),
            ("sn_canalizaciones", ("unidad_nombre",), "tipo_ruta", "motivo", "fecha_limite", "estado", "prioridad", "salud-nutricion"),
            ("fcr_actividades", ("unidad_nombre", "unidad_clave"), "titulo", "objetivo", "fecha_programada", "estado", "tipo", "familias-redes"),
            ("fcr_compromisos", ("unidad_nombre", "unidad_clave"), "titulo", "descripcion", "fecha_limite", "estado", "prioridad", "familias-redes"),
            ("fcr_alertas", ("unidad_nombre", "unidad_clave"), "tipo", "descripcion", "fecha_proximo_seguimiento", "estado", "nivel", "familias-redes"),
            ("csc_supervisiones", ("unidad_nombre", "unidad_clave"), "titulo", "alcance", "fecha_programada", "estado", "tipo", "supervision-calidad"),
            ("csc_hallazgos", ("unidad_nombre", "unidad_clave"), "titulo", "descripcion", "fecha_limite", "estado", "nivel_riesgo", "supervision-calidad"),
            ("csc_planes_mejora", ("unidad_nombre", "unidad_clave"), "nombre", "objetivo", "fecha_limite", "estado", "progreso", "supervision-calidad"),
        ]
        for table, unit_cols, title_col, desc_col, date_col, state_col, priority_col, section in specs:
            cols = self.columns(conn, table)
            if not cols:
                continue
            fields = tuple(col for col in ("id", *unit_cols, title_col, desc_col, date_col, state_col, priority_col, "modulo", "responsable", "responsable_nombre") if col in cols)
            for row in self._scoped_rows(conn, table, fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=unit_cols, fields=fields, limit=5000):
                due = _date_value(row.get(date_col))
                status = _state(row.get(state_col))
                items.append({
                    "source_table": table,
                    "source_id": row.get("id"),
                    "titulo": row.get(title_col) or table,
                    "descripcion": row.get(desc_col),
                    "fecha": due,
                    "estado": row.get(state_col),
                    "prioridad": row.get(priority_col),
                    "responsable": row.get("responsable") or row.get("responsable_nombre"),
                    "vencida": bool(due and due < today and status not in _COMPLETE_STATES),
                    "seccion": section,
                })
        items.sort(key=lambda item: (item.get("fecha") or "9999-12-31", str(item.get("titulo") or "")))
        return items[: max(1, min(limit, 500))]

    def documents(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None, limit: int = 250) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []

        def append_rows(table: str, module: str, category: str, unit_cols: tuple[str, ...], title_cols: tuple[str, ...], path_cols: tuple[str, ...], date_cols: tuple[str, ...], state_cols: tuple[str, ...] = ("estado",)) -> None:
            cols = self.columns(conn, table)
            if not cols:
                return
            fields = tuple(dict.fromkeys(("id", *unit_cols, *title_cols, *path_cols, *date_cols, *state_cols, "mime_type", "tipo", "sha256", "hash_sha256", "version", "nombre_guardado", "nombre_archivo")))
            rows = self._scoped_rows(conn, table, fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=unit_cols, fields=fields, limit=5000)
            for row in rows:
                title = next((row.get(col) for col in title_cols if row.get(col)), f"{category} #{row.get('id')}")
                path = next((row.get(col) for col in path_cols if row.get(col)), None)
                doc_date = next((_date_value(row.get(col)) for col in date_cols if _date_value(row.get(col))), None)
                status = next((row.get(col) for col in state_cols if row.get(col) not in (None, "")), None)
                file_name = row.get("nombre_original") or row.get("nombre_archivo") or row.get("nombre_guardado") or (os.path.basename(str(path)) if path else None)
                docs.append({
                    "source_module": module,
                    "source_table": table,
                    "source_id": row.get("id"),
                    "categoria": category,
                    "titulo": title,
                    "estado": status,
                    "fecha_documento": doc_date,
                    "file_name": file_name,
                    "file_path": str(path) if path else None,
                    "mime_type": row.get("mime_type"),
                    "sha256": row.get("sha256") or row.get("hash_sha256"),
                    "version": row.get("version"),
                })

        append_rows("gp_evidencias", "gestion-pedagogica", "Evidencia pedagógica", ("unidad",), ("titulo", "nombre_original"), ("ruta_archivo",), ("fecha_creacion", "fecha_actualizacion"))
        append_rows("pp_planeaciones", "planeacion-pedagogica", "Planeación pedagógica", ("unidad",), ("tema", "nombre_original"), ("ruta_archivo",), ("fecha_carga", "fecha_creacion", "fecha_actualizacion"))
        append_rows("pp_documentos_generados", "planeacion-pedagogica", "Documento pedagógico generado", ("unidad",), ("nombre", "nombre_original"), ("ruta_archivo",), ("fecha_generacion",))
        append_rows("sn_entregables_mes", "salud-nutricion", "Entregable Salud y Nutrición", ("uds",), ("codigo",), (), ("fecha_actualizacion", "fecha_creacion"))
        append_rows("sn_productos_actividad", "salud-nutricion", "Producto Salud y Nutrición", (), ("nombre_archivo", "tipo_producto"), ("ruta_archivo",), ("fecha_generacion",))
        append_rows("sn_evidencias_integrales", "salud-nutricion", "Evidencia Salud y Nutrición", (), ("titulo", "nombre_original"), ("ruta_archivo",), ("fecha_carga",), ())
        append_rows("cuentas_cobro_generadas", "cuentas-cobro", "Cuenta de cobro", ("unidad",), ("nombre_archivo",), ("ruta_archivo",), ("fecha_generacion",), ())
        append_rows("entregables_operacion", "cumplimiento", "Entregable operativo", ("unidad",), ("tipo", "categoria"), ("ruta_archivo",), ("fecha_carga", "fecha_limite"))
        append_rows("fcr_evidencias", "familias-redes", "Evidencia Familia y Redes", ("unidad_nombre", "unidad_clave"), ("titulo", "nombre_original"), ("ruta_archivo",), ("fecha_carga",), ())
        append_rows("fcr_documentos_generados", "familias-redes", "Documento Familia y Redes", ("unidad_nombre", "unidad_clave"), ("nombre_archivo", "tipo_documento"), ("ruta_archivo",), ("fecha_generacion",))
        append_rows("csc_evidencias", "supervision-calidad", "Evidencia de supervisión", ("unidad_nombre", "unidad_clave"), ("nombre_original", "descripcion"), ("ruta_archivo",), ("fecha_carga",), ())
        append_rows("csc_productos", "supervision-calidad", "Producto de supervisión", ("unidad_nombre", "unidad_clave"), ("nombre_archivo", "tipo_producto"), ("ruta_archivo",), ("fecha_generacion",))

        # Documentos pedagógicos requieren la unidad del entregable padre.
        if self.table_exists(conn, "gp_documentos") and self.table_exists(conn, "gp_entregables"):
            dcols, ecols = self.columns(conn, "gp_documentos"), self.columns(conn, "gp_entregables")
            if {"id", "entregable_id"} <= dcols and {"id", "unidad"} <= ecols:
                where = []
                params: list[Any] = []
                if "fundacion_id" in dcols:
                    where.append("d.fundacion_id=?")
                    params.append(fundacion_id)
                elif "fundacion_id" in ecols:
                    where.append("e.fundacion_id=?")
                    params.append(fundacion_id)
                if "activo" in dcols:
                    where.append("COALESCE(d.activo,1)=1")
                select = ["d.id", "e.unidad", "d.nombre_original", "d.nombre_guardado", "d.ruta_archivo", "d.estado", "d.version", "d.fecha_carga"]
                try:
                    rows = [dict(row) for row in conn.execute(f"SELECT {','.join(select)} FROM gp_documentos d JOIN gp_entregables e ON e.id=d.entregable_id" + (" WHERE " + " AND ".join(where) if where else ""), params).fetchall()]
                except sqlite3.Error:
                    rows = []
                for row in rows:
                    if not self._matches_unit(row, unit_name, unit_code, ("unidad",)):
                        continue
                    docs.append({
                        "source_module": "gestion-pedagogica", "source_table": "gp_documentos", "source_id": row.get("id"),
                        "categoria": "Documento pedagógico", "titulo": row.get("nombre_original") or f"Documento #{row.get('id')}",
                        "estado": row.get("estado"), "fecha_documento": _date_value(row.get("fecha_carga")),
                        "file_name": row.get("nombre_original") or row.get("nombre_guardado"), "file_path": row.get("ruta_archivo"),
                        "mime_type": None, "sha256": None, "version": row.get("version"),
                    })

        # Adjuntos de Salud y Nutrición se filtran por la valoración padre.
        if self.table_exists(conn, "sn_adjuntos") and self.table_exists(conn, "sn_valoraciones"):
            acols, vcols = self.columns(conn, "sn_adjuntos"), self.columns(conn, "sn_valoraciones")
            if {"id", "valoracion_id"} <= acols and {"id", "unidad"} <= vcols:
                where = ["v.fundacion_id=?"] if "fundacion_id" in vcols else []
                params = [fundacion_id] if where else []
                try:
                    rows = [dict(row) for row in conn.execute(
                        "SELECT a.id,v.unidad,a.nombre_original,a.nombre_guardado,a.ruta_archivo,a.tipo,a.estado,a.fecha_carga "
                        "FROM sn_adjuntos a JOIN sn_valoraciones v ON v.id=a.valoracion_id" + (" WHERE " + " AND ".join(where) if where else ""), params).fetchall()]
                except sqlite3.Error:
                    rows = []
                for row in rows:
                    if self._matches_unit(row, unit_name, unit_code, ("unidad",)):
                        docs.append({
                            "source_module": "salud-nutricion", "source_table": "sn_adjuntos", "source_id": row.get("id"),
                            "categoria": row.get("tipo") or "Adjunto Salud y Nutrición", "titulo": row.get("nombre_original") or f"Adjunto #{row.get('id')}",
                            "estado": row.get("estado"), "fecha_documento": _date_value(row.get("fecha_carga")),
                            "file_name": row.get("nombre_original") or row.get("nombre_guardado"), "file_path": row.get("ruta_archivo"),
                            "mime_type": None, "sha256": None, "version": None,
                        })

        # Archivos de entregables de Salud y Nutrición se filtran por UDS padre.
        if self.table_exists(conn, "sn_entregables_archivos") and self.table_exists(conn, "sn_entregables_mes"):
            try:
                rows = [dict(row) for row in conn.execute(
                    "SELECT a.id,m.uds,m.fundacion_id,m.codigo,a.tipo,a.nombre_archivo,a.ruta_archivo,a.estado,a.fecha_generacion "
                    "FROM sn_entregables_archivos a JOIN sn_entregables_mes m ON m.id=a.entregable_id WHERE m.fundacion_id=?",
                    (fundacion_id,),
                ).fetchall()]
            except sqlite3.Error:
                rows = []
            for row in rows:
                if self._matches_unit(row, unit_name, unit_code, ("uds",)):
                    docs.append({
                        "source_module": "salud-nutricion", "source_table": "sn_entregables_archivos", "source_id": row.get("id"),
                        "categoria": row.get("tipo") or "Entregable Salud y Nutrición", "titulo": row.get("nombre_archivo") or row.get("codigo"),
                        "estado": row.get("estado"), "fecha_documento": _date_value(row.get("fecha_generacion")),
                        "file_name": row.get("nombre_archivo"), "file_path": row.get("ruta_archivo"), "mime_type": None,
                        "sha256": None, "version": None,
                    })

        # Documentos y evidencias de Familia, Comunidad y Redes, vinculados por su actividad/compromiso/alerta fuente.
        if self.table_exists(conn, "fcr_documentos_generados") and self.table_exists(conn, "fcr_actividades"):
            try:
                rows = [dict(row) for row in conn.execute(
                    "SELECT d.id,a.unidad_nombre,a.unidad_clave,d.tipo_documento,d.nombre_archivo,d.ruta_archivo,d.mime_type,d.sha256,d.estado,d.fecha_generacion "
                    "FROM fcr_documentos_generados d JOIN fcr_actividades a ON a.id=d.actividad_id AND a.fundacion_id=d.fundacion_id WHERE d.fundacion_id=?",
                    (fundacion_id,),
                ).fetchall()]
            except sqlite3.Error:
                rows = []
            for row in rows:
                if self._matches_unit(row, unit_name, unit_code, ("unidad_nombre", "unidad_clave")):
                    docs.append({"source_module":"familias-redes","source_table":"fcr_documentos_generados","source_id":row.get("id"),"categoria":row.get("tipo_documento") or "Documento Familia y Redes","titulo":row.get("nombre_archivo"),"estado":row.get("estado"),"fecha_documento":_date_value(row.get("fecha_generacion")),"file_name":row.get("nombre_archivo"),"file_path":row.get("ruta_archivo"),"mime_type":row.get("mime_type"),"sha256":row.get("sha256"),"version":None})

        if self.table_exists(conn, "fcr_evidencias"):
            try:
                rows = [dict(row) for row in conn.execute(
                    """SELECT e.id,COALESCE(a.unidad_nombre,c.unidad_nombre,al.unidad_nombre,fr.unidad_nombre) unidad_nombre,
                    COALESCE(a.unidad_clave,c.unidad_clave,al.unidad_clave,fr.unidad_clave) unidad_clave,e.tipo,e.titulo,
                    e.nombre_original,e.ruta_archivo,e.mime_type,e.sha256,e.version,e.fecha_carga
                    FROM fcr_evidencias e
                    LEFT JOIN fcr_actividades a ON a.id=e.actividad_id AND a.fundacion_id=e.fundacion_id
                    LEFT JOIN fcr_compromisos c ON c.id=e.compromiso_id AND c.fundacion_id=e.fundacion_id
                    LEFT JOIN fcr_alertas al ON al.id=e.alerta_id AND al.fundacion_id=e.fundacion_id
                    LEFT JOIN fcr_expedientes_familiares fr ON fr.id=e.expediente_familiar_id AND fr.fundacion_id=e.fundacion_id
                    WHERE e.fundacion_id=? AND COALESCE(e.activo,1)=1""",
                    (fundacion_id,),
                ).fetchall()]
            except sqlite3.Error:
                rows = []
            for row in rows:
                if self._matches_unit(row, unit_name, unit_code, ("unidad_nombre", "unidad_clave")):
                    docs.append({"source_module":"familias-redes","source_table":"fcr_evidencias","source_id":row.get("id"),"categoria":row.get("tipo") or "Evidencia Familia y Redes","titulo":row.get("titulo") or row.get("nombre_original"),"estado":"VIGENTE","fecha_documento":_date_value(row.get("fecha_carga")),"file_name":row.get("nombre_original"),"file_path":row.get("ruta_archivo"),"mime_type":row.get("mime_type"),"sha256":row.get("sha256"),"version":row.get("version")})

        if self.table_exists(conn, "csc_productos") and self.table_exists(conn, "csc_supervisiones"):
            try:
                rows = [dict(row) for row in conn.execute(
                    "SELECT p.id,s.unidad_nombre,s.unidad_clave,p.tipo_producto,p.nombre_archivo,p.ruta_archivo,p.mime_type,p.sha256,p.estado,p.fecha_generacion "
                    "FROM csc_productos p JOIN csc_supervisiones s ON s.id=p.supervision_id AND s.fundacion_id=p.fundacion_id WHERE p.fundacion_id=?",
                    (fundacion_id,),
                ).fetchall()]
            except sqlite3.Error:
                rows = []
            for row in rows:
                if self._matches_unit(row, unit_name, unit_code, ("unidad_nombre", "unidad_clave")):
                    docs.append({"source_module":"supervision-calidad","source_table":"csc_productos","source_id":row.get("id"),"categoria":row.get("tipo_producto") or "Producto de supervisión","titulo":row.get("nombre_archivo"),"estado":row.get("estado"),"fecha_documento":_date_value(row.get("fecha_generacion")),"file_name":row.get("nombre_archivo"),"file_path":row.get("ruta_archivo"),"mime_type":row.get("mime_type"),"sha256":row.get("sha256"),"version":None})

        if self.table_exists(conn, "csc_evidencias"):
            try:
                rows = [dict(row) for row in conn.execute(
                    """SELECT e.id,e.entidad_tipo,e.entidad_id,e.nombre_original,e.ruta_archivo,e.mime_type,e.sha256,e.version,e.descripcion,e.fecha_carga,
                    COALESCE(s.unidad_nombre,sv.unidad_nombre,h.unidad_nombre,p.unidad_nombre,pa.unidad_nombre) unidad_nombre,
                    COALESCE(s.unidad_clave,sv.unidad_clave,h.unidad_clave,p.unidad_clave,pa.unidad_clave) unidad_clave
                    FROM csc_evidencias e
                    LEFT JOIN csc_supervisiones s ON e.entidad_tipo='SUPERVISION' AND s.id=e.entidad_id AND s.fundacion_id=e.fundacion_id
                    LEFT JOIN csc_verificaciones v ON e.entidad_tipo='VERIFICACION' AND v.id=e.entidad_id AND v.fundacion_id=e.fundacion_id
                    LEFT JOIN csc_supervisiones sv ON sv.id=v.supervision_id AND sv.fundacion_id=e.fundacion_id
                    LEFT JOIN csc_hallazgos h ON e.entidad_tipo='HALLAZGO' AND h.id=e.entidad_id AND h.fundacion_id=e.fundacion_id
                    LEFT JOIN csc_planes_mejora p ON e.entidad_tipo='PLAN' AND p.id=e.entidad_id AND p.fundacion_id=e.fundacion_id
                    LEFT JOIN csc_acciones_mejora ac ON e.entidad_tipo='ACCION' AND ac.id=e.entidad_id AND ac.fundacion_id=e.fundacion_id
                    LEFT JOIN csc_planes_mejora pa ON pa.id=ac.plan_id AND pa.fundacion_id=e.fundacion_id
                    WHERE e.fundacion_id=?""",
                    (fundacion_id,),
                ).fetchall()]
            except sqlite3.Error:
                rows = []
            for row in rows:
                if self._matches_unit(row, unit_name, unit_code, ("unidad_nombre", "unidad_clave")):
                    docs.append({"source_module":"supervision-calidad","source_table":"csc_evidencias","source_id":row.get("id"),"categoria":f"Evidencia {row.get('entidad_tipo') or 'Supervisión'}","titulo":row.get("descripcion") or row.get("nombre_original"),"estado":"VIGENTE","fecha_documento":_date_value(row.get("fecha_carga")),"file_name":row.get("nombre_original"),"file_path":row.get("ruta_archivo"),"mime_type":row.get("mime_type"),"sha256":row.get("sha256"),"version":row.get("version")})

        unique: dict[tuple[str, int], dict[str, Any]] = {}
        for doc in docs:
            source_id = int(doc.get("source_id") or 0)
            if source_id <= 0:
                continue
            unique[(str(doc.get("source_table")), source_id)] = doc
        result = list(unique.values())
        result.sort(key=lambda item: (item.get("fecha_documento") or "", str(item.get("titulo") or "")), reverse=True)
        return result[: max(1, min(limit, 1000))]

    def alerts(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None, schedule: list[dict[str, Any]], limit: int = 100) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for row in self._scoped_rows(conn, "sn_alertas", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "unidad", "tipo", "nivel", "mensaje", "fecha_alerta", "atendida"), extra_where="COALESCE(atendida,0)=0" if "atendida" in self.columns(conn, "sn_alertas") else None):
            alerts.append({"source_table": "sn_alertas", "source_id": row.get("id"), "componente": "Salud y Nutrición", "tipo": row.get("tipo"), "nivel": row.get("nivel") or "AMARILLO", "mensaje": row.get("mensaje"), "fecha": _date_value(row.get("fecha_alerta")), "seccion": "salud-nutricion"})
        for row in self._scoped_rows(conn, "master_inconsistencias", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, fields=("id", "unidad_servicio", "severidad", "tipo", "descripcion", "resuelta", "fecha_creacion"), extra_where="COALESCE(resuelta,0)=0" if "resuelta" in self.columns(conn, "master_inconsistencias") else None):
            alerts.append({"source_table": "master_inconsistencias", "source_id": row.get("id"), "componente": "Base Maestra", "tipo": row.get("tipo") or "INCONSISTENCIA", "nivel": row.get("severidad") or "AMARILLO", "mensaje": row.get("descripcion"), "fecha": _date_value(row.get("fecha_creacion")), "seccion": "calidad-datos"})
        for row in self._scoped_rows(conn, "fcr_alertas", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "tipo", "nivel", "descripcion", "fecha_identificacion", "estado")):
            if _state(row.get("estado")) not in _COMPLETE_STATES:
                alerts.append({"source_table": "fcr_alertas", "source_id": row.get("id"), "componente": "Familia, Comunidad y Redes Sociales", "tipo": row.get("tipo") or "ALERTA", "nivel": row.get("nivel") or "AMARILLO", "mensaje": row.get("descripcion"), "fecha": _date_value(row.get("fecha_identificacion")), "seccion": "familias-redes"})
        for row in self._scoped_rows(conn, "csc_hallazgos", fundacion_id=fundacion_id, unit_name=unit_name, unit_code=unit_code, unit_columns=("unidad_nombre", "unidad_clave"), fields=("id", "unidad_nombre", "unidad_clave", "titulo", "descripcion", "nivel_riesgo", "fecha_deteccion", "estado")):
            if _state(row.get("estado")) not in {"CERRADO", "DESCARTADO"}:
                alerts.append({"source_table": "csc_hallazgos", "source_id": row.get("id"), "componente": "Supervisión, Auditoría y Calidad", "tipo": "HALLAZGO", "nivel": row.get("nivel_riesgo") or "AMARILLO", "mensaje": row.get("titulo") or row.get("descripcion"), "fecha": _date_value(row.get("fecha_deteccion")), "seccion": "supervision-calidad"})
        for item in schedule:
            if item.get("vencida"):
                alerts.append({"source_table": item.get("source_table"), "source_id": item.get("source_id"), "componente": "Cronograma", "tipo": "VENCIMIENTO", "nivel": "ROJO", "mensaje": f"Actividad vencida: {item.get('titulo')}", "fecha": item.get("fecha"), "seccion": item.get("seccion")})
        severity = {"CRITICO": 0, "CRITICA": 0, "ROJO": 1, "ALTO": 1, "AMARILLO": 2, "MEDIO": 2, "VERDE": 3, "BAJO": 3}
        alerts.sort(key=lambda item: (severity.get(normalize_text(item.get("nivel")), 2), item.get("fecha") or "9999-12-31"))
        return alerts[: max(1, min(limit, 500))]

    def _reporting(self, conn: sqlite3.Connection, fundacion_id: int, unit_name: str, unit_code: str | None) -> dict[str, Any]:
        reports = self._foundation_rows(conn, "rg_reportes", fundacion_id=fundacion_id, fields=("id", "periodo", "tipo", "estado", "total_indicadores", "total_hallazgos", "total_alertas", "total_pendientes", "fecha_generacion"), limit=1000)
        packages = self._foundation_rows(conn, "pm_paquetes", fundacion_id=fundacion_id, fields=("id", "periodo", "estado", "total_archivos", "tamano_bytes", "fecha_creacion"), limit=1000)
        return {"reportes_gerenciales": len(reports), "paquetes_mensuales": len(packages), "ultimo_reporte": max((row.get("fecha_generacion") or "" for row in reports), default=None), "ultimo_paquete": max((row.get("fecha_creacion") or "" for row in packages), default=None), "alcance": "FUNDACION", "fuentes": ["rg_reportes", "pm_paquetes"]}

    def source_status(self, conn: sqlite3.Connection, fundacion_id: int) -> list[dict[str, Any]]:
        tables = [
            "master_ninos", "master_inconsistencias", "gp_entregables", "pp_planeaciones", "sn_valoraciones",
            "sn_alertas", "sn_entregables_mes", "th_personas", "th_asignaciones", "calendario_entregables",
            "rg_reportes", "plantillas_oficiales_versiones", "fcr_expedientes_familiares", "fcr_actividades",
            "fcr_compromisos", "fcr_alertas", "fcr_redes_apoyo", "csc_supervisiones", "csc_hallazgos",
            "csc_planes_mejora", "csc_acciones_mejora", "csc_productos",
            "cpo_actividad_metadata", "cpo_dependencias", "cpo_documentos_preparados",
            "ps_expedientes", "ps_caracterizaciones", "ps_planes_acompanamiento", "ps_acciones_plan",
        ]
        result = []
        for table in tables:
            exists = self.table_exists(conn, table)
            cols = self.columns(conn, table) if exists else set()
            total = 0
            if exists:
                where = " WHERE fundacion_id=?" if "fundacion_id" in cols else ""
                params = (fundacion_id,) if where else ()
                try:
                    total = int(conn.execute(f"SELECT COUNT(*) FROM {_ident(table)}{where}", params).fetchone()[0] or 0)
                except sqlite3.Error:
                    total = 0
            result.append({"tabla": table, "disponible": exists, "registros_fundacion": total})
        return result

    def build_view(self, expediente: dict[str, Any]) -> dict[str, Any]:
        fundacion_id = int(expediente["fundacion_id"])
        unit_name = str(expediente["unidad_nombre"])
        unit_code = expediente.get("codigo_unidad")
        conn = self.connect()
        try:
            base = self._participants(conn, fundacion_id, unit_name, unit_code)
            pedagogy = self._pedagogy(conn, fundacion_id, unit_name, unit_code)
            health = self._health(conn, fundacion_id, unit_name, unit_code, int(base.get("total_participantes") or 0))
            formats = self._formats(conn, fundacion_id, unit_name, unit_code)
            talent = self._talent(conn, fundacion_id, unit_name, unit_code)
            families = self._families_networks(conn, fundacion_id, unit_name, unit_code)
            supervision = self._supervision_quality(conn, fundacion_id, unit_name, unit_code)
            planning = self._planning_center(conn, fundacion_id, unit_name, unit_code)
            psychosocial = self._psychosocial(conn, fundacion_id, unit_name, unit_code)
            schedule = self.schedule(conn, fundacion_id, unit_name, unit_code)
            documents = self.documents(conn, fundacion_id, unit_name, unit_code)
            alerts = self.alerts(conn, fundacion_id, unit_name, unit_code, schedule)
            reporting = self._reporting(conn, fundacion_id, unit_name, unit_code)
            sources = self.source_status(conn, fundacion_id)
        finally:
            conn.close()

        document_score = 100.0 if documents else 0.0
        schedule_total = len(schedule)
        schedule_overdue = sum(1 for item in schedule if item.get("vencida"))
        schedule_score = round(((schedule_total - schedule_overdue) / schedule_total) * 100, 2) if schedule_total else 100.0
        components = {
            "base_maestra": base,
            "pedagogico": pedagogy,
            "salud_nutricion": health,
            "ram_rpp_bienestarina": formats,
            "talento_humano": talent,
            "familias_redes": families,
            "supervision_calidad": supervision,
            "planeacion_operativa": planning,
            "psicosocial": psychosocial,
            "documentos_evidencias": {"documentos_vinculados": len(documents), "semaforo": self._semaphore(document_score) if documents else "AMARILLO", "fuentes": sorted({doc["source_table"] for doc in documents})},
            "cronograma": {"actividades": schedule_total, "vencidas": schedule_overdue, "cumplimiento_porcentaje": schedule_score, "semaforo": self._semaphore(schedule_score), "fuentes": sorted({str(item.get("source_table")) for item in schedule})},
            "reportes_indicadores": {**reporting, "semaforo": "VERDE" if reporting["reportes_gerenciales"] or reporting["paquetes_mensuales"] else "AMARILLO"},
        }
        component_meta = {item.key: item for item in COMPONENTS}
        component_list = []
        for key, metrics in components.items():
            meta = component_meta[key]
            component_list.append({"codigo": key, "nombre": meta.label, "descripcion": meta.description, "seccion": meta.section, "metricas": metrics, "semaforo": metrics.get("semaforo", "GRIS")})

        indicators = [
            {"codigo": "UCA_PARTICIPANTES", "nombre": "Participantes activos", "valor": base["total_participantes"], "unidad": "personas", "semaforo": "VERDE" if base["total_participantes"] else "ROJO", "fuente": "master_ninos"},
            {"codigo": "UCA_CALIDAD_DATOS", "nombre": "Calidad de Base Maestra", "valor": base["calidad_porcentaje"], "unidad": "%", "semaforo": base["semaforo"], "fuente": "master_ninos"},
            {"codigo": "UCA_COBERTURA_VALORACION", "nombre": "Cobertura de valoración nutricional", "valor": health["cobertura_valoracion_porcentaje"], "unidad": "%", "semaforo": self._semaphore(health["cobertura_valoracion_porcentaje"]) if base["total_participantes"] else "GRIS", "fuente": "sn_valoraciones"},
            {"codigo": "UCA_CUMPLIMIENTO_PEDAGOGICO", "nombre": "Cumplimiento pedagógico", "valor": pedagogy["cumplimiento_porcentaje"], "unidad": "%", "semaforo": pedagogy["semaforo"], "fuente": "gp_entregables/pp_planeaciones"},
            {"codigo": "UCA_TALENTO_ACTIVO", "nombre": "Talento humano activo", "valor": talent["personas_activas"], "unidad": "personas", "semaforo": talent["semaforo"], "fuente": "th_personas"},
            {"codigo": "UCA_FAMILIAS_ACOMPANADAS", "nombre": "Expedientes familiares activos", "valor": families["expedientes_familiares"], "unidad": "familias", "semaforo": families["semaforo"], "fuente": "fcr_expedientes_familiares"},
            {"codigo": "UCA_HALLAZGOS_SUPERVISION", "nombre": "Hallazgos de supervisión abiertos", "valor": supervision["hallazgos_abiertos"], "unidad": "hallazgos", "semaforo": supervision["semaforo"], "fuente": "csc_hallazgos"},
            {"codigo": "UCA_PLANEACION_OPERATIVA", "nombre": "Cumplimiento de planeación operativa", "valor": planning["cumplimiento_porcentaje"], "unidad": "%", "semaforo": planning["semaforo"], "fuente": "cpo_actividad_metadata"},
            {"codigo": "UCA_COBERTURA_PSICOSOCIAL", "nombre": "Cobertura de caracterización psicosocial", "valor": psychosocial["cumplimiento_porcentaje"], "unidad": "%", "semaforo": psychosocial["semaforo"], "fuente": "ps_caracterizaciones"},
            {"codigo": "UCA_ALERTAS_ABIERTAS", "nombre": "Alertas abiertas", "valor": len(alerts), "unidad": "alertas", "semaforo": "VERDE" if not alerts else ("AMARILLO" if len(alerts) <= 3 else "ROJO"), "fuente": "agregación transversal"},
            {"codigo": "UCA_CRONOGRAMA", "nombre": "Cumplimiento del cronograma", "valor": schedule_score, "unidad": "%", "semaforo": self._semaphore(schedule_score), "fuente": "calendario"},
        ]
        blockers: list[str] = []
        if not base["total_participantes"]:
            blockers.append("La UCA no tiene participantes activos en la Base Maestra.")
        if base["inconsistencias_abiertas"]:
            blockers.append(f"Existen {base['inconsistencias_abiertas']} inconsistencias de datos sin resolver.")
        if health["alertas_abiertas"]:
            blockers.append(f"Existen {health['alertas_abiertas']} alertas de Salud y Nutrición abiertas.")
        if schedule_overdue:
            blockers.append(f"Existen {schedule_overdue} actividades o entregables vencidos.")
        if families["alertas_abiertas"]:
            blockers.append(f"Existen {families['alertas_abiertas']} alertas de Familia, Comunidad y Redes abiertas.")
        if supervision["hallazgos_abiertos"]:
            blockers.append(f"Existen {supervision['hallazgos_abiertos']} hallazgos de supervisión abiertos.")
        if planning["bloqueadas"]:
            blockers.append(f"Existen {planning['bloqueadas']} actividades de planeación bloqueadas por dependencias.")
        if psychosocial["acciones_pendientes"]:
            blockers.append(f"Existen {psychosocial['acciones_pendientes']} acciones psicosociales pendientes.")
        if not documents:
            blockers.append("No se encontraron documentos o evidencias vinculables a esta UCA.")
        readiness_scores = [
            base["calidad_porcentaje"],
            health["cobertura_valoracion_porcentaje"] if base["total_participantes"] else 0,
            pedagogy["cumplimiento_porcentaje"],
            100.0 if talent["personas_activas"] else 0.0,
            families["cumplimiento_porcentaje"],
            supervision["cumplimiento_porcentaje"],
            planning["cumplimiento_porcentaje"],
            psychosocial["cumplimiento_porcentaje"],
            schedule_score,
            100.0 if documents else 50.0,
        ]
        readiness = round(sum(readiness_scores) / len(readiness_scores), 2)
        return {
            "expediente_id": expediente.get("id"),
            "fundacion_id": fundacion_id,
            "unidad": {"nombre": unit_name, "codigo": unit_code, "vigencia": expediente.get("vigencia"), "contrato": expediente.get("contrato"), "modalidad": expediente.get("servicio_modalidad"), "fase_actual": expediente.get("fase_actual")},
            "componentes": component_list,
            "indicadores": indicators,
            "alertas": alerts,
            "cronograma": schedule,
            "documentos": documents,
            "preparacion_supervision": {"porcentaje": readiness, "semaforo": self._semaphore(readiness), "bloqueos": blockers, "lista_para_paquete": not any("no tiene participantes" in item.lower() for item in blockers)},
            "fuentes": sources,
            "generado_en": now_iso(),
            "principio": "Lectura integrada y referencias; no se duplican registros operativos.",
        }
