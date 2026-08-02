"""Fase 2C.8: Salud y Nutrición, historial, BOA y calendario nutricional.

Formaliza el núcleo de Salud y Nutrición para PostgreSQL staging sin activar
runtime PostgreSQL completo.
"""
from __future__ import annotations

from alembic import op, context
import sqlalchemy as sa

revision = '20260626_0008_phase2c8_salud_nutricion'
down_revision = '20260626_0007_phase2c7_talento_humano'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    if context.is_offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    if context.is_offline_mode():
        return False
    if not _has_table(table):
        return False
    return any(col['name'] == column for col in sa.inspect(op.get_bind()).get_columns(table))


def _add_column(table: str, column: sa.Column) -> None:
    if not _has_column(table, column.name):
        op.add_column(table, column)


def _create_sn_valoraciones() -> None:
    if _has_table('sn_valoraciones'):
        return
    op.create_table(
        'sn_valoraciones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('tipo_documento', sa.String(80)),
        sa.Column('documento', sa.String(80), nullable=False, index=True),
        sa.Column('nui', sa.String(80)),
        sa.Column('nombre_completo', sa.Text()),
        sa.Column('fecha_nacimiento', sa.String(40)),
        sa.Column('edad_meses', sa.Integer(), server_default='0'),
        sa.Column('edad_texto', sa.String(80)),
        sa.Column('sexo', sa.String(40)),
        sa.Column('unidad', sa.String(255), index=True),
        sa.Column('docente', sa.String(255)),
        sa.Column('acudiente', sa.Text()),
        sa.Column('telefono', sa.String(80)),
        sa.Column('direccion', sa.Text()),
        sa.Column('fecha_valoracion', sa.String(40), index=True),
        sa.Column('peso_kg', sa.Float()),
        sa.Column('talla_cm', sa.Float()),
        sa.Column('imc', sa.Float()),
        sa.Column('perimetro_braquial_cm', sa.Float()),
        sa.Column('perimetro_cefalico_cm', sa.Float()),
        sa.Column('z_peso_edad', sa.Float()),
        sa.Column('z_talla_edad', sa.Float()),
        sa.Column('z_peso_talla', sa.Float()),
        sa.Column('z_imc_edad', sa.Float()),
        sa.Column('z_braquial_edad', sa.Float()),
        sa.Column('diag_peso_edad', sa.String(120)),
        sa.Column('diag_talla_edad', sa.String(120)),
        sa.Column('diag_peso_talla', sa.String(120)),
        sa.Column('diag_imc_edad', sa.String(120)),
        sa.Column('diag_braquial_edad', sa.String(120)),
        sa.Column('diagnostico_global', sa.String(120), index=True),
        sa.Column('nivel_alerta', sa.String(40), server_default='VERDE'),
        sa.Column('estado_control', sa.String(80)),
        sa.Column('trimestre', sa.String(40)),
        sa.Column('periodo', sa.String(20), index=True),
        sa.Column('proximo_control', sa.String(40)),
        sa.Column('fuente_archivo', sa.Text()),
        sa.Column('observaciones', sa.Text()),
        sa.Column('activo', sa.Integer(), server_default='1'),
        sa.Column('fecha_carga', sa.String(40), nullable=False),
        sa.Column('fecha_actualizacion', sa.String(40)),
        sa.Column('usuario_carga', sa.String(120), server_default='sistema'),
    )


def _create_sn_alertas() -> None:
    if _has_table('sn_alertas'):
        return
    op.create_table(
        'sn_alertas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('documento', sa.String(80), index=True),
        sa.Column('valoracion_id', sa.Integer()),
        sa.Column('tipo', sa.String(120), nullable=False),
        sa.Column('nivel', sa.String(40), server_default='AMARILLO', index=True),
        sa.Column('mensaje', sa.Text(), nullable=False),
        sa.Column('unidad', sa.String(255)),
        sa.Column('fecha_alerta', sa.String(40), nullable=False),
        sa.Column('atendida', sa.Integer(), server_default='0'),
        sa.Column('observaciones', sa.Text()),
        sa.Column('fecha_creacion', sa.String(40), nullable=False),
        sa.Column('fecha_actualizacion', sa.String(40)),
    )


