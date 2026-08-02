from __future__ import annotations

import json

DEFAULT_UI_SETTINGS = {
    'preset': 'oscuro-icbf',
    'primaryColor': '#4f46e5',
    'primaryHoverColor': '#4338ca',
    'accentColor': '#06b6d4',
    'backgroundColor': '#020617',
    'surfaceColor': '#0f172a',
    'surfaceSoftColor': '#1e293b',
    'borderColor': '#334155',
    'textColor': '#f8fafc',
    'mutedTextColor': '#94a3b8',
    'successColor': '#10b981',
    'warningColor': '#f59e0b',
    'dangerColor': '#ef4444',
    'radius': '16px',
    'density': 'comfortable',
    'fontScale': '100',
    'sidebarMode': 'normal',
    'reduceMotion': False,
}

PRESETS = {
    'oscuro-icbf': DEFAULT_UI_SETTINGS,
    'azul-profesional': {
        **DEFAULT_UI_SETTINGS,
        'primaryColor': '#2563eb',
        'primaryHoverColor': '#1d4ed8',
        'accentColor': '#0891b2',
        'surfaceColor': '#0f172a',
    },
    'verde-institucional': {
        **DEFAULT_UI_SETTINGS,
        'primaryColor': '#059669',
        'primaryHoverColor': '#047857',
        'accentColor': '#65a30d',
    },
    'morado-ejecutivo': {
        **DEFAULT_UI_SETTINGS,
        'primaryColor': '#7c3aed',
        'primaryHoverColor': '#6d28d9',
        'accentColor': '#d946ef',
    },
    'alto-contraste': {
        **DEFAULT_UI_SETTINGS,
        'primaryColor': '#facc15',
        'primaryHoverColor': '#eab308',
        'accentColor': '#22d3ee',
        'backgroundColor': '#000000',
        'surfaceColor': '#0a0a0a',
        'surfaceSoftColor': '#171717',
        'borderColor': '#facc15',
        'textColor': '#ffffff',
        'mutedTextColor': '#e5e7eb',
    },
    'claro': {
        **DEFAULT_UI_SETTINGS,
        'primaryColor': '#4f46e5',
        'primaryHoverColor': '#4338ca',
        'accentColor': '#0891b2',
        'backgroundColor': '#f8fafc',
        'surfaceColor': '#ffffff',
        'surfaceSoftColor': '#e2e8f0',
        'borderColor': '#cbd5e1',
        'textColor': '#0f172a',
        'mutedTextColor': '#475569',
    },
}

AJUSTES_UI_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ui_ajustes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL DEFAULT 1,
    clave TEXT NOT NULL DEFAULT 'tema',
    valor_json TEXT NOT NULL,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, clave)
);

CREATE TABLE IF NOT EXISTS ui_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_id INTEGER,
    accion TEXT NOT NULL,
    descripcion TEXT,
    datos_json TEXT,
    ip TEXT,
    fecha TEXT NOT NULL
);
"""


def defaults_json() -> str:
    return json.dumps(DEFAULT_UI_SETTINGS, ensure_ascii=False)
