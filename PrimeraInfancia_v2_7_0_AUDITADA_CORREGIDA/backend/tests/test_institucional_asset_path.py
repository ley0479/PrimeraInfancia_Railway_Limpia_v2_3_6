from pathlib import PureWindowsPath


def test_institutional_asset_relative_path_uses_url_separators():
    root = PureWindowsPath(r"C:\data\tenants\1\institutional")
    asset = root / "uploads" / "fotos_admin" / "foto.png"

    assert asset.relative_to(root).as_posix() == "uploads/fotos_admin/foto.png"
