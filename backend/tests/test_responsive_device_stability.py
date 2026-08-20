"""Contrato estatico de estabilidad visual en celulares y tabletas."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "responsive-mobile.css").read_text(encoding="utf-8")
JS = (ROOT / "frontend" / "js" / "modules" / "responsive-mobile.js").read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    require('name="viewport" content="width=device-width, initial-scale=1.0"' in HTML, "Falta viewport movil")
    require("height: 100dvh" in CSS, "El shell no usa altura dinamica del dispositivo")
    require("@media (max-width: 480px)" in CSS and "@media (max-width: 767px)" in CSS, "Faltan cortes para celular")
    require("min-width: 768px) and (max-width: 1024px" in CSS, "Falta corte para tableta")
    require("pi-responsive-table-scroll" in CSS and "overflow-x: auto" in CSS, "Las tablas no tienen scroll seguro")
    require('input:not([type="checkbox"]):not([type="radio"])' in CSS, "Falta limite de controles")
    require("visualViewport?.addEventListener('resize'" in JS, "No responde al teclado/viewport movil")
    require("window.addEventListener('orientationchange'" in JS, "No responde a rotacion")
    require("scope.querySelectorAll('table').forEach(mejorarTabla)" in JS, "Las tablas dinamicas no se recalculan")
    require("2.3.4-responsive-stability" in HTML, "Los navegadores podrian conservar CSS/JS anterior en cache")
    print("Responsive estable: celular, tableta, rotacion, teclado y tablas dinamicas PASS")


if __name__ == "__main__":
    main()
