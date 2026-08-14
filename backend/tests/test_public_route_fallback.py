from pathlib import Path


def test_public_route_fallback_and_health_aliases_are_registered():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "@app.route('/health'" in source
    assert "@app.route('/api/ready'" in source
    assert "@app.route('/<path:client_path>'" in source
    assert "normalized.startswith('api/')" in source
    assert "return send_from_directory(frontend_dir, 'index.html')" in source
