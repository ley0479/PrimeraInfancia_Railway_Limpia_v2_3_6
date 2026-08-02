"""
Motor maestro de impresión para formatos oficiales ICBF.

Alpha13 refuerza el motor maestro de impresión oficial:
- No se usa ws.dimensions como área de impresión cuando la plantilla trae
  columnas/filas con formato hasta columnas lejanas (ej. CP), porque eso crea
  páginas en blanco.
- Bienestarina se configura como Legal horizontal, respetando la orientación
  real de la plantilla oficial.
- Se conservan los colores, bordes, combinaciones y estilos oficiales; el motor
  solo ajusta configuración de página e impresión.
- Recalcula áreas seguras, elimina saltos manuales heredados y fuerza una página
  de ancho para evitar hojas en blanco laterales.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

CM_TO_INCH = 1 / 2.54

# Excel / OOXML paperSize: Folio 8.5 x 13 pulgadas.
# Openpyxl no siempre expone una constante para este tamaño; el valor OOXML
# utilizado por Excel para Folio es 14.
PAPERSIZE_FOLIO_8_5_X_13 = 14

PRINT_MASTER_CONFIG: dict[str, dict[str, Any]] = {
    "rpp": {
        "label": "Formato RPP",
        "pageSize": "A4",
        "cssPageSize": "A4 landscape",
        "excelPaperSize": "A4",
        "orientation": "landscape",
        "scale": 35,
        "preserveTemplatePrintArea": False,
        "forceSafePrintArea": True,
        "autoPrintAreaWhenMissing": True,
        "fitToWidth": 1,
        "fitToHeight": 0,
        "margins": {
            "top": 1.91,
            "bottom": 1.91,
            "left": 0.76,
            "right": 0.64,
            "header": 0.76,
            "footer": 0.76,
        },
    },
    "bienestarina": {
        "label": "Formato Bienestarina",
        "pageSize": "Legal",
        "cssPageSize": "Legal landscape",
        "excelPaperSize": "LEGAL",
        "orientation": "landscape",
        "scale": 55,
        "preserveTemplatePrintArea": False,
        "forceSafePrintArea": True,
        "autoPrintAreaWhenMissing": True,
        "fitToWidth": 1,
        "fitToHeight": 0,
        "margins": {
            "top": 1.91,
            "bottom": 1.91,
            "left": 0.64,
            "right": 0.64,
            "header": 0.76,
            "footer": 0.76,
        },
    },
    "ram_ran": {
        "label": "Formato RAM/RAN/Asistencia",
        "pageSize": "8.5x13",
        "cssPageSize": "13in 8.5in",
        "excelPaperSize": "FOLIO",
        "orientation": "landscape",
        "scale": 60,
        "preserveTemplateMargins": True,
        "preserveTemplatePrintArea": False,
        "forceSafePrintArea": True,
        "autoPrintAreaWhenMissing": True,
        "fitToWidth": 1,
        "fitToHeight": 0,
        "margins": None,
    },
}

ALIAS_PRINT_FORMATS = {
    "rpp": "rpp",
    "registro procedencia procedimiento": "rpp",
    "bienestarina": "bienestarina",
    "bienestarina del mes": "bienestarina",
    "ram": "ram_ran",
    "ran": "ram_ran",
    "run": "ram_ran",
    "rran": "ram_ran",
    "asistencia": "ram_ran",
    "registro asistencia mensual": "ram_ran",
    "registro de asistencia mensual": "ram_ran",
}


def cm_to_in(cm: float | int | str | None) -> float:
    """Convierte centímetros a pulgadas para openpyxl."""
    try:
        return float(cm) * CM_TO_INCH
    except Exception:
        return 0.0


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.replace("º", "o").replace("°", "o")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def infer_print_format(value: Any) -> str | None:
    """Detecta el tipo de impresión desde nombre, ruta, código o etiqueta."""
    text = normalizar_texto(value)
    if not text:
        return None

    # Prioridad explícita: RPP y Bienestarina antes que RAM/RAN.
    if "bienestarina" in text:
        return "bienestarina"
    if "rpp" in text or "registro procedencia" in text:
        return "rpp"
    if any(token in text for token in ["rran", "ram", "ran", "run", "asistencia", "registro asistencia"]):
        return "ram_ran"

    return ALIAS_PRINT_FORMATS.get(text)


def get_print_config(tipo_formato: str | None) -> dict[str, Any] | None:
    tipo = infer_print_format(tipo_formato) or str(tipo_formato or "").strip().lower()
    return PRINT_MASTER_CONFIG.get(tipo)


def _paper_size_value(ws: Any, excel_paper_size: str | None) -> int | None:
    paper = str(excel_paper_size or "").strip().upper()
    if paper == "A4":
        return getattr(ws, "PAPERSIZE_A4", 9)
    if paper in {"LEGAL", "OFICIO_LEGAL"}:
        return getattr(ws, "PAPERSIZE_LEGAL", 5)
    if paper in {"FOLIO", "8.5X13", "8_5X13", "8.5 X 13"}:
        return PAPERSIZE_FOLIO_8_5_X_13
    return None


def _orientation_value(ws: Any, orientation: str | None) -> str:
    value = str(orientation or "portrait").strip().lower()
    if value == "landscape":
        return getattr(ws, "ORIENTATION_LANDSCAPE", "landscape")
    return getattr(ws, "ORIENTATION_PORTRAIT", "portrait")


def _index_to_col(index: int) -> str:
    """Convierte índice de columna 1-based a letra Excel sin depender de utilidades externas."""
    index = int(index or 1)
    letters = ""
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters or "A"


def _cell_has_value(cell: Any) -> bool:
    value = getattr(cell, "value", None)
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    return True


def _cell_has_border(cell: Any) -> bool:
    try:
        border = getattr(cell, "border", None)
        if not border:
            return False
        return any(
            getattr(side, "style", None)
            for side in [border.left, border.right, border.top, border.bottom]
        )
    except Exception:
        return False


def _has_print_area(ws: Any) -> bool:
    try:
        area = getattr(ws, "print_area", None)
        if isinstance(area, (list, tuple)):
            return bool(area)
        return bool(str(area or "").strip())
    except Exception:
        return False


def detectar_area_util_impresion(ws: Any) -> str | None:
    """Detecta un área de impresión real sin incluir columnas vacías con formato.

    Varias plantillas oficiales tienen formato/colores hasta columnas muy lejanas
    (por ejemplo CP) aunque la información del formato termina alrededor de S/AL.
    Usar ws.dimensions en esos casos genera páginas en blanco. Por eso el área se
    calcula desde celdas con valor y se expande solo hasta bordes cercanos.
    """
    min_row = None
    min_col = None
    max_row = 0
    max_col = 0

    try:
        max_scan_row = min(int(getattr(ws, "max_row", 1) or 1), 300)
        max_scan_col = min(int(getattr(ws, "max_column", 1) or 1), 120)
    except Exception:
        return None

    for row in ws.iter_rows(min_row=1, max_row=max_scan_row, min_col=1, max_col=max_scan_col):
        for cell in row:
            if not _cell_has_value(cell):
                continue
            min_row = cell.row if min_row is None else min(min_row, cell.row)
            min_col = cell.column if min_col is None else min(min_col, cell.column)
            max_row = max(max_row, cell.row)
            max_col = max(max_col, cell.column)

    if min_row is None or min_col is None or max_row <= 0 or max_col <= 0:
        return None

    # Mantener siempre el encabezado desde A1 en formatos oficiales.
    min_row = 1
    min_col = 1

    # Expandir únicamente a bordes cercanos al contenido real. Esto conserva
    # tablas/firmas del formato sin tragarse columnas fantasma con color/formato.
    row_limit = min(max_scan_row, max_row + 8)
    col_limit = min(max_scan_col, max_col + 8)
    for row in ws.iter_rows(min_row=min_row, max_row=row_limit, min_col=min_col, max_col=col_limit):
        for cell in row:
            if _cell_has_border(cell):
                max_row = max(max_row, cell.row)
                max_col = max(max_col, cell.column)

    # Evitar rangos de una sola celda en hojas casi vacías.
    max_row = max(max_row, min_row)
    max_col = max(max_col, min_col)

    return f"{_index_to_col(min_col)}{min_row}:{_index_to_col(max_col)}{max_row}"


def _aplicar_area_impresion_segura(ws: Any, cfg: dict[str, Any]) -> None:
    """Aplica un área de impresión segura.

    Las plantillas oficiales no se modifican en contenido ni estilos, pero algunas
    traen áreas de impresión demasiado amplias o saltos heredados. Esa metadata
    provoca hojas en blanco al imprimir. Por eso se recalcula el área útil cuando
    forceSafePrintArea está activo.
    """
    preserve_existing = bool(cfg.get("preserveTemplatePrintArea", True))
    force_safe = bool(cfg.get("forceSafePrintArea", False))
    if preserve_existing and _has_print_area(ws) and not force_safe:
        return

    if not cfg.get("autoPrintAreaWhenMissing", True) and not force_safe:
        return

    area = detectar_area_util_impresion(ws)
    if not area:
        return

    try:
        ws.print_area = area
    except Exception:
        pass


def aplicar_configuracion_impresion(
    ws: Any,
    tipo_formato: str | None,
    *,
    preserve_template_margins: bool | None = None,
    set_print_area_when_missing: bool = True,
) -> Any:
    """Aplica configuración oficial de impresión a una hoja openpyxl."""
    tipo = infer_print_format(tipo_formato) or str(tipo_formato or "").strip().lower()
    cfg = PRINT_MASTER_CONFIG.get(tipo)
    if not cfg:
        return ws

    paper_size = _paper_size_value(ws, cfg.get("excelPaperSize"))
    if paper_size is not None:
        ws.page_setup.paperSize = paper_size

    ws.page_setup.orientation = _orientation_value(ws, cfg.get("orientation"))
    ws.page_setup.scale = int(cfg.get("scale") or 100)

    fit_to_width = cfg.get("fitToWidth")
    fit_to_height = cfg.get("fitToHeight")
    try:
        ws.sheet_properties.pageSetUpPr.fitToPage = bool(fit_to_width)
    except Exception:
        pass

    try:
        if fit_to_width:
            # Evita páginas en blanco horizontales en Excel sin alterar estructura.
            # Se conserva la escala oficial en el archivo, pero Excel puede priorizar
            # el ajuste a una página de ancho cuando imprime.
            ws.page_setup.fitToWidth = int(fit_to_width)
            ws.page_setup.fitToHeight = int(fit_to_height or 0)
        else:
            ws.page_setup.fitToWidth = None
            ws.page_setup.fitToHeight = None
    except Exception:
        pass

    preserve = cfg.get("preserveTemplateMargins", False) if preserve_template_margins is None else preserve_template_margins
    margins = cfg.get("margins")
    if margins and not preserve:
        ws.page_margins.top = cm_to_in(margins.get("top"))
        ws.page_margins.bottom = cm_to_in(margins.get("bottom"))
        ws.page_margins.left = cm_to_in(margins.get("left"))
        ws.page_margins.right = cm_to_in(margins.get("right"))
        ws.page_margins.header = cm_to_in(margins.get("header"))
        ws.page_margins.footer = cm_to_in(margins.get("footer"))

    try:
        ws.print_options.horizontalCentered = True
    except Exception:
        pass

    if set_print_area_when_missing:
        _aplicar_area_impresion_segura(ws, cfg)

    # Quitar saltos manuales heredados que generan hojas en blanco laterales
    # o inferiores en vista de impresión. No toca contenido ni estilos.
    try:
        ws.row_breaks.brk = []
    except Exception:
        pass
    try:
        ws.col_breaks.brk = []
    except Exception:
        pass

    return ws


def aplicar_configuracion_impresion_libro(
    wb: Any,
    tipo_formato: str | None = None,
    *,
    source_name: str | None = None,
    worksheets: Iterable[Any] | None = None,
) -> Any:
    """Aplica la configuración maestra a todas o algunas hojas de un libro."""
    tipo = infer_print_format(tipo_formato) or infer_print_format(source_name)
    if not tipo or tipo not in PRINT_MASTER_CONFIG:
        return wb

    hojas = list(worksheets) if worksheets is not None else list(getattr(wb, "worksheets", []) or [])
    for ws in hojas:
        aplicar_configuracion_impresion(ws, tipo)
    return wb


def print_master_config_public() -> dict[str, Any]:
    """Copia segura para entregar por API sin referencias mutables internas."""
    import copy

    return copy.deepcopy(PRINT_MASTER_CONFIG)
