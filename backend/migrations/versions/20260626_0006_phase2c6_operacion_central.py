"""Fase 2C.6: beneficiarios, usuarios, unidades y operación central.

Crea/normaliza las tablas operativas mínimas necesarias para PostgreSQL
staging. En SQLite local las tablas históricas siguen siendo la fuente de
verdad; esta migración es compatible con la cadena autónoma iniciada en 2C.5.
"""
from __future__ import annotations

from alembic import op, context
import sqlalchemy as sa

revision = '20260626_0006_phase2c6_operacion_central'
down_revision = '20260626_0005_phase2c5_facturacion_suscripciones'
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


def _create_usuarios() -> None:
    if _has_table('usuarios'):
        return
    op.create_table(
        'usuarios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('documento', sa.String(80), index=True),
        sa.Column('nombre', sa.Text()),
        sa.Column('unidad', sa.String(255), index=True),
        sa.Column('fecha_nacimiento', sa.String(40)),
        sa.Column('estado', sa.String(40)),
        sa.Column('peso_talla_al_dia', sa.String(80)),
        sa.Column('docente', sa.String(255)),
        sa.Column('tipo_beneficiario', sa.String(80)),
        sa.Column('fecha_carga', sa.String(40)),
        sa.Column('nui', sa.String(80)),
        sa.Column('tipo_documento', sa.String(40)),
        sa.Column('primer_nombre', sa.String(120)),
        sa.Column('segundo_nombre', sa.String(120)),
        sa.Column('primer_apellido', sa.String(120)),
        sa.Column('segundo_apellido', sa.String(120)),
        sa.Column('sexo', sa.String(40)),
        sa.Column('nombre_acudiente', sa.Text()),
        sa.Column('documento_acudiente', sa.String(80)),
        sa.Column('tipo_documento_acudiente', sa.String(40)),
        sa.Column('parentesco', sa.String(80)),
        sa.Column('telefono', sa.String(80)),
        sa.Column('edad_meses', sa.Integer(), server_default='0'),
        sa.Column('grupo_edad', sa.String(120)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('fecha_creacion', sa.String(40)),
        sa.Column('fecha_actualizacion', sa.String(40)),
    )


def _create_beneficiarios() -> None:
    if _has_table('beneficiarios'):
        return
    op.create_table(
        'beneficiarios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('documento', sa.String(80), nullable=False),
        sa.Column('nombres', sa.Text()),
        sa.Column('apellidos', sa.Text()),
        sa.Column('fecha_nacimiento', sa.String(40)),
        sa.Column('sexo', sa.String(40)),
        sa.Column('unidad', sa.String(255), index=True),
        sa.Column('estado', sa.String(40), index=True),
        sa.Column('tipo_beneficiario', sa.String(80)),
        sa.Column('fecha_ingreso', sa.String(40)),
        sa.Column('fecha_carga', sa.String(40)),
        sa.Column('nui', sa.String(80)),
        sa.Column('tipo_documento', sa.String(40)),
        sa.Column('primer_nombre', sa.String(120)),
        sa.Column('segundo_nombre', sa.String(120)),
        sa.Column('primer_apellido', sa.String(120)),
        sa.Column('segundo_apellido', sa.String(120)),
        sa.Column('nombre_acudiente', sa.Text()),
        sa.Column('documento_acudiente', sa.String(80)),
        sa.Column('tipo_documento_acudiente', sa.String(40)),
        sa.Column('parentesco', sa.String(80)),
        sa.Column('telefono', sa.String(80)),
        sa.Column('edad_meses', sa.Integer(), server_default='0'),
        sa.Column('grupo_edad', sa.String(120)),
        sa.Column('regional', sa.String(120)),
        sa.Column('centro_zonal', sa.String(120)),
        sa.Column('municipio', sa.String(120)),
        sa.Column('modalidad', sa.Text()),
        sa.Column('numero_contrato', sa.String(120)),
        sa.Column('vigencia', sa.String(40)),
        sa.Column('nombre_eas', sa.Text()),
        sa.Column('direccion_unidad', sa.Text()),
        sa.Column('codigo_unidad_servicio', sa.String(120)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('fecha_creacion', sa.String(40)),
        sa.Column('fecha_actualizacion', sa.String(40)),
        sa.UniqueConstraint('fundacion_id', 'documento', name='uq_beneficiarios_fundacion_documento'),
    )


def _create_unidades() -> None:
    if _has_table('unidades'):
        return
    op.create_table(
        'unidades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(255), nullable=False),
        sa.Column('direccion', sa.Text()),
        sa.Column('telefono', sa.String(80)),
        sa.Column('coordinador_id', sa.Integer()),
        sa.Column('total_usuarios', sa.Integer(), server_default='0'),
        sa.Column('total_gestantes', sa.Integer(), server_default='0'),
        sa.Column('fecha_actualizacion', sa.String(40)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
        sa.Column('usuario_creador_id', sa.Integer()),
        sa.Column('fecha_creacion', sa.String(40)),
        sa.UniqueConstraint('fundacion_id', 'nombre', name='uq_unidades_fundacion_nombre'),
    )


def _create_movimientos() -> None:
    if _has_table('movimientos'):
        return
    op.create_table(
        'movimientos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('beneficiario_id', sa.Integer()),
        sa.Column('tipo', sa.String(80)),
        sa.Column('documento', sa.String(80), index=True),
        sa.Column('nombre', sa.Text()),
        sa.Column('unidad_origen', sa.String(255)),
        sa.Column('unidad_destino', sa.String(255)),
        sa.Column('fecha', sa.String(40)),
        sa.Column('detalle', sa.Text()),
        sa.Column('fecha_movimiento', sa.String(40)),
        sa.Column('razon', sa.Text()),
        sa.Column('usuario_registra', sa.String(120)),
        sa.Column('fecha_registro', sa.String(40)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
    )


def _create_auditoria() -> None:
    if _has_table('auditoria'):
        return
    op.create_table(
        'auditoria',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fecha', sa.String(40)),
        sa.Column('usuario', sa.String(120)),
        sa.Column('accion', sa.String(120)),
        sa.Column('tabla', sa.String(120)),
        sa.Column('registro_id', sa.Integer()),
        sa.Column('datos_anteriores', sa.Text()),
        sa.Column('datos_nuevos', sa.Text()),
        sa.Column('archivo', sa.Text()),
        sa.Column('archivo_cargado', sa.Text()),
        sa.Column('formato_generado', sa.Text()),
        sa.Column('total_registros', sa.Integer()),
        sa.Column('cambios_detectados', sa.Text()),
        sa.Column('fecha_accion', sa.String(40)),
        sa.Column('direccion_ip', sa.String(80)),
        sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
    )


def _create_cb_tables() -> None:
    if not _has_table('cb_cruces'):
        op.create_table(
            'cb_cruces',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('usuario_id', sa.Integer()),
            sa.Column('usuario', sa.String(120)),
            sa.Column('mes', sa.Integer()),
            sa.Column('anio', sa.Integer()),
            sa.Column('periodo', sa.String(20), index=True),
            sa.Column('archivo_anterior', sa.Text()),
            sa.Column('archivo_actual', sa.Text()),
            sa.Column('ruta_anterior', sa.Text()),
            sa.Column('ruta_actual', sa.Text()),
            sa.Column('total_anterior', sa.Integer(), server_default='0'),
            sa.Column('total_actual', sa.Integer(), server_default='0'),
            sa.Column('nuevos', sa.Integer(), server_default='0'),
            sa.Column('retirados', sa.Integer(), server_default='0'),
            sa.Column('reemplazados', sa.Integer(), server_default='0'),
            sa.Column('trasladados', sa.Integer(), server_default='0'),
            sa.Column('cambios_total', sa.Integer(), server_default='0'),
            sa.Column('resultado_json', sa.Text()),
            sa.Column('errores_json', sa.Text()),
            sa.Column('reporte_excel', sa.Text()),
            sa.Column('reporte_pdf', sa.Text()),
            sa.Column('fecha_cruce', sa.String(40)),
        )
    if not _has_table('cb_detalles'):
        op.create_table(
            'cb_detalles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('cruce_id', sa.Integer(), index=True),
            sa.Column('fundacion_id', sa.Integer(), server_default='1', index=True),
            sa.Column('tipo', sa.String(80), index=True),
            sa.Column('documento', sa.String(80), index=True),
            sa.Column('nombre', sa.Text()),
            sa.Column('unidad_anterior', sa.String(255)),
            sa.Column('unidad_actual', sa.String(255)),
            sa.Column('docente_anterior', sa.String(255)),
            sa.Column('docente_actual', sa.String(255)),
            sa.Column('datos_json', sa.Text()),
            sa.Column('fecha_creacion', sa.String(40)),
        )


def upgrade() -> None:
    _create_usuarios()
    _create_beneficiarios()
    _create_unidades()
    _create_movimientos()
    _create_auditoria()
    _create_cb_tables()

    # Compatibilidad incremental cuando las tablas ya existen.
    for table in ('usuarios', 'beneficiarios', 'unidades', 'movimientos', 'auditoria'):
        if _has_table(table):
            _add_column(table, sa.Column('fundacion_id', sa.Integer(), server_default='1'))
            _add_column(table, sa.Column('fecha_actualizacion', sa.String(40)))


def downgrade() -> None:
    # No se eliminan tablas operativas en downgrade para evitar pérdida de datos
    # accidentales. El rollback de esta fase debe hacerse restaurando el backup.
    pass
