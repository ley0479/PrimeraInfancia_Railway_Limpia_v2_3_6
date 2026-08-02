"""Fase 2C.5: facturación, suscripciones, panel comercial y gerencia general.

Esta migración crea las tablas comerciales migradas a SQLAlchemy Core. En la
cadena completa del proyecto debe colgar de la revisión que cree las tablas
base fundaciones y usuarios_app. En este artefacto se mantiene autónoma porque
la cadena 2A-2C.4 no estaba empaquetada en el ZIP base disponible.
"""
from __future__ import annotations

from alembic import op, context
import sqlalchemy as sa

revision = '20260626_0005_phase2c5_facturacion_suscripciones'
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    if context.is_offline_mode():
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    # Facturación y suscripciones
    if not _has_table('planes_suscripcion'):
        op.create_table(
            'planes_suscripcion',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('nombre', sa.String(length=120), nullable=False, unique=True),
            sa.Column('descripcion', sa.Text()),
            sa.Column('precio_mensual', sa.Numeric(14, 2), server_default='0'),
            sa.Column('limite_usuarios', sa.Integer(), server_default='0'),
            sa.Column('limite_coordinadores', sa.Integer(), server_default='0'),
            sa.Column('limite_unidades', sa.Integer(), server_default='0'),
            sa.Column('creditos_incluidos', sa.Integer(), server_default='0'),
            sa.Column('modulos_habilitados', sa.Text()),
            sa.Column('estado', sa.String(length=30), server_default='ACTIVO'),
            sa.Column('personalizado', sa.Boolean(), server_default=sa.text('false')),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(length=40)),
        )
    if not _has_table('suscripciones_fundacion'):
        op.create_table(
            'suscripciones_fundacion',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), nullable=False, unique=True),
            sa.Column('plan_id', sa.Integer()),
            sa.Column('estado', sa.String(length=30), server_default='ACTIVA'),
            sa.Column('fecha_inicio', sa.String(length=40), nullable=False),
            sa.Column('fecha_vencimiento', sa.String(length=40), nullable=False),
            sa.Column('dias_gracia', sa.Integer(), server_default='5'),
            sa.Column('creditos_disponibles', sa.Integer(), server_default='0'),
            sa.Column('creditos_incluidos_periodo', sa.Integer(), server_default='0'),
            sa.Column('modulos_habilitados', sa.Text()),
            sa.Column('renovacion_automatica', sa.Boolean(), server_default=sa.text('false')),
            sa.Column('observaciones', sa.Text()),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(length=40)),
        )
        op.create_index('idx_suscripciones_fundacion', 'suscripciones_fundacion', ['fundacion_id'])
        op.create_index('idx_suscripciones_estado', 'suscripciones_fundacion', ['estado'])
    if not _has_table('pagos_suscripcion'):
        op.create_table(
            'pagos_suscripcion',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), nullable=False),
            sa.Column('suscripcion_id', sa.Integer()),
            sa.Column('plan_id', sa.Integer()),
            sa.Column('valor_pagado', sa.Numeric(14, 2), nullable=False),
            sa.Column('metodo_pago', sa.String(length=60), nullable=False),
            sa.Column('fecha_pago', sa.String(length=40), nullable=False),
            sa.Column('fecha_vencimiento', sa.String(length=40), nullable=False),
            sa.Column('referencia_pago', sa.String(length=160)),
            sa.Column('comprobante_nombre', sa.String(length=260)),
            sa.Column('comprobante_ruta', sa.Text()),
            sa.Column('usuario_registra_id', sa.Integer()),
            sa.Column('observaciones', sa.Text()),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(length=40)),
        )
        op.create_index('idx_pagos_fundacion', 'pagos_suscripcion', ['fundacion_id'])
        op.create_index('idx_pagos_fecha', 'pagos_suscripcion', ['fecha_pago'])
    if not _has_table('paquetes_credito'):
        op.create_table(
            'paquetes_credito',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('nombre', sa.String(length=120), nullable=False, unique=True),
            sa.Column('creditos', sa.Integer(), nullable=False),
            sa.Column('precio', sa.Numeric(14, 2), server_default='0'),
            sa.Column('estado', sa.String(length=30), server_default='ACTIVO'),
            sa.Column('personalizado', sa.Boolean(), server_default=sa.text('false')),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(length=40)),
        )
    if not _has_table('movimientos_credito'):
        op.create_table(
            'movimientos_credito',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), nullable=False),
            sa.Column('suscripcion_id', sa.Integer()),
            sa.Column('tipo', sa.String(length=40), nullable=False),
            sa.Column('accion', sa.String(length=120)),
            sa.Column('creditos', sa.Integer(), nullable=False),
            sa.Column('saldo_anterior', sa.Integer(), server_default='0'),
            sa.Column('saldo_nuevo', sa.Integer(), server_default='0'),
            sa.Column('referencia_tipo', sa.String(length=80)),
            sa.Column('referencia_id', sa.String(length=120)),
            sa.Column('descripcion', sa.Text()),
            sa.Column('usuario_id', sa.Integer()),
            sa.Column('fecha_movimiento', sa.String(length=40), nullable=False),
        )
        op.create_index('idx_mov_credito_fundacion', 'movimientos_credito', ['fundacion_id'])
        op.create_index('idx_mov_credito_fecha', 'movimientos_credito', ['fecha_movimiento'])
    if not _has_table('modulos_plan'):
        op.create_table(
            'modulos_plan',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('plan_id', sa.Integer(), nullable=False),
            sa.Column('modulo_codigo', sa.String(length=120), nullable=False),
            sa.Column('habilitado', sa.Boolean(), server_default=sa.text('true')),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.UniqueConstraint('plan_id', 'modulo_codigo', name='uq_modulos_plan_modulo'),
        )
    if not _has_table('historial_suscripcion'):
        op.create_table(
            'historial_suscripcion',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer(), nullable=False),
            sa.Column('suscripcion_id', sa.Integer()),
            sa.Column('accion', sa.String(length=120), nullable=False),
            sa.Column('estado_anterior', sa.String(length=40)),
            sa.Column('estado_nuevo', sa.String(length=40)),
            sa.Column('plan_anterior_id', sa.Integer()),
            sa.Column('plan_nuevo_id', sa.Integer()),
            sa.Column('datos_anteriores', sa.Text()),
            sa.Column('datos_nuevos', sa.Text()),
            sa.Column('usuario_id', sa.Integer()),
            sa.Column('fecha_accion', sa.String(length=40), nullable=False),
        )
    if not _has_table('auditoria_facturacion'):
        op.create_table(
            'auditoria_facturacion',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('usuario_id', sa.Integer()),
            sa.Column('username', sa.String(length=120)),
            sa.Column('fundacion_id', sa.Integer()),
            sa.Column('accion', sa.String(length=120), nullable=False),
            sa.Column('tabla_afectada', sa.String(length=120)),
            sa.Column('registro_id', sa.Integer()),
            sa.Column('datos_anteriores', sa.Text()),
            sa.Column('datos_nuevos', sa.Text()),
            sa.Column('ip', sa.String(length=80)),
            sa.Column('user_agent', sa.Text()),
            sa.Column('fecha', sa.String(length=40), nullable=False),
        )

    # Panel comercial y soporte
    if not _has_table('pc_tickets_soporte'):
        op.create_table(
            'pc_tickets_soporte',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer()),
            sa.Column('titulo', sa.String(length=240), nullable=False),
            sa.Column('descripcion', sa.Text()),
            sa.Column('categoria', sa.String(length=80), server_default='Soporte general'),
            sa.Column('prioridad', sa.String(length=30), server_default='MEDIA'),
            sa.Column('estado', sa.String(length=40), server_default='ABIERTO'),
            sa.Column('modulo_origen', sa.String(length=120)),
            sa.Column('usuario_creador_id', sa.Integer()),
            sa.Column('usuario_asignado_id', sa.Integer()),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(length=40)),
            sa.Column('fecha_cierre', sa.String(length=40)),
            sa.Column('observaciones', sa.Text()),
        )
        op.create_index('idx_pc_tickets_fundacion', 'pc_tickets_soporte', ['fundacion_id'])
        op.create_index('idx_pc_tickets_estado', 'pc_tickets_soporte', ['estado'])
        op.create_index('idx_pc_tickets_prioridad', 'pc_tickets_soporte', ['prioridad'])
    if not _has_table('pc_ticket_comentarios'):
        op.create_table(
            'pc_ticket_comentarios',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('ticket_id', sa.Integer(), nullable=False),
            sa.Column('usuario_id', sa.Integer()),
            sa.Column('comentario', sa.Text(), nullable=False),
            sa.Column('archivo_nombre', sa.String(length=260)),
            sa.Column('archivo_ruta', sa.Text()),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
        )
    if not _has_table('pc_alertas_pago'):
        op.create_table(
            'pc_alertas_pago',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer()),
            sa.Column('tipo', sa.String(length=80), nullable=False),
            sa.Column('nivel', sa.String(length=40), server_default='AMARILLO'),
            sa.Column('mensaje', sa.Text(), nullable=False),
            sa.Column('estado', sa.String(length=40), server_default='ABIERTA'),
            sa.Column('referencia_tipo', sa.String(length=80)),
            sa.Column('referencia_id', sa.String(length=120)),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(length=40)),
        )
        op.create_index('idx_pc_alertas_fundacion', 'pc_alertas_pago', ['fundacion_id'])
        op.create_index('idx_pc_alertas_estado', 'pc_alertas_pago', ['estado'])
    if not _has_table('pc_auditoria'):
        op.create_table(
            'pc_auditoria',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('usuario_id', sa.Integer()),
            sa.Column('username', sa.String(length=120)),
            sa.Column('fundacion_id', sa.Integer()),
            sa.Column('accion', sa.String(length=120), nullable=False),
            sa.Column('tabla_afectada', sa.String(length=120)),
            sa.Column('registro_id', sa.Integer()),
            sa.Column('datos_anteriores', sa.Text()),
            sa.Column('datos_nuevos', sa.Text()),
            sa.Column('ip', sa.String(length=80)),
            sa.Column('user_agent', sa.Text()),
            sa.Column('fecha', sa.String(length=40), nullable=False),
        )

    # Gerencia general
    if not _has_table('gg_auditoria'):
        op.create_table(
            'gg_auditoria',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer()),
            sa.Column('usuario_id', sa.Integer()),
            sa.Column('accion', sa.String(length=120), nullable=False),
            sa.Column('detalle', sa.Text()),
            sa.Column('datos', sa.Text()),
            sa.Column('ip', sa.String(length=80)),
            sa.Column('user_agent', sa.Text()),
            sa.Column('fecha', sa.String(length=40), nullable=False),
        )
        op.create_index('idx_gg_auditoria_fundacion', 'gg_auditoria', ['fundacion_id'])
        op.create_index('idx_gg_auditoria_fecha', 'gg_auditoria', ['fecha'])
    if not _has_table('gg_configuracion'):
        op.create_table(
            'gg_configuracion',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('fundacion_id', sa.Integer()),
            sa.Column('clave', sa.String(length=120), nullable=False),
            sa.Column('valor', sa.Text()),
            sa.Column('fecha_creacion', sa.String(length=40), nullable=False),
            sa.Column('fecha_actualizacion', sa.String(length=40)),
            sa.UniqueConstraint('fundacion_id', 'clave', name='uq_gg_configuracion_fundacion_clave'),
        )
        op.create_index('idx_gg_config_fundacion', 'gg_configuracion', ['fundacion_id'])


def downgrade() -> None:
    for table in [
        'gg_configuracion', 'gg_auditoria',
        'pc_auditoria', 'pc_alertas_pago', 'pc_ticket_comentarios', 'pc_tickets_soporte',
        'auditoria_facturacion', 'historial_suscripcion', 'modulos_plan', 'movimientos_credito',
        'paquetes_credito', 'pagos_suscripcion', 'suscripciones_fundacion', 'planes_suscripcion',
    ]:
        op.drop_table(table)
