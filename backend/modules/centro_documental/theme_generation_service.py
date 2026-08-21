from __future__ import annotations


def generate_planning(theme: str, component: str, activity_type: str = "", population: str = "") -> dict:
    clean_theme = " ".join(str(theme or "").split())
    if not clean_theme:
        raise ValueError("El tema es obligatorio para generar la planeación.")
    context = ", ".join(value for value in (activity_type.strip(), population.strip()) if value)
    suffix = f" en {context}" if context else ""
    return {
        "clasificacion": "PLANEADO",
        "tema": clean_theme,
        "objetivo": f"Promover la comprensión y aplicación del tema «{clean_theme}»{suffix}.",
        "descripcion_planeada": f"Se desarrollará una experiencia participativa sobre «{clean_theme}», con apertura, actividad central y cierre reflexivo.",
        "metodologia": "Diálogo orientado, experiencia práctica y construcción de acuerdos.",
        "recursos": ["Material pedagógico disponible", "Recursos del entorno"],
        "logros_esperados": [f"Reconocer orientaciones relacionadas con {clean_theme}.", "Participar en la experiencia propuesta."],
        "dificultades_posibles": ["Disponibilidad limitada de tiempo", "Necesidad de adaptar los recursos"],
        "compromisos_sugeridos": ["Continuar la práctica acordada en el entorno familiar."],
        "recomendaciones_generales": ["Ajustar la actividad al contexto y registrar únicamente hechos observados."],
        "componente": str(component or "").upper(),
    }
