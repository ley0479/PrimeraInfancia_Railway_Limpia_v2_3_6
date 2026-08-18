from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    registry_path = ROOT / "integrity" / "format_capabilities.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["scope"] == "ALL_FORMATS"
    assert registry["policy"]["default_protection"] == "PROTECTED"
    assert registry["policy"]["unknown_formats"] == "AUTO_REGISTER_AND_BLOCK_UNTESTED"
    assert registry["policy"]["regression_test_required"] is True
    assert registry["policy"]["deployment_on_failure"] == "BLOCKED"
    assert "OTROS_DINAMICOS" in registry["format_families"]
    assert len(registry["universal_capabilities"]) >= 10

    gate = (ROOT / "backend" / "tools" / "integrity_gate.py").read_text(encoding="utf-8")
    assert "check_format_registry" in gate
    assert "gate.check_format_registry()" in gate
    print("OK: continuidad y no regresión aplican a todos los formatos")


if __name__ == "__main__":
    main()