def _create_sn_aux() -> None:
    if not _has_table('sn_cargas'):
        op.create_table(
            'sn_cargas',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('tipo', sa.String(120), nullable=False),
            sa.Column('archivo_original', sa.Text()),
            sa.Column('archivo_guardado', sa.Text()),
            sa.Column('total_registros', sa.Integer(), server_default='0'),
            sa.Column('registros_validos', sa.Integer(), server_default='0'),
            sa.Column('registros_con_alerta', sa.Integer(), server_default='0'),
            sa.Column('errores_json', sa.Text()),
            sa.Column('fecha_carga', sa.String(40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(40)),
            sa.Column('usuario', sa.String(120), server_default='sistema'),
        )
    if not _has_table('sn_comparaciones'):
        op.create_table(
            'sn_comparaciones',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('archivo_anterior', sa.Text()),
            sa.Column('archivo_actual', sa.Text()),
            sa.Column('total_anterior', sa.Integer(), server_default='0'),
            sa.Column('total_actual', sa.Integer(), server_default='0'),
            sa.Column('nuevos', sa.Integer(), server_default='0'),
            sa.Column('retirados', sa.Integer(), server_default='0'),
            sa.Column('trasladados', sa.Integer(), server_default='0'),
            sa.Column('cambios', sa.Integer(), server_default='0'),
            sa.Column('resumen_json', sa.Text()),
            sa.Column('reporte_excel', sa.Text()),
            sa.Column('reporte_pdf', sa.Text()),
            sa.Column('fecha_comparacion', sa.String(40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(40)),
            sa.Column('usuario', sa.String(120), server_default='sistema'),
        )
    if not _has_table('sn_calendario'):
        op.create_table(
            'sn_calendario',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('valoracion_id', sa.Integer()),
            sa.Column('tipo_evento', sa.String(120), nullable=False),
            sa.Column('fecha_programada', sa.String(40), nullable=False, index=True),
            sa.Column('estado', sa.String(80), server_default='PROGRAMADO'),
            sa.Column('nivel', sa.String(40), server_default='VERDE'),
            sa.Column('unidad', sa.String(255)),
            sa.Column('responsable', sa.String(255)),
            sa.Column('descripcion', sa.Text()),
            sa.Column('fecha_creacion', sa.String(40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(40)),
        )
    if not _has_table('sn_adjuntos'):
        op.create_table(
            'sn_adjuntos',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('valoracion_id', sa.Integer()),
            sa.Column('nombre_original', sa.Text()),
            sa.Column('nombre_guardado', sa.Text()),
            sa.Column('ruta_archivo', sa.Text()),
            sa.Column('tipo', sa.String(120)),
            sa.Column('estado', sa.String(80), server_default='ACTIVO'),
            sa.Column('fecha_carga', sa.String(40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(40)),
        )
    if not _has_table('sn_historial_acciones'):
        op.create_table(
            'sn_historial_acciones',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('usuario', sa.String(120)),
            sa.Column('accion', sa.String(120), nullable=False),
            sa.Column('entidad_tipo', sa.String(120)),
            sa.Column('entidad_id', sa.Integer()),
            sa.Column('documento', sa.String(80)),
            sa.Column('datos_anteriores', sa.Text()),
            sa.Column('datos_nuevos', sa.Text()),
            sa.Column('fecha_accion', sa.String(40), nullable=False),
        )
    if not _has_table('sn_referencias_oms'):
        op.create_table(
            'sn_referencias_oms',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1'),
            sa.Column('indicador', sa.String(120), nullable=False),
            sa.Column('sexo', sa.String(40)),
            sa.Column('edad_meses', sa.Integer()),
            sa.Column('talla_cm', sa.Float()),
            sa.Column('medida', sa.Float()),
            sa.Column('sd3neg', sa.Float()),
            sa.Column('sd2neg', sa.Float()),
            sa.Column('sd1neg', sa.Float()),
            sa.Column('mediana', sa.Float()),
            sa.Column('sd1', sa.Float()),
            sa.Column('sd2', sa.Float()),
            sa.Column('sd3', sa.Float()),
            sa.Column('fuente', sa.Text()),
            sa.Column('fecha_carga', sa.String(40), nullable=False),
        )


def _create_peso_talla() -> None:
    if _has_table('peso_talla'):
        return
    op.create_table(
        'peso_talla',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('beneficiario_id', sa.Integer(), server_default='0'),
        sa.Column('documento', sa.String(80), index=True),
        sa.Column('nombre', sa.Text()),
        sa.Column('unidad', sa.String(255)),
        sa.Column('peso', sa.Float()),
        sa.Column('talla', sa.Float()),
        sa.Column('fecha_toma', sa.String(40)),
        sa.Column('estado', sa.String(80)),
        sa.Column('fecha_medicion', sa.String(40)),
        sa.Column('responsable', sa.String(255)),
        sa.Column('estado_nutricional', sa.String(120), server_default='PENDIENTE'),
        sa.Column('fecha_proximo_control', sa.String(40)),
        sa.Column('fecha_carga', sa.String(40)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('fecha_actualizacion', sa.String(40)),
    )


def _compat_columns() -> None:
    for table in (
        'sn_valoraciones', 'sn_alertas', 'sn_cargas', 'sn_comparaciones',
        'sn_calendario', 'sn_adjuntos', 'sn_historial_acciones', 'sn_referencias_oms',
        'peso_talla'
    ):
        if not _has_table(table):
            continue
        _add_column(table, sa.Column('fundacion_id', sa.Integer(), server_default='1'))
        _add_column(table, sa.Column('usuario_creador_id', sa.Integer()))
        _add_column(table, sa.Column('fecha_actualizacion', sa.String(40)))


def upgrade() -> None:
    _create_sn_valoraciones()
    _create_sn_alertas()
    _create_sn_aux()
    _create_peso_talla()
    _compat_columns()


def downgrade() -> None:
    # No eliminar tablas clínicas/nutricionales en rollback lógico. Para revertir
    # esta fase use el backup previo documentado.
    pass
