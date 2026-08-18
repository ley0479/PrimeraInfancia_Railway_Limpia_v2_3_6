"""Proyecto pedagógico por UCA, versionado y derivado de fuentes existentes."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .repository import PlaneacionRepository, now_iso


EDIT_ROLES = {'DOCENTE', 'COORDINADOR', 'GERENTE', 'SUPERADMIN'}


def _ctx(repo: PlaneacionRepository) -> dict[str, Any]:
    return repo.context()


def _require_role(repo: PlaneacionRepository, allowed: set[str]) -> dict[str, Any]:
    ctx = _ctx(repo)
    if str(ctx.get('rol') or '').upper() not in allowed:
        raise PermissionError('El rol actual no puede realizar esta acción pedagógica.')
    return ctx


def _project_access(repo: PlaneacionRepository, alias: str = 'p') -> tuple[str, list[Any]]:
    ctx = _ctx(repo)
    role = str(ctx.get('rol') or '').upper()
    fid = int(ctx.get('fundacion_id') or 1)
    clause = f'{alias}.fundacion_id=?'
    params: list[Any] = [fid]
    if role == 'DOCENTE':
        docente_id = repo.current_docente_id()
        if not docente_id:
            return '1=0', []
        clause += f' AND {alias}.docente_id=?'
        params.append(docente_id)
    elif role == 'COORDINADOR':
        coordinador_id = repo.current_coordinator_id()
        if not coordinador_id:
            return '1=0', []
        clause += f' AND {alias}.coordinador_id=?'
        params.append(coordinador_id)
    return clause, params


def _content(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key) or ''
        for key in (
            'nombre', 'enfoque', 'diagnostico_contexto', 'objetivos', 'estrategias',
            'participacion_familias', 'enfoque_diferencial',
        )
    }


def list_projects(repo: PlaneacionRepository, vigencia: int | None = None, unidad: str | None = None) -> list[dict[str, Any]]:
    clause, params = _project_access(repo, 'p')
    if vigencia:
        clause += ' AND p.vigencia=?'
        params.append(vigencia)
    if unidad:
        clause += ' AND p.unidad=?'
        params.append(unidad)
    return repo.fetch_all(
        f"SELECT p.* FROM pp_proyectos_pedagogicos p WHERE {clause} AND p.activo=1 ORDER BY p.vigencia DESC, p.unidad, p.id DESC",
        params,
    )


def get_project(repo: PlaneacionRepository, project_id: int) -> dict[str, Any] | None:
    clause, params = _project_access(repo, 'p')
    project = repo.fetch_one(
        f"SELECT p.* FROM pp_proyectos_pedagogicos p WHERE {clause} AND p.id=? AND p.activo=1",
        params + [project_id],
    )
    if not project:
        return None
    fid = int(project['fundacion_id'])
    project['versiones'] = repo.fetch_all(
        "SELECT * FROM pp_proyecto_versiones WHERE fundacion_id=? AND proyecto_id=? ORDER BY numero_version DESC",
        (fid, project_id),
    )
    project['seguimientos'] = repo.fetch_all(
        "SELECT * FROM pp_seguimientos_pedagogicos WHERE fundacion_id=? AND proyecto_id=? AND activo=1 ORDER BY periodo DESC, id DESC",
        (fid, project_id),
    )
    return project


def create_project(repo: PlaneacionRepository, data: dict[str, Any]) -> dict[str, Any]:
    ctx = _require_role(repo, EDIT_ROLES)
    unidad = str(data.get('unidad') or '').strip()
    nombre = str(data.get('nombre') or '').strip()
    vigencia = int(data.get('vigencia') or datetime.now().year)
    if not unidad or not nombre:
        raise ValueError('UCA y nombre del proyecto pedagógico son obligatorios.')
    docente_id = data.get('docente_id') or (repo.current_docente_id() if ctx.get('rol') == 'DOCENTE' else None)
    coordinador_id = data.get('coordinador_id') or (repo.current_coordinator_id() if ctx.get('rol') == 'COORDINADOR' else None)
    fid = int(ctx.get('fundacion_id') or 1)
    now = now_iso()
    content = _content({**data, 'nombre': nombre})
    conn = repo.connect()
    try:
        existing = conn.execute(
            'SELECT id FROM pp_proyectos_pedagogicos WHERE fundacion_id=? AND unidad=? AND vigencia=? AND activo=1',
            (fid, unidad, vigencia),
        ).fetchone()
        if existing:
            raise ValueError('Ya existe un proyecto pedagógico activo para esta UCA y vigencia.')
        cur = conn.execute(
            """INSERT INTO pp_proyectos_pedagogicos
            (fundacion_id, usuario_creador_id, unidad, vigencia, nombre, enfoque, diagnostico_contexto,
             objetivos, estrategias, participacion_familias, enfoque_diferencial, estado, version_actual,
             docente_id, coordinador_id, activo, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BORRADOR', 1, ?, ?, 1, ?, ?)""",
            (fid, ctx.get('usuario_id'), unidad, vigencia, nombre, content['enfoque'], content['diagnostico_contexto'],
             content['objetivos'], content['estrategias'], content['participacion_familias'], content['enfoque_diferencial'],
             docente_id, coordinador_id, now, now),
        )
        project_id = int(cur.lastrowid)
        conn.execute(
            """INSERT INTO pp_proyecto_versiones
            (fundacion_id, usuario_creador_id, proyecto_id, numero_version, origen, estado, contenido_json,
             fuentes_json, resumen_cambios, fecha_creacion)
            VALUES (?, ?, ?, 1, 'MANUAL', 'BORRADOR', ?, ?, ?, ?)""",
            (fid, ctx.get('usuario_id'), project_id, json.dumps(content, ensure_ascii=False), '[]',
             'Versión inicial creada por usuario.', now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    repo.log('CREAR_PROYECTO_PEDAGOGICO', 'pp_proyectos_pedagogicos', project_id, nuevos={'unidad': unidad, 'vigencia': vigencia})
    return get_project(repo, project_id) or {}


def update_from_execution(repo: PlaneacionRepository, project_id: int, summary: str = '') -> dict[str, Any]:
    ctx = _require_role(repo, EDIT_ROLES)
    project = get_project(repo, project_id)
    if not project:
        raise LookupError('Proyecto pedagógico no encontrado.')
    fid = int(project['fundacion_id'])
    activities = repo.fetch_all(
        """SELECT a.id, a.planeacion_id, a.tipo_actividad, a.titulo, a.tema, a.objetivo, a.actividad,
                  a.fecha_programada, a.estado,
                  (SELECT COUNT(*) FROM pp_evidencias_planeacion e
                   WHERE e.fundacion_id=? AND e.actividad_id=a.id AND e.activo=1) AS evidencias
           FROM pp_actividades a
           WHERE a.fundacion_id=? AND a.unidad=?
             AND a.estado IN ('EJECUTADA','CUMPLIDA','CUMPLIDO','FINALIZADA')
           ORDER BY a.fecha_programada, a.id""",
        (fid, fid, project['unidad']),
    )
    latest = (project.get('versiones') or [{}])[0]
    try:
        content = json.loads(latest.get('contenido_json') or '{}')
    except (TypeError, ValueError):
        content = _content(project)
    content['actualizacion_desde_ejecucion'] = {
        'actividades_ejecutadas': len(activities),
        'temas_trabajados': sorted({str(item.get('tema') or item.get('titulo') or '').strip() for item in activities if item.get('tema') or item.get('titulo')}),
        'evidencias_vinculadas': sum(int(item.get('evidencias') or 0) for item in activities),
        'fecha_corte': now_iso(),
    }
    next_version = int(project.get('version_actual') or 0) + 1
    sources = [{'tabla': 'pp_actividades', 'id': item['id'], 'planeacion_id': item.get('planeacion_id')} for item in activities]
    now = now_iso()
    conn = repo.connect()
    try:
        conn.execute(
            """INSERT INTO pp_proyecto_versiones
            (fundacion_id, usuario_creador_id, proyecto_id, numero_version, origen, estado, contenido_json,
             fuentes_json, resumen_cambios, fecha_creacion)
            VALUES (?, ?, ?, ?, 'EJECUCION', 'BORRADOR', ?, ?, ?, ?)""",
            (fid, ctx.get('usuario_id'), project_id, next_version, json.dumps(content, ensure_ascii=False),
             json.dumps(sources, ensure_ascii=False), summary or 'Actualización derivada de actividades ejecutadas; requiere validación docente.', now),
        )
        conn.execute(
            "UPDATE pp_proyectos_pedagogicos SET version_actual=?, estado='BORRADOR_ACTUALIZACION', fecha_actualizacion=? WHERE id=? AND fundacion_id=?",
            (next_version, now, project_id, fid),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    repo.log('ACTUALIZAR_PROYECTO_DESDE_EJECUCION', 'pp_proyectos_pedagogicos', project_id, nuevos={'version': next_version, 'fuentes': len(sources)})
    return get_project(repo, project_id) or {}


def validate_teacher_version(repo: PlaneacionRepository, project_id: int, observation: str = '') -> dict[str, Any]:
    ctx = _require_role(repo, {'DOCENTE'})
    project = get_project(repo, project_id)
    if not project:
        raise LookupError('Proyecto pedagógico no encontrado o no asignado a la docente.')
    docente_id = repo.current_docente_id()
    if not docente_id or int(project.get('docente_id') or 0) != int(docente_id):
        raise PermissionError('Solo la docente asignada puede realizar la validación final.')
    fid = int(project['fundacion_id'])
    version = int(project.get('version_actual') or 0)
    now = now_iso()
    conn = repo.connect()
    try:
        conn.execute(
            """UPDATE pp_proyecto_versiones SET estado='VALIDADA_DOCENTE', validado_por_docente_id=?,
               validado_por=?, fecha_validacion=? WHERE fundacion_id=? AND proyecto_id=? AND numero_version=?""",
            (docente_id, ctx.get('username'), now, fid, project_id, version),
        )
        conn.execute(
            """UPDATE pp_proyectos_pedagogicos SET estado='VALIDADO_DOCENTE', validado_por_docente_id=?,
               validado_por=?, fecha_validacion=?, fecha_actualizacion=? WHERE fundacion_id=? AND id=?""",
            (docente_id, ctx.get('username'), now, now, fid, project_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    repo.log('VALIDAR_PROYECTO_DOCENTE', 'pp_proyectos_pedagogicos', project_id, nuevos={'version': version, 'observacion': observation})
    return get_project(repo, project_id) or {}
