from __future__ import annotations
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = root / "SHA256SUMS.txt"
errors = []
for line in manifest.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    expected, rel = line.split("  ", 1)
    path = root / rel
    if not path.is_file():
        errors.append(f"FALTA: {rel}")
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        errors.append(f"HASH INCORRECTO: {rel}")
if errors:
    print("\n".join(errors))
    raise SystemExit(1)
print("PASS: todos los archivos del patch coinciden con el manifiesto SHA-256.")
