"""Contrato de seguridad de la identidad global."""
from pathlib import Path


SERVICES = Path(__file__).resolve().parents[1] / "modules" / "seguridad" / "services.py"
INSTITUCIONAL = Path(__file__).resolve().parents[1] / "modules" / "institucional_normativo.py"


def main():
    security = SERVICES.read_text(encoding="utf-8")
    institutional = INSTITUCIONAL.read_text(encoding="utf-8")
    assert "'/api/configuracion-global', MANAGEMENT" in security
    assert "'/api/configuracion-publica'" in security
    assert "('/api/branding/global/',)" in security
    assert "normalized_path.startswith(prefix)" in security
    assert institutional.count("@require_roles('SUPERADMIN', 'GERENTE')") >= 5
    assert "ADMINISTRADOR_GENERAL" not in institutional
    print("Seguridad rutas identidad global v7: PASS")


if __name__ == "__main__":
    main()
