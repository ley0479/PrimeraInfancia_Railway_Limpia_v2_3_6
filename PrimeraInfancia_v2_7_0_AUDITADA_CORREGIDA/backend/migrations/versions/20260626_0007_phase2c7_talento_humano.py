"""Fase 2C.7: Talento Humano, coordinadores, docentes y fuente maestra.

Formaliza el núcleo de Talento Humano para PostgreSQL staging sin activar el
runtime PostgreSQL completo. La aplicación local conserva SQLite.
"""
from __future__ import annotations

from alembic import op, context
import sqlalchemy as sa

revision = '20260626_0007_phase2c7_talento_humano'
down_revision = '20260626_0006_phase2c6_operacion_central'
branch_labels = None
depends_on = None


def _inspect():
    if context.is_offline_mode():
        return None
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    insp = _inspect()
    return False if insp is None else insp.has_table(name)


def _has_column(table: str, column: str) -> bool:
    insp = _inspect()
    if insp is None or not insp.has_table(table):
        return False
    return any(col['name'] == column for col in insp.get_columns(table))


def _add_column(table: str, column: sa.Column) -> None:
    if not _has_column(table, column.name):
        op.add_column(table, column)


def _create_coordinadores() -> None:
    if _has_table('coordinadores'):
        return
    op.create_table(
        'coordinadores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('documento', sa.String(80), index=True),
        sa.Column('nombre', sa.Text()),
        sa.Column('nombres', sa.Text()),
        sa.Column('apellidos', sa.Text()),
        sa.Column('cargo', sa.String(160)),
        sa.Column('unidad', sa.String(255), index=True),
        sa.Column('unidades', sa.Text()),
        sa.Column('direccion', sa.Text()),
        sa.Column('telefono', sa.String(80)),
        sa.Column('coordinador', sa.Text()),
        sa.Column('tipo_equipo', sa.String(120), index=True),
        sa.Column('contrato', sa.String(120)),
        sa.Column('perfil', sa.Text()),
        sa.Column('estado', sa.String(40), server_default='activo'),
        sa.Column('activo', sa.Integer(), server_default='1'),
        sa.Column('archivo', sa.Text()),
        sa.Column('fecha_carga', sa.String(40)),
        sa.Column('fecha_ultima_actualizacion', sa.String(40)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('fecha_creacion', sa.String(40)),
        sa.Column('fecha_actualizacion', sa.String(40)),
    )


def _create_docentes() -> None:
    if _has_table('docentes'):
        return
    op.create_table(
        'docentes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('documento', sa.String(80), index=True),
        sa.Column('nombres', sa.Text()),
        sa.Column('apellidos', sa.Text()),
        sa.Column('cargo', sa.String(160)),
        sa.Column('unidad', sa.String(255), index=True),
        sa.Column('email', sa.String(255)),
        sa.Column('telefono', sa.String(80)),
        sa.Column('fecha_vinculacion', sa.String(40)),
        sa.Column('activo', sa.Integer(), server_default='1'),
        sa.Column('fecha_carga', sa.String(40)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('fecha_creacion', sa.String(40)),
        sa.Column('fecha_actualizacion', sa.String(40)),
    )


def _create_gp_tables() -> None:
    if not _has_table('gp_coordinadores'):
        op.create_table(
            'gp_coordinadores',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('contrato_id', sa.Integer()),
            sa.Column('contrato', sa.String(120), index=True),
            sa.Column('nombre', sa.Text(), nullable=False),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('telefono', sa.String(80)),
            sa.Column('email', sa.String(255)),
            sa.Column('cargo', sa.String(120), server_default='COORDINADOR'),
            sa.Column('zona', sa.String(120)),
            sa.Column('unidades_json', sa.Text()),
            sa.Column('observaciones', sa.Text()),
            sa.Column('activo', sa.Integer(), server_default='1'),
            sa.Column('fecha_creacion', sa.String(40)),
            sa.Column('fecha_actualizacion', sa.String(40)),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('usuario_id', sa.Integer()),
        )
    if not _has_table('gp_docentes'):
        op.create_table(
            'gp_docentes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('coordinador_id', sa.Integer(), index=True),
            sa.Column('nombre', sa.Text(), nullable=False),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('unidad', sa.String(255), index=True),
            sa.Column('telefono', sa.String(80)),
            sa.Column('email', sa.String(255)),
            sa.Column('cargo', sa.String(120), server_default='DOCENTE'),
            sa.Column('activo', sa.Integer(), server_default='1'),
            sa.Column('fecha_creacion', sa.String(40)),
            sa.Column('fecha_actualizacion', sa.String(40)),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('usuario_id', sa.Integer()),
        )
    if not _has_table('gp_equipos_interdisciplinarios'):
        op.create_table(
            'gp_equipos_interdisciplinarios',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('coordinador_id', sa.Integer(), index=True),
            sa.Column('nombre', sa.Text(), nullable=False),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('rol', sa.String(120), nullable=False),
            sa.Column('profesion', sa.Text()),
            sa.Column('telefono', sa.String(80)),
            sa.Column('email', sa.String(255)),
            sa.Column('activo', sa.Integer(), server_default='1'),
            sa.Column('fecha_creacion', sa.String(40)),
            sa.Column('fecha_actualizacion', sa.String(40)),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
        )
    if not _has_table('gp_unidades_asignadas'):
        op.create_table(
            'gp_unidades_asignadas',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('coordinador_id', sa.Integer(), nullable=False, index=True),
            sa.Column('unidad', sa.String(255), nullable=False, index=True),
            sa.Column('estado', sa.String(40), server_default='activo'),
            sa.Column('fecha_creacion', sa.String(40)),
            sa.Column('fecha_actualizacion', sa.String(40)),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
        )
    if not _has_table('gp_asignaciones_coordinador'):
        op.create_table(
            'gp_asignaciones_coordinador',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('coordinador_id', sa.Integer(), index=True),
            sa.Column('tipo_talento', sa.String(120)),
            sa.Column('origen_tabla', sa.String(120)),
            sa.Column('origen_id', sa.Integer()),
            sa.Column('nombre', sa.Text()),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('cargo', sa.String(160)),
            sa.Column('rol', sa.String(120), index=True),
            sa.Column('unidad', sa.String(255), index=True),
            sa.Column('telefono', sa.String(80)),
            sa.Column('email', sa.String(255)),
            sa.Column('estado', sa.String(40), server_default='ACTIVO'),
            sa.Column('fecha_inicio', sa.String(40)),
            sa.Column('fecha_fin', sa.String(40)),
            sa.Column('observaciones', sa.Text()),
            sa.Column('fecha_creacion', sa.String(40)),
            sa.Column('fecha_actualizacion', sa.String(40)),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
        )


def _create_th_tables() -> None:
    if not _has_table('th_personas'):
        op.create_table(
            'th_personas',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('nombre', sa.Text(), nullable=False),
            sa.Column('nombres', sa.Text()),
            sa.Column('apellidos', sa.Text()),
            sa.Column('cargo', sa.String(160)),
            sa.Column('tipo_equipo', sa.String(120)),
            sa.Column('rol_normalizado', sa.String(80), index=True),
            sa.Column('unidad', sa.String(255), index=True),
            sa.Column('direccion', sa.Text()),
            sa.Column('telefono', sa.String(80)),
            sa.Column('coordinador', sa.Text()),
            sa.Column('contrato', sa.String(120)),
            sa.Column('perfil', sa.Text()),
            sa.Column('estado', sa.String(40), server_default='activo'),
            sa.Column('activo', sa.Integer(), server_default='1'),
            sa.Column('origen_tabla', sa.String(120), server_default='coordinadores'),
            sa.Column('origen_id', sa.Integer()),
            sa.Column('archivo', sa.Text()),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('fecha_creacion', sa.String(40)),
            sa.Column('fecha_actualizacion', sa.String(40)),
        )
    if not _has_table('th_asignaciones'):
        op.create_table(
            'th_asignaciones',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('persona_id', sa.Integer(), index=True),
            sa.Column('coordinador_id', sa.Integer(), index=True),
            sa.Column('coordinador_nombre', sa.Text()),
            sa.Column('unidad', sa.String(255), index=True),
            sa.Column('rol', sa.String(120), index=True),
            sa.Column('cargo', sa.String(160)),
            sa.Column('estado', sa.String(40), server_default='ACTIVO'),
            sa.Column('fecha_inicio', sa.String(40)),
            sa.Column('fecha_fin', sa.String(40)),
            sa.Column('observaciones', sa.Text()),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('fecha_creacion', sa.String(40)),
            sa.Column('fecha_actualizacion', sa.String(40)),
        )
    if not _has_table('th_historial'):
        op.create_table(
            'th_historial',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('persona_id', sa.Integer(), index=True),
            sa.Column('accion', sa.String(160), index=True),
            sa.Column('datos_anteriores', sa.Text()),
            sa.Column('datos_nuevos', sa.Text()),
            sa.Column('usuario', sa.String(255)),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('fecha_accion', sa.String(40)),
        )
    if not _has_table('th_sincronizaciones'):
        op.create_table(
            'th_sincronizaciones',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('origen', sa.String(160)),
            sa.Column('total_personas', sa.Integer(), server_default='0'),
            sa.Column('total_asignaciones', sa.Integer(), server_default='0'),
            sa.Column('resultado_json', sa.Text()),
            sa.Column('usuario', sa.String(255)),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('fecha_sincronizacion', sa.String(40)),
        )


def _normalize_existing_columns() -> None:
    for table, columns in {
        'coordinadores': [
            ('documento', sa.String(80)),
            ('nombre', sa.Text()),
            ('nombres', sa.Text()),
            ('apellidos', sa.Text()),
            ('cargo', sa.String(160)),
            ('unidad', sa.String(255)),
            ('unidades', sa.Text()),
            ('direccion', sa.Text()),
            ('telefono', sa.String(80)),
            ('coordinador', sa.Text()),
            ('tipo_equipo', sa.String(120)),
            ('contrato', sa.String(120)),
            ('perfil', sa.Text()),
            ('estado', sa.String(40), 'activo'),
            ('activo', sa.Integer(), '1'),
            ('archivo', sa.Text()),
            ('fecha_carga', sa.String(40)),
            ('fecha_ultima_actualizacion', sa.String(40)),
            ('fundacion_id', sa.Integer(), '1'),
            ('usuario_creador_id', sa.Integer()),
            ('fecha_creacion', sa.String(40)),
            ('fecha_actualizacion', sa.String(40)),
        ],
        'unidades': [
            ('docente_asignado', sa.Text()),
            ('docente_documento', sa.String(80)),
            ('coordinador_nombre', sa.Text()),
            ('contrato', sa.String(120)),
            ('fundacion_id', sa.Integer(), '1'),
        ],
    }.items():
        if not _has_table(table):
            continue
        for item in columns:
            name, type_ = item[0], item[1]
            default = item[2] if len(item) > 2 else None
            column = sa.Column(name, type_, server_default=default)
            _add_column(table, column)

    for table in [
        'gp_coordinadores',
        'gp_docentes',
        'gp_equipos_interdisciplinarios',
        'gp_unidades_asignadas',
        'gp_asignaciones_coordinador',
        'gp_historial_acciones',
    ]:
        if _has_table(table):
            _add_column(table, sa.Column('fundacion_id', sa.Integer(), server_default='1'))
            _add_column(table, sa.Column('usuario_creador_id', sa.Integer()))
            _add_column(table, sa.Column('fecha_actualizacion', sa.String(40)))


def upgrade() -> None:
    _create_coordinadores()
    _create_docentes()
    _create_gp_tables()
    _create_th_tables()
    _normalize_existing_columns()


def downgrade() -> None:
    # En producción no se elimina información de Talento Humano automáticamente.
    # El rollback estructural se hace restaurando el backup previo de la fase.
    pass
