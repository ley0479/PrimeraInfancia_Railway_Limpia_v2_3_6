"""
Reportes del módulo Salud y Nutrición Inteligente.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .services import now_iso


def sanitize_filename(texto: str) -> str:
    import re
    texto = re.sub(r'[^A-Za-z0-9_\-]+', '_', str(texto or '')).strip('_')
    return texto or 'reporte'


def generar_excel_comparacion(resultado: dict[str, Any], output_folder: str) -> str:
    os.makedirs(output_folder, exist_ok=True)
    nombre = f"SALUD_NUTRICION_COMPARACION_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    ruta = os.path.join(output_folder, nombre)

    with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
        pd.DataFrame([resultado.get('resumen', {})]).to_excel(writer, sheet_name='Resumen', index=False)
        pd.DataFrame(resultado.get('nuevos', [])).to_excel(writer, sheet_name='Nuevos', index=False)
        pd.DataFrame(resultado.get('retirados', [])).to_excel(writer, sheet_name='Retirados', index=False)
        pd.DataFrame(resultado.get('trasladados', [])).to_excel(writer, sheet_name='Trasladados', index=False)

        cambios_rows = []
        for item in resultado.get('cambios', []):
            base = {'documento': item.get('documento'), 'nombre': item.get('nombre')}
            for campo, valores in item.get('cambios', {}).items():
                cambios_rows.append({
                    **base,
                    'campo': campo,
                    'anterior': valores.get('anterior', ''),
                    'actual': valores.get('actual', ''),
                })
        pd.DataFrame(cambios_rows).to_excel(writer, sheet_name='Cambios', index=False)

    return ruta


def generar_pdf_comparacion(resultado: dict[str, Any], output_folder: str) -> str:
    os.makedirs(output_folder, exist_ok=True)
    nombre = f"SALUD_NUTRICION_COMPARACION_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    ruta = os.path.join(output_folder, nombre)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(ruta, pagesize=landscape(letter), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    story = [
        Paragraph('Reporte de comparación de bases - Salud y Nutrición', styles['Title']),
        Paragraph(f'Fecha de generación: {datetime.now().strftime("%Y-%m-%d %H:%M")}', styles['Normal']),
        Spacer(1, 12),
    ]

    resumen = resultado.get('resumen', {})
    data = [['Indicador', 'Valor']] + [[k.replace('_', ' ').title(), str(v)] for k, v in resumen.items()]
    table = Table(data, colWidths=[240, 140])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9eaf7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))

    for titulo, key in [('Niños nuevos', 'nuevos'), ('Niños retirados', 'retirados'), ('Traslados/cambios de unidad', 'trasladados')]:
        story.append(Paragraph(titulo, styles['Heading2']))
        rows = resultado.get(key, [])[:25]
        if rows:
            table_data = [['Documento', 'Nombre', 'Unidad', 'Docente']] + [
                [r.get('documento', ''), r.get('nombre', ''), r.get('unidad', ''), r.get('docente', '')]
                for r in rows
            ]
            t = Table(table_data, colWidths=[90, 220, 120, 160])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ]))
            story.append(t)
        else:
            story.append(Paragraph('Sin registros.', styles['Normal']))
        story.append(Spacer(1, 10))

    doc.build(story)
    return ruta


def generar_excel_dashboard(data: dict[str, Any], output_folder: str, periodo: str | None = None) -> str:
    os.makedirs(output_folder, exist_ok=True)
    nombre = f"SALUD_NUTRICION_DASHBOARD_{sanitize_filename(periodo or 'GENERAL')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    ruta = os.path.join(output_folder, nombre)
    resumen = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
    with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
        pd.DataFrame([resumen]).to_excel(writer, sheet_name='Resumen', index=False)
        for key in ['por_sexo', 'por_edad', 'por_unidad', 'por_diagnostico', 'por_estado_control']:
            items = data.get(key, {})
            pd.DataFrame([{'categoria': k, 'total': v} for k, v in items.items()]).to_excel(
                writer, sheet_name=key[:31], index=False
            )
        pd.DataFrame(data.get('ultimos_casos', [])).to_excel(writer, sheet_name='Casos', index=False)
        pd.DataFrame(data.get('tendencias', [])).to_excel(writer, sheet_name='Tendencias', index=False)
    return ruta


def generar_pdf_dashboard(data: dict[str, Any], output_folder: str, periodo: str | None = None) -> str:
    os.makedirs(output_folder, exist_ok=True)
    nombre = f"SALUD_NUTRICION_DASHBOARD_{sanitize_filename(periodo or 'GENERAL')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    ruta = os.path.join(output_folder, nombre)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(ruta, pagesize=landscape(letter), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    story = [
        Paragraph('Dashboard Ejecutivo - Salud y Nutrición', styles['Title']),
        Paragraph(f'Periodo: {periodo or "General"}', styles['Normal']),
        Spacer(1, 12),
    ]

    resumen = [
        ['Total usuarios', data.get('total_usuarios', 0)],
        ['Total valorados', data.get('total_valorados', 0)],
        ['Pendientes', data.get('total_pendientes', 0)],
        ['Casos críticos', data.get('casos_criticos', 0)],
        ['Casos en seguimiento', data.get('casos_seguimiento', 0)],
        ['Cumplimiento %', data.get('cumplimiento', 0)],
    ]
    t = Table([['Indicador', 'Valor']] + resumen, colWidths=[220, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9eaf7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    story.append(Paragraph('Distribución por diagnóstico', styles['Heading2']))
    diag = data.get('por_diagnostico', {})
    if diag:
        table_data = [['Diagnóstico', 'Total']] + [[k, v] for k, v in diag.items()]
        td = Table(table_data, colWidths=[260, 80])
        td.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(td)

    doc.build(story)
    return ruta
