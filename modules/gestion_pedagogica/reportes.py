"""
Reportes del módulo Gestión Pedagógica.
La primera fase retorna JSON listo para convertir en Excel/PDF en fases posteriores.
"""

from .services import reporte_mensual

__all__ = ['reporte_mensual']
