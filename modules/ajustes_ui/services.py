from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import AJUSTES_UI_SCHEMA_SQL, DEFAULT_UI_SETTINGS, PRESETS

HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def connect(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(database_path: str) -> None:
    conn = connect(database_path)
    conn.executescript(AJUSTES_UI_SCHEMA_SQL)
    conn.commit()
    conn.close()


def sanitize_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})
    preset = str(payload.get('preset') or DEFAULT_UI_SETTINGS['preset'])
    base = dict(PRESETS.get(preset, DEFAULT_UI_SETTINGS))
    base['preset'] = preset if preset in PRESETS or preset == 'personalizado' else DEFAULT_UI_SETTINGS['preset']

    for key in [
        'primaryColor', 'primaryHoverColor', 'accentColor', 'backgroundColor', 'surfaceColor',
        'surfaceSoftColor', 'borderColor', 'textColor', 'mutedTextColor', 'successColor',
        'warningColor', 'dangerColor'
    ]:
        value = str(payload.get(key) or base.get(key) or '').strip()
        if HEX_RE.match(value):
            base[key] = value

    radius = str(payload.get('radius') or base.get('radius') or '16px').strip()
    if radius in {'8px', '12px', '16px', '20px', '24px'}:
        base['radius'] = radius

    density = str(payload.get('density') or base.get('density') or 'comfortable').strip()
    if density in {'compact', 'comfortable', 'spacious'}:
        base['density'] = density

    font_scale = str(payload.get('fontScale') or base.get('fontScale') or '100').strip()
    if font_scale in {'90', '95', '100', '105', '110', '115'}:
        base['fontScale'] = font_scale

    sidebar_mode = str(payload.get('sidebarMode') or base.get('sidebarMode') or 'normal').strip()
    if sidebar_mode in {'normal', 'compact'}:
        base['sidebarMode'] = sidebar_mode

    base['reduceMotion'] = bool(payload.get('reduceMotion'))
    return base


def get_settings(database_path: str, fundacion_id: int) -> dict[str, Any]:
    init_schema(database_path)
    conn = connect(database_path)
    row = conn.execute(
        "SELECT valor_json FROM ui_ajustes WHERE fundacion_id=? AND clave='tema'",
        (fundacion_id,),
    ).fetchone()
    conn.close()
    if not row:
        return dict(DEFAULT_UI_SETTINGS)
    try:
        return sanitize_settings(json.loads(row['valor_json'] or '{}'))
    except Exception:
        return dict(DEFAULT_UI_SETTINGS)


def save_settings(database_path: str, fundacion_id: int, usuario_id: int | None, payload: dict[str, Any], ip: str | None = None) -> dict[str, Any]:
    init_schema(database_path)
    settings = sanitize_settings(payload)
    now = now_iso()
    conn = connect(database_path)
    conn.execute(
        """
        INSERT INTO ui_ajustes (fundacion_id, clave, valor_json, usuario_creador_id, fecha_creacion, fecha_actualizacion)
        VALUES (?, 'tema', ?, ?, ?, ?)
        ON CONFLICT(fundacion_id, clave) DO UPDATE SET
            valor_json=excluded.valor_json,
            usuario_creador_id=excluded.usuario_creador_id,
            fecha_actualizacion=excluded.fecha_actualizacion
        """,
        (fundacion_id, json.dumps(settings, ensure_ascii=False), usuario_id, now, now),
    )
    conn.execute(
        """
        INSERT INTO ui_auditoria (fundacion_id, usuario_id, accion, descripcion, datos_json, ip, fecha)
        VALUES (?, ?, 'AJUSTES_UI_GUARDADOS', 'Actualización de tema visual', ?, ?, ?)
        """,
        (fundacion_id, usuario_id, json.dumps(settings, ensure_ascii=False), ip, now),
    )
    conn.commit()
    conn.close()
    return settings


