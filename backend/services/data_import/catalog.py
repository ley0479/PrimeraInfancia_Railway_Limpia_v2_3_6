from __future__ import annotations

CATALOG_VERSION = "2026.08.1"

CANONICAL_FIELDS = {
    "regional.nombre": {"aliases": ["nombre regional", "regional", "nombre de la regional de la unidad de servicio"]},
    "municipio.codigo": {"aliases": ["codigo municipio", "codigo del municipio de la unidad de servicio"]},
    "municipio.nombre": {"aliases": ["nombre municipio", "nombre municipio de la unidad de servicio"]},
    "centro_zonal.nombre": {"aliases": ["nombre centro zonal", "nombre del centro zonal", "centro zonal"]},
    "unidad.codigo": {"aliases": ["codigo de la unidad de servicio", "codigo unidad de servicio", "codigo unidad servicio", "codigo uds", "id unidad de servicio", "id uds", "identificador de unidad"]},
    "unidad.nombre": {"aliases": ["nombre de la unidad de servicio", "nombre unidad de servicio", "nombre unidad servicio", "nombre de la uds", "nombre uds", "unidad de servicio", "unidad servicio", "uds", "nombre sede", "nombre centro de atencion", "punto de atencion"]},
    "participante.tipo_documento": {"aliases": ["tipo documento beneficiario", "tipo de documento del beneficiario", "tipo documento"]},
    "participante.numero_documento": {"aliases": ["documento del beneficiario", "numero documento beneficiario", "numero de documento", "documento"]},
    "participante.nui": {"aliases": ["nui", "numero unico identificacion"]},
    "participante.nombre_completo": {"aliases": ["nombre completo beneficiario", "nombres y apellidos", "beneficiario"]},
    "participante.primer_nombre": {"aliases": ["primer nombre del beneficiario", "primer nombre"]},
    "participante.segundo_nombre": {"aliases": ["segundo nombre del beneficiario", "segundo nombre"]},
    "participante.primer_apellido": {"aliases": ["primer apellido del beneficiario", "primer apellido"]},
    "participante.segundo_apellido": {"aliases": ["segundo apellido del beneficiario", "segundo apellido"]},
    "participante.fecha_nacimiento": {"aliases": ["fecha de nacimiento del beneficiario", "fecha nacimiento"]},
    "participante.sexo": {"aliases": ["sexo del beneficiario", "sexo", "genero"]},
    "participante.estado": {"aliases": ["estado del beneficiario", "estado beneficiario"]},
    "participante.grupo_etario": {"aliases": ["grupo etario", "grupo de edad", "tipo de beneficiario"]},
    "nutricion.peso_kg": {"aliases": ["peso kg", "peso"]},
    "nutricion.talla_cm": {"aliases": ["talla cm", "talla", "estatura"]},
}

NEGATIVE_TERMS = {
    "unidad.nombre": {"regional": -120, "municipio": -120, "departamento": -120, "centro zonal": -110, "distrito": -110, "contrato": -100, "entidad": -100, "operador": -100, "codigo": -80, "documento": -100},
    "unidad.codigo": {"regional": -120, "departamento": -120, "municipio": -120, "centro zonal": -120, "contrato": -100, "operador": -100, "beneficiario": -120, "documento": -120, "nui": -120},
}

FORMAT_REQUIREMENTS = {
    "RAM": {"required": ["unidad.codigo", "unidad.nombre", "participante.numero_documento", "participante.nombre_completo"], "optional": ["participante.nui", "participante.fecha_nacimiento"]},
    "RPP": {"required": ["unidad.codigo", "unidad.nombre", "participante.nombre_completo", "participante.fecha_nacimiento", "participante.grupo_etario"]},
    "BIENESTARINA": {"required": ["unidad.codigo", "unidad.nombre", "participante.numero_documento", "participante.nombre_completo"]},
    "LISTADO_ASISTENCIA": {"required": ["unidad.codigo", "unidad.nombre", "participante.numero_documento", "participante.nombre_completo"]},
}
