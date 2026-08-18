# Sistema Integral Administrativo y Financiero

Consolida la gestión operativa financiera sin sustituir contabilidad ni duplicar fuentes existentes. Los presupuestos se relacionan por `contrato_id`; las compras pueden referenciar rubros y proveedores; las legalizaciones referencian compras; las cuentas de cobro continúan en `cuentas_cobro_generadas` y el inventario físico permanece en Ambientes Protectores.

## Controles

- Aislamiento obligatorio por `fundacion_id`.
- Auditoría de cada creación en `af_auditoria`.
- Estados iniciales controlados: presupuesto `BORRADOR`, compra `SOLICITADA`, legalización `PENDIENTE`.
- Ningún registro automático equivale a aprobación, pago o legalización definitiva.
- Acceso para Superadmin, Gerencia, Coordinación y Auxiliar Administrativo.

## API

- `GET /api/administrativo-financiero/dashboard?vigencia=2026`
- `POST /api/administrativo-financiero/presupuestos`
- `POST /api/administrativo-financiero/proveedores`
- `POST /api/administrativo-financiero/compras`
- `POST /api/administrativo-financiero/movimientos`
- `POST /api/administrativo-financiero/legalizaciones`
