"""Repositorio SQLite del Calendario Inteligente de Entregables."""
from __future__ import annotations

import os
import json
from modules.dbapi_compat import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .services import (
    ESTADOS_PERMITIDOS,
    MODULOS_PERMITIDOS,
    calcular_estado_color,
    canonical_modulo,
    clave_unica_entregable,
    detectar_columnas,
    parse_fecha,
    row_to_payload,
    leer_cronograma_flexible,
    construir_preview_cronograma,
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CalendarioInteligenteRepository:
    def __init__(self, database_path: str, upload_folder: str | None = None):
        self.database_path = database_path
        self.upload_folder = upload_folder

    def connect(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendario_entregables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    descripcion TEXT,
                    fecha_inicio TEXT,
                    fecha_limite TEXT NOT NULL,
                    modulo TEXT,
                    tipo_formato TEXT,
                    responsable_id INTEGER,
                    responsable_nombre TEXT,
                    coordinador TEXT,
                    unidad TEXT,
                    municipio TEXT,
                    estado TEXT DEFAULT 'pendiente',
                    prioridad TEXT DEFAULT 'Media',
                    color TEXT DEFAULT 'azul',
                    requiere_evidencia INTEGER DEFAULT 0,
                    archivo_evidencia TEXT,
                    fecha_entrega TEXT,
                    observaciones TEXT,
                    creado_por TEXT,
                    fecha_creacion TEXT,
                    actualizado_en TEXT,
                    fundacion_id INTEGER DEFAULT 1,
                    usuario_creador_id INTEGER,
                    clave_unica TEXT,
                    origen TEXT DEFAULT 'manual'
                )
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_calendario_entregables_clave ON calendario_entregables(clave_unica)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calendario_fecha ON calendario_entregables(fecha_limite)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calendario_coordinador ON calendario_entregables(coordinador)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calendario_unidad ON calendario_entregables(unidad)")

            # ALPHA33: tablas auxiliares para flujo de cronograma revisable antes de guardar.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendario_cronogramas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_archivo TEXT,
                    archivo_guardado TEXT,
                    periodo TEXT,
                    estado TEXT DEFAULT 'preview',
                    total_detectadas INTEGER DEFAULT 0,
                    total_validas INTEGER DEFAULT 0,
                    total_invalidas INTEGER DEFAULT 0,
                    requiere_revision INTEGER DEFAULT 1,
                    preview_json TEXT,
                    usuario_carga TEXT,
                    fecha_carga TEXT,
                    fecha_confirmacion TEXT,
                    confirmado_por TEXT,
                    fundacion_id INTEGER DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendario_actividades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cronograma_id INTEGER,
                    entregable_id INTEGER,
                    fecha TEXT,
                    titulo TEXT,
                    descripcion TEXT,
                    responsable TEXT,
                    coordinador TEXT,
                    unidad TEXT,
                    modulo TEXT,
                    estado TEXT DEFAULT 'programado',
                    prioridad TEXT DEFAULT 'Media',
                    observacion TEXT,
                    archivo_origen TEXT,
                    usuario_carga TEXT,
                    fecha_carga TEXT,
                    fecha_entrega TEXT,
                    entregado_por TEXT,
                    soporte_path TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    clave_unica TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ci_actividades_fecha ON calendario_actividades(fecha)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ci_actividades_cronograma ON calendario_actividades(cronograma_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendario_entregas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actividad_id INTEGER,
                    entregable_id INTEGER,
                    fecha_entrega TEXT,
                    entregado_por TEXT,
                    soporte_path TEXT,
                    observaciones TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendario_alertas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entregable_id INTEGER,
                    fecha TEXT,
                    nivel TEXT,
                    mensaje TEXT,
                    estado TEXT DEFAULT 'activa',
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendario_archivos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cronograma_id INTEGER,
                    nombre_original TEXT,
                    nombre_guardado TEXT,
                    ruta TEXT,
                    tipo TEXT,
                    usuario_carga TEXT,
                    fecha_carga TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendario_auditoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accion TEXT,
                    referencia_tipo TEXT,
                    referencia_id INTEGER,
                    detalle TEXT,
                    usuario TEXT,
                    created_at TEXT
                )
                """
            )
            conn.commit()

    def _row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        data = dict(row)
        estado, color, dias = calcular_estado_color(data.get("fecha_limite"), data.get("estado"))
        # No sobrescribe entregado/aprobado/no_aplica/cerrado. Sí actualiza estado visual en salida.
        data["estado_calculado"] = estado
        data["color_calculado"] = color
        data["dias_restantes"] = dias
        data["color"] = data.get("color") or color
        if data.get("estado") not in {"entregado", "aprobado", "no_aplica", "cerrado", "rechazado"}:
            data["estado"] = estado
            data["color"] = color
        return data

    def _rows(self, rows) -> list[dict[str, Any]]:
        return [self._row(r) for r in rows]

    def _build_where(self, filters: dict[str, Any]) -> tuple[str, list[Any]]:
        where = ["1=1"]
        params: list[Any] = []
        periodo = filters.get("periodo")
        anio = filters.get("anio")
        if periodo:
            where.append("substr(fecha_limite, 1, 7) = ?")
            params.append(str(periodo)[:7])
        elif anio:
            where.append("substr(fecha_limite, 1, 4) = ?")
            params.append(str(anio)[:4])
        for field in ["coordinador", "unidad", "modulo", "estado", "responsable_nombre", "municipio"]:
            value = filters.get(field)
            if value:
                if field in {"coordinador", "unidad", "modulo", "responsable_nombre", "municipio"}:
                    where.append(f"LOWER(COALESCE({field}, '')) LIKE LOWER(?)")
                    params.append(f"%{value}%")
                else:
                    where.append(f"{field} = ?")
                    params.append(value)
        fecha = filters.get("fecha")
        if fecha:
            where.append("fecha_limite = ?")
            params.append(parse_fecha(fecha) or fecha)
        return " AND ".join(where), params

    def list_entregables(self, filters: dict[str, Any] | None = None, limit: int = 500) -> list[dict[str, Any]]:
        filters = filters or {}
        where, params = self._build_where(filters)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM calendario_entregables WHERE {where} ORDER BY fecha_limite ASC, prioridad DESC, modulo ASC, unidad ASC LIMIT ?",
                params + [limit],
            ).fetchall()
        return self._rows(rows)

    def get_entregable(self, entregable_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM calendario_entregables WHERE id=?", (entregable_id,)).fetchone()
        return self._row(row)

    def create_entregable(self, data: dict[str, Any], origen: str = "manual") -> dict[str, Any]:
        payload = self._prepare_payload(data, origen=origen)
        fields = [
            "titulo", "descripcion", "fecha_inicio", "fecha_limite", "modulo", "tipo_formato", "responsable_id",
            "responsable_nombre", "coordinador", "unidad", "municipio", "estado", "prioridad", "color",
            "requiere_evidencia", "archivo_evidencia", "fecha_entrega", "observaciones", "creado_por", "fecha_creacion",
            "actualizado_en", "fundacion_id", "usuario_creador_id", "clave_unica", "origen",
        ]
        values = [payload.get(f) for f in fields]
        placeholders = ",".join("?" for _ in fields)
        with self.connect() as conn:
            try:
                cur = conn.execute(f"INSERT INTO calendario_entregables ({','.join(fields)}) VALUES ({placeholders})", values)
                conn.commit()
                new_id = cur.lastrowid
            except sqlite3.IntegrityError:
                row = conn.execute("SELECT id FROM calendario_entregables WHERE clave_unica=?", (payload["clave_unica"],)).fetchone()
                new_id = int(row["id"])
        return self.get_entregable(new_id)

    def update_entregable(self, entregable_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_entregable(entregable_id)
        if not current:
            return None
        payload = {**current, **(data or {})}
        payload = self._prepare_payload(payload, origen=current.get("origen") or "manual", keep_created=True)
        fields = [
            "titulo", "descripcion", "fecha_inicio", "fecha_limite", "modulo", "tipo_formato", "responsable_id",
            "responsable_nombre", "coordinador", "unidad", "municipio", "estado", "prioridad", "color",
            "requiere_evidencia", "archivo_evidencia", "fecha_entrega", "observaciones", "actualizado_en", "clave_unica",
        ]
        values = [payload.get(f) for f in fields] + [entregable_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE calendario_entregables SET {','.join(f + '=?' for f in fields)} WHERE id=?", values)
            conn.commit()
        return self.get_entregable(entregable_id)

    def delete_entregable(self, entregable_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM calendario_entregables WHERE id=?", (entregable_id,))
            conn.commit()
            return cur.rowcount > 0

    def _prepare_payload(self, data: dict[str, Any], origen: str = "manual", keep_created: bool = False) -> dict[str, Any]:
        now = now_iso()
        fecha_limite = parse_fecha(data.get("fecha_limite") or data.get("fecha") or data.get("fecha_entrega"))
        if not fecha_limite:
            raise ValueError("fecha_limite es obligatoria y debe ser válida.")
        fecha_inicio = parse_fecha(data.get("fecha_inicio")) or fecha_limite
        estado_input = data.get("estado") or "pendiente"
        estado, color, _dias = calcular_estado_color(fecha_limite, estado_input)
        if estado_input in {"entregado", "aprobado", "rechazado", "no_aplica", "cerrado"}:
            estado = estado_input
            color = calcular_estado_color(fecha_limite, estado_input)[1]
        modulo = canonical_modulo(data.get("modulo"), data.get("tipo_formato"))
        payload = dict(data)
        payload.update({
            "titulo": str(data.get("titulo") or data.get("actividad") or "Entregable operativo").strip(),
            "descripcion": data.get("descripcion") or data.get("observaciones") or "",
            "fecha_inicio": fecha_inicio,
            "fecha_limite": fecha_limite,
            "modulo": modulo,
            "tipo_formato": data.get("tipo_formato") or data.get("formato") or modulo,
            "responsable_id": data.get("responsable_id") or None,
            "responsable_nombre": data.get("responsable_nombre") or data.get("responsable") or "",
            "coordinador": data.get("coordinador") or "",
            "unidad": data.get("unidad") or data.get("uds") or "",
            "municipio": data.get("municipio") or "",
            "estado": estado,
            "prioridad": data.get("prioridad") or "Media",
            "color": color,
            "requiere_evidencia": 1 if str(data.get("requiere_evidencia", "0")).lower() in {"1", "true", "si", "sí", "yes"} else 0,
            "archivo_evidencia": data.get("archivo_evidencia") or None,
            "fecha_entrega": parse_fecha(data.get("fecha_entrega")) or None,
            "observaciones": data.get("observaciones") or "",
            "creado_por": data.get("creado_por") or "sistema",
            "fecha_creacion": data.get("fecha_creacion") if keep_created else now,
            "actualizado_en": now,
            "fundacion_id": data.get("fundacion_id") or 1,
            "usuario_creador_id": data.get("usuario_creador_id") or None,
            "origen": origen,
        })
        payload["clave_unica"] = data.get("clave_unica") or clave_unica_entregable(payload)
        return payload

    def import_cronograma(self, path: str, filename: str = "") -> dict[str, Any]:
        df = leer_cronograma_flexible(path, filename)
        mapping = detectar_columnas(df.columns)
        if "fecha_limite" not in mapping or "titulo" not in mapping:
            return {
                "total_filas": int(len(df)),
                "creados": 0,
                "duplicados": 0,
                "errores": [{"fila": 0, "error": "El archivo debe contener columnas de fecha y actividad/entregable."}],
                "columnas_detectadas": mapping,
            }
        creados = 0
        duplicados = 0
        errores = []
        for idx, row in df.iterrows():
            try:
                payload = row_to_payload(row, mapping)
                if not payload.get("fecha_limite"):
                    errores.append({"fila": int(idx) + 2, "error": "Fecha inválida o vacía."})
                    continue
                before = self.find_by_clave(payload["clave_unica"])
                self.create_entregable(payload, origen="excel")
                if before:
                    duplicados += 1
                else:
                    creados += 1
            except Exception as exc:
                errores.append({"fila": int(idx) + 2, "error": str(exc)})
        return {
            "total_filas": int(len(df)),
            "creados": creados,
            "duplicados": duplicados,
            "errores": errores[:50],
            "columnas_detectadas": mapping,
        }

    def registrar_preview_cronograma(self, path: str, filename: str = "", usuario: str = "sistema") -> dict[str, Any]:
        """Procesa un cronograma y guarda una vista previa editable sin crear entregables."""
        preview = construir_preview_cronograma(path, filename)
        actividades = preview.get("actividades") or []
        fechas = [a.get("fecha_limite") for a in actividades if a.get("fecha_limite")]
        periodo = (min(fechas)[:7] if fechas else date.today().isoformat()[:7])
        now = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO calendario_cronogramas (
                    nombre_archivo, archivo_guardado, periodo, estado, total_detectadas,
                    total_validas, total_invalidas, requiere_revision, preview_json,
                    usuario_carga, fecha_carga, fundacion_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    filename,
                    os.path.basename(path),
                    periodo,
                    "preview",
                    len(actividades),
                    int(preview.get("validas") or 0),
                    int(preview.get("invalidas") or 0),
                    1 if preview.get("requiere_revision") else 0,
                    json.dumps(preview, ensure_ascii=False),
                    usuario,
                    now,
                    1,
                ),
            )
            cronograma_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO calendario_archivos (cronograma_id, nombre_original, nombre_guardado, ruta, tipo, usuario_carga, fecha_carga)
                VALUES (?,?,?,?,?,?,?)
                """,
                (cronograma_id, filename, os.path.basename(path), path, "cronograma", usuario, now),
            )
            conn.execute(
                "INSERT INTO calendario_auditoria (accion, referencia_tipo, referencia_id, detalle, usuario, created_at) VALUES (?,?,?,?,?,?)",
                ("preview_cronograma", "cronograma", cronograma_id, f"Detectadas {len(actividades)} actividades", usuario, now),
            )
            conn.commit()
        preview["cronograma_id"] = cronograma_id
        preview["periodo"] = periodo
        preview["archivo"] = os.path.basename(path)
        return preview

    def confirmar_cronograma(self, cronograma_id: int, actividades: list[dict[str, Any]], usuario: str = "sistema") -> dict[str, Any]:
        """Guarda actividades revisadas en el calendario operativo."""
        creados = 0
        duplicados = 0
        errores: list[dict[str, Any]] = []
        now = now_iso()
        if not actividades:
            with self.connect() as conn:
                row = conn.execute("SELECT preview_json FROM calendario_cronogramas WHERE id=?", (cronograma_id,)).fetchone()
            if row and row["preview_json"]:
                try:
                    actividades = (json.loads(row["preview_json"]).get("actividades") or [])
                except Exception:
                    actividades = []
        for idx, item in enumerate(actividades or [], start=1):
            try:
                if not item or item.get("descartar") is True:
                    continue
                fecha = parse_fecha(item.get("fecha_limite") or item.get("fecha") or item.get("fecha_entrega"))
                titulo = str(item.get("titulo") or item.get("actividad") or "").strip()
                if not fecha or not titulo:
                    errores.append({"fila": idx, "error": "La actividad debe tener fecha y título para guardarse."})
                    continue
                payload = {
                    "fecha_limite": fecha,
                    "fecha_inicio": parse_fecha(item.get("fecha_inicio")) or fecha,
                    "titulo": titulo,
                    "descripcion": item.get("descripcion") or item.get("observaciones") or item.get("observacion") or "",
                    "responsable_nombre": item.get("responsable_nombre") or item.get("responsable") or "",
                    "coordinador": item.get("coordinador") or "",
                    "unidad": item.get("unidad") or item.get("uds") or "",
                    "modulo": item.get("modulo") or "General",
                    "tipo_formato": item.get("tipo_formato") or item.get("modulo") or "General",
                    "estado": item.get("estado") or "programado",
                    "prioridad": item.get("prioridad") or "Media",
                    "observaciones": item.get("observaciones") or item.get("observacion") or "",
                    "municipio": item.get("municipio") or "",
                    "creado_por": usuario,
                    "requiere_evidencia": item.get("requiere_evidencia", True),
                }
                prepared = self._prepare_payload(payload, origen="cronograma")
                before = self.find_by_clave(prepared["clave_unica"])
                entregable = self.create_entregable(payload, origen="cronograma")
                if before:
                    duplicados += 1
                else:
                    creados += 1
                with self.connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO calendario_actividades (
                            cronograma_id, entregable_id, fecha, titulo, descripcion, responsable,
                            coordinador, unidad, modulo, estado, prioridad, observacion, archivo_origen,
                            usuario_carga, fecha_carga, created_at, updated_at, clave_unica
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            cronograma_id,
                            entregable.get("id") if entregable else None,
                            fecha,
                            titulo,
                            payload.get("descripcion"),
                            payload.get("responsable_nombre"),
                            payload.get("coordinador"),
                            payload.get("unidad"),
                            canonical_modulo(payload.get("modulo"), payload.get("tipo_formato")),
                            entregable.get("estado") if entregable else prepared.get("estado"),
                            payload.get("prioridad"),
                            payload.get("observaciones"),
                            item.get("archivo_origen") or "cronograma",
                            usuario,
                            now,
                            now,
                            now,
                            prepared.get("clave_unica"),
                        ),
                    )
                    conn.commit()
            except Exception as exc:
                errores.append({"fila": idx, "error": str(exc)})
        with self.connect() as conn:
            conn.execute(
                "UPDATE calendario_cronogramas SET estado=?, fecha_confirmacion=?, confirmado_por=? WHERE id=?",
                ("confirmado", now, usuario, cronograma_id),
            )
            conn.execute(
                "INSERT INTO calendario_auditoria (accion, referencia_tipo, referencia_id, detalle, usuario, created_at) VALUES (?,?,?,?,?,?)",
                ("confirmar_cronograma", "cronograma", cronograma_id, f"Creados {creados}, duplicados {duplicados}, errores {len(errores)}", usuario, now),
            )
            conn.commit()
        return {
            "cronograma_id": cronograma_id,
            "creados": creados,
            "duplicados": duplicados,
            "errores": errores[:100],
            "total_recibidas": len(actividades or []),
        }

    def exportar_cronograma_excel(self, filters: dict[str, Any] | None = None) -> str:
        """Genera un Excel simple del cronograma filtrado."""
        if not self.upload_folder:
            raise ValueError("No hay carpeta de salida configurada para exportar.")
        eventos = self.list_entregables(filters or {}, limit=10000)
        out_dir = Path(self.upload_folder) / "calendario_inteligente" / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"cronograma_calendario_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        rows = []
        for e in eventos:
            rows.append({
                "Fecha": e.get("fecha_limite"),
                "Actividad": e.get("titulo"),
                "Descripción": e.get("descripcion"),
                "Responsable": e.get("responsable_nombre"),
                "Coordinador": e.get("coordinador"),
                "Unidad": e.get("unidad"),
                "Módulo": e.get("modulo"),
                "Estado": e.get("estado"),
                "Prioridad": e.get("prioridad"),
                "Observaciones": e.get("observaciones"),
            })
        pd.DataFrame(rows).to_excel(out_path, index=False)
        return str(out_path)

    def exportar_cronograma_pdf(self, filters: dict[str, Any] | None = None) -> str:
        """Genera un PDF sencillo del calendario filtrado."""
        if not self.upload_folder:
            raise ValueError("No hay carpeta de salida configurada para exportar.")
        eventos = self.list_entregables(filters or {}, limit=10000)
        out_dir = Path(self.upload_folder) / "calendario_inteligente" / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"cronograma_calendario_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        except Exception as exc:
            raise ValueError("Para exportar PDF se requiere reportlab instalado.") from exc
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(out_path), pagesize=landscape(letter), rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
        story = [Paragraph("Calendario Inteligente de Entregables", styles["Title"]), Spacer(1, 10)]
        data = [["Fecha", "Actividad", "Módulo", "Unidad", "Coordinador", "Estado"]]
        for e in eventos[:250]:
            data.append([
                str(e.get("fecha_limite") or ""),
                str(e.get("titulo") or "")[:55],
                str(e.get("modulo") or "")[:28],
                str(e.get("unidad") or "")[:28],
                str(e.get("coordinador") or "")[:28],
                str(e.get("estado") or ""),
            ])
        if len(data) == 1:
            data.append(["Sin actividades", "", "", "", "", ""])
        table = Table(data, repeatRows=1, colWidths=[70, 240, 120, 130, 130, 80])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(table)
        doc.build(story)
        return str(out_path)

    def find_by_clave(self, clave: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM calendario_entregables WHERE clave_unica=?", (clave,)).fetchone()
        return self._row(row)

    def dashboard(self, periodo: str | None = None, anio: str | None = None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        if not periodo:
            periodo = date.today().isoformat()[:7]
        filtros = {**(filters or {}), "periodo": periodo}
        eventos = self.list_entregables(filtros, limit=1000)
        annual = self.list_entregables({**(filters or {}), "anio": anio or periodo[:4]}, limit=5000)
        def count_color(*colors):
            return sum(1 for e in eventos if e.get("color") in colors or e.get("color_calculado") in colors)
        entregados = sum(1 for e in eventos if e.get("estado") in {"entregado", "aprobado"})
        resumen = {
            "entregables_mes": len(eventos),
            "proximos": count_color("amarillo", "naranja"),
            "vencidos": count_color("rojo"),
            "entregados": entregados,
            "programados": count_color("azul"),
        }
        resumen["cumplimiento_general"] = round((entregados / len(eventos)) * 100, 1) if eventos else 0
        return {
            "periodo": periodo,
            "anio": anio or periodo[:4],
            "resumen": resumen,
            "eventos": eventos,
            "annual": annual,
            "alertas": self.alertas(eventos),
            "cumplimiento_coordinador": self.cumplimiento(eventos, "coordinador"),
            "cumplimiento_modulo": self.cumplimiento(eventos, "modulo"),
            "catalogos": self.catalogos(),
        }

    def alertas(self, eventos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        alertas = []
        for e in eventos:
            color = e.get("color") or e.get("color_calculado")
            if color in {"rojo", "naranja", "amarillo"}:
                msg = f"{e.get('titulo')} de {e.get('unidad') or e.get('coordinador') or 'la plataforma'}"
                if color == "rojo":
                    msg += " está vencido o vence hoy."
                elif color == "naranja":
                    msg += " vence en 1 o 2 días."
                else:
                    msg += " está próximo a vencer."
                alertas.append({"id": e.get("id"), "nivel": color, "mensaje": msg, "fecha_limite": e.get("fecha_limite"), "modulo": e.get("modulo")})
        return alertas[:50]

    def cumplimiento(self, eventos: list[dict[str, Any]], campo: str) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, int]] = {}
        for e in eventos:
            key = str(e.get(campo) or "Sin asignar").strip() or "Sin asignar"
            buckets.setdefault(key, {"total": 0, "entregado": 0, "vencido": 0})
            buckets[key]["total"] += 1
            if e.get("estado") in {"entregado", "aprobado"}:
                buckets[key]["entregado"] += 1
            if (e.get("color") or e.get("color_calculado")) == "rojo":
                buckets[key]["vencido"] += 1
        rows = []
        for key, values in buckets.items():
            total = values["total"]
            rows.append({
                "nombre": key,
                "total": total,
                "entregados": values["entregado"],
                "vencidos": values["vencido"],
                "porcentaje": round((values["entregado"] / total) * 100, 1) if total else 0,
            })
        return sorted(rows, key=lambda x: (-x["vencidos"], x["porcentaje"], x["nombre"]))

    def catalogos(self) -> dict[str, Any]:
        with self.connect() as conn:
            coordinadores = [r[0] for r in conn.execute("SELECT DISTINCT coordinador FROM calendario_entregables WHERE COALESCE(coordinador,'')<>'' ORDER BY coordinador").fetchall()]
            unidades = [r[0] for r in conn.execute("SELECT DISTINCT unidad FROM calendario_entregables WHERE COALESCE(unidad,'')<>'' ORDER BY unidad").fetchall()]
        return {"estados": ESTADOS_PERMITIDOS, "modulos": MODULOS_PERMITIDOS, "coordinadores": coordinadores, "unidades": unidades}

    def marcar_entregado(self, entregable_id: int, archivo: str | None = None, observaciones: str | None = None) -> dict[str, Any] | None:
        data = {"estado": "entregado", "fecha_entrega": date.today().isoformat()}
        if archivo:
            data["archivo_evidencia"] = archivo
        if observaciones:
            data["observaciones"] = observaciones
        return self.update_entregable(entregable_id, data)

    def sincronizar_entrega(self, data: dict[str, Any]) -> dict[str, Any] | None:
        # Busca un entregable abierto del mismo módulo/unidad/formato en el mes; si existe, lo marca entregado.
        fecha = parse_fecha(data.get("fecha_entrega")) or date.today().isoformat()
        periodo = fecha[:7]
        modulo = canonical_modulo(data.get("modulo"), data.get("tipo_formato"))
        unidad = data.get("unidad") or ""
        eventos = self.list_entregables({"periodo": periodo, "modulo": modulo, "unidad": unidad}, limit=20)
        candidatos = [e for e in eventos if e.get("estado") not in {"entregado", "aprobado", "no_aplica", "cerrado"}]
        if candidatos:
            return self.update_entregable(candidatos[0]["id"], {"estado": "entregado", "fecha_entrega": fecha, "archivo_evidencia": data.get("archivo_evidencia")})
        payload = {
            "titulo": data.get("titulo") or f"Entrega {modulo}",
            "fecha_limite": fecha,
            "fecha_entrega": fecha,
            "estado": "entregado",
            "modulo": modulo,
            "tipo_formato": data.get("tipo_formato") or modulo,
            "unidad": unidad,
            "coordinador": data.get("coordinador") or "",
            "responsable_nombre": data.get("responsable_nombre") or "",
            "observaciones": data.get("observaciones") or "Sincronizado desde módulo operativo.",
        }
        return self.create_entregable(payload, origen="sincronizacion")