def reset_settings(database_path: str, fundacion_id: int, usuario_id: int | None, ip: str | None = None) -> dict[str, Any]:
    init_schema(database_path)
    now = now_iso()
    conn = connect(database_path)
    conn.execute("DELETE FROM ui_ajustes WHERE fundacion_id=? AND clave='tema'", (fundacion_id,))
    conn.execute(
        """
        INSERT INTO ui_auditoria (fundacion_id, usuario_id, accion, descripcion, datos_json, ip, fecha)
        VALUES (?, ?, 'AJUSTES_UI_RESTABLECIDOS', 'Tema visual restablecido a valores predeterminados', ?, ?, ?)
        """,
        (fundacion_id, usuario_id, json.dumps(DEFAULT_UI_SETTINGS, ensure_ascii=False), ip, now),
    )
    conn.commit()
    conn.close()
    return dict(DEFAULT_UI_SETTINGS)


def _scan_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8', errors='ignore')
    color_patterns = [
        r'bg-(slate|indigo|cyan|emerald|rose|amber|violet|fuchsia|sky|blue|green|red|yellow)-',
        r'text-(slate|indigo|cyan|emerald|rose|amber|violet|fuchsia|sky|blue|green|red|yellow)-',
        r'border-(slate|indigo|cyan|emerald|rose|amber|violet|fuchsia|sky|blue|green|red|yellow)-',
        r'hover:bg-(slate|indigo|cyan|emerald|rose|amber|violet|fuchsia|sky|blue|green|red|yellow)-',
    ]
    return {
        'archivo': str(path),
        'lineas': text.count('\n') + 1,
        'clases_color_quemadas': sum(len(re.findall(pattern, text)) for pattern in color_patterns),
        'onclick_inline': text.count('onclick='),
        'ids_hardcoded': len(re.findall(r'id="[^"]+"', text)),
        'estilos_inline': text.count('style='),
        'hex_colores': len(re.findall(r'#[0-9A-Fa-f]{6}', text)),
        'px_quemados': len(re.findall(r'\b\d+px\b', text)),
    }


def audit_ux(project_root: str) -> dict[str, Any]:
    root = Path(project_root)
    patterns = [root / 'frontend' / 'index.html', root / 'js' / 'app.js']
    modules_dir = root / 'js' / 'modules'
    components_dir = root / 'js' / 'components'
    css_dir = root / 'css'
    if modules_dir.exists():
        patterns.extend(modules_dir.glob('*.js'))
    if components_dir.exists():
        patterns.extend(components_dir.glob('*.js'))
    if css_dir.exists():
        patterns.extend(css_dir.glob('*.css'))

    files = []
    for path in patterns:
        if path.exists() and path.is_file():
            files.append(_scan_file(path))
    totals = {
        'archivos_revisados': len(files),
        'clases_color_quemadas': sum(item['clases_color_quemadas'] for item in files),
        'onclick_inline': sum(item['onclick_inline'] for item in files),
        'ids_hardcoded': sum(item['ids_hardcoded'] for item in files),
        'estilos_inline': sum(item['estilos_inline'] for item in files),
        'hex_colores': sum(item['hex_colores'] for item in files),
        'px_quemados': sum(item['px_quemados'] for item in files),
    }
    top = sorted(files, key=lambda item: (item['clases_color_quemadas'], item['onclick_inline'], item['ids_hardcoded']), reverse=True)[:10]
    recomendaciones = [
        'Centralizar colores en variables CSS para evitar editar cientos de clases Tailwind por cambio de marca.',
        'Reducir onclick inline gradualmente hacia listeners por módulo para mejorar mantenibilidad.',
        'Unificar tarjetas, botones, tablas e inputs como componentes reutilizables de diseño.',
        'Mantener ajustes visuales por fundación para comercializar la plataforma con marca del cliente.',
        'Aplicar densidad compacta en pantallas con tablas grandes y densidad cómoda en operación diaria.',
    ]
    return {'totales': totals, 'archivos': top, 'recomendaciones': recomendaciones}
