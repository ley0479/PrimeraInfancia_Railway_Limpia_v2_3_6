"""Contrato de rendimiento para descargas aisladas por fundación."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app.py"


def function_source(name: str) -> str:
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"No existe la función {name}")


def test_rpp_no_genera_paquete_completo() -> None:
    for name in ("_alpha61_generar_rpp_grupo", "_alpha64_generar_rpp_resiliente"):
        source = function_source(name)
        assert "_alpha61_generar_formatos_unidad(" not in source, (
            f"{name} todavía genera todos los formatos antes de un único RPP"
        )


def test_formatos_complementarios_tienen_generacion_directa() -> None:
    source = function_source("_alpha59_intentar_generar_faltante")
    for generator in (
        "_alpha68_generar_listado_usuarios",
        "_alpha68_generar_relacion_mensual",
        "_alpha68_generar_distribucion_alimentos",
        "_alpha65_generar_bienestarina_para_uds",
    ):
        assert generator in source, f"Falta ruta directa para {generator}"
    direct_position = source.index("directos =")
    legacy_position = source.index("inyectar_datos_en_plantillas")
    assert direct_position < legacy_position, "El fallback pesado se ejecuta antes del generador directo"


def test_listado_word_se_reutiliza() -> None:
    source = function_source("buscar_archivo_generado")
    assert "'.docx'" in source, "El buscador no reutiliza el listado oficial Word ya generado"


if __name__ == "__main__":
    test_rpp_no_genera_paquete_completo()
    test_formatos_complementarios_tienen_generacion_directa()
    test_listado_word_se_reutiliza()
    print("Descarga directa tenant v2.7.0: PASS")
