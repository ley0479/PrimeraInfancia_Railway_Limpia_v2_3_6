from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print('Uso: python aplicar_patch.py "RUTA_AL_REPOSITORIO"')
        return 2

    repo = Path(sys.argv[1]).expanduser().resolve()
    payload = Path(__file__).resolve().parent / "payload"
    if not (repo / "backend" / "app.py").is_file() or not (repo / "frontend" / "index.html").is_file():
        print(f"ERROR: {repo} no parece ser la raíz válida del proyecto.")
        return 3

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = repo / f"backup_patch_calendario_v280_{stamp}"
    copied = []
    backups = []

    for source in sorted(p for p in payload.rglob("*") if p.is_file()):
        rel = source.relative_to(payload)
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = backup_root / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
            backups.append(str(rel))
        shutil.copy2(source, target)
        copied.append((str(rel), sha256(target)))

    checks = []
    app_text = (repo / "backend" / "app.py").read_text(encoding="utf-8", errors="replace")
    index_text = (repo / "frontend" / "index.html").read_text(encoding="utf-8", errors="replace")
    appjs_text = (repo / "frontend" / "js" / "app.js").read_text(encoding="utf-8", errors="replace")

    checks.append(("Registro backend calendario", "register_calendario_inteligente" in app_text))
    checks.append(("Registro backend centro de planeación", "register_centro_planeacion" in app_text))
    checks.append(("Script frontend calendario", "calendario-inteligente.js" in index_text))
    checks.append(("Script frontend centro de planeación", "centro-planeacion.js" in index_text))
    checks.append(("Sección calendario autorizada", "calendario-inteligente" in appjs_text))
    checks.append(("Sección centro planeación autorizada", "centro-planeacion" in appjs_text))

    report = repo / "REPORTE_APLICACION_PATCH.txt"
    with report.open("w", encoding="utf-8") as fh:
        fh.write("PATCH CALENDARIO / ENTREGABLES / LISTADOS\n")
        fh.write(f"Aplicado: {datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"Repositorio: {repo}\n")
        fh.write(f"Backup: {backup_root}\n\n")
        fh.write("ARCHIVOS COPIADOS\n")
        for rel, digest in copied:
            fh.write(f"- {rel} | sha256={digest}\n")
        fh.write("\nARCHIVOS RESPALDADOS\n")
        for rel in backups:
            fh.write(f"- {rel}\n")
        fh.write("\nVERIFICACIONES DE INTEGRACIÓN\n")
        for name, ok in checks:
            fh.write(f"- {'PASS' if ok else 'PENDIENTE'}: {name}\n")
        if not all(ok for _, ok in checks):
            fh.write("\nADVERTENCIA: faltan referencias de integración en archivos centrales. No despliegue hasta revisarlas manualmente.\n")

    print(f"Patch copiado. Reporte: {report}")
    print(f"Backup: {backup_root}")
    for name, ok in checks:
        print(f"{'PASS' if ok else 'PENDIENTE'} - {name}")
    return 0 if all(ok for _, ok in checks) else 4


if __name__ == "__main__":
    raise SystemExit(main())
