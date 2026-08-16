from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_schema_ddl_is_not_run_by_route_registration_or_requests() -> None:
    billing_routes = _text('backend/modules/facturacion_suscripcion/routes.py')
    billing_middleware = _text('backend/modules/facturacion_suscripcion/services.py')
    panel_routes = _text('backend/modules/panel_comercial/routes.py')
    master_routes = _text('backend/modules/base_maestra/routes.py')

    assert 'service.init()' not in billing_routes
    assert 'def _ensure_schema' not in billing_routes
    assert 'service.init()\n\n    @app.before_request' not in billing_middleware
    assert 'service.init_schema()' not in panel_routes
    assert 'def _ensure_schema' not in panel_routes
    assert 'repo.init_schema()' not in master_routes


def test_runtime_guard_precedes_hosting_import_and_migrations_are_explicit() -> None:
    startup = _text('start_hosting.sh')
    init_hosting = _text('backend/init_hosting.py')

    assert startup.index('export SKIP_RUNTIME_SCHEMA_DDL=1') < startup.index('python backend/init_hosting.py')
    assert init_hosting.index("os.environ['SKIP_RUNTIME_SCHEMA_DDL'] = '1'") < init_hosting.index('import app as app_module')
    assert 'BillingService(BillingRepository(config_class.DATABASE_PATH)).init(force=True)' in init_hosting
    assert 'PanelComercialService(config_class.DATABASE_PATH).init_schema()' in init_hosting
    assert 'BaseMaestraRepository(config_class.DATABASE_PATH).init_schema()' in init_hosting


def test_repository_runtime_guards_are_present() -> None:
    for relative in (
        'backend/modules/facturacion_suscripcion/repository.py',
        'backend/modules/base_maestra/repository.py',
    ):
        source = _text(relative)
        assert "os.getenv('SKIP_RUNTIME_SCHEMA_DDL'" in source


if __name__ == '__main__':
    test_schema_ddl_is_not_run_by_route_registration_or_requests()
    test_runtime_guard_precedes_hosting_import_and_migrations_are_explicit()
    test_repository_runtime_guards_are_present()
    print('STARTUP_MIGRATION_BOUNDARY_PASS')
