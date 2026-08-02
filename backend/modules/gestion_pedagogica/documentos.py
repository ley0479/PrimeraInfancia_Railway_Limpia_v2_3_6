"""
Utilidades para documentos de Gestión Pedagógica.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from werkzeug.utils import secure_filename


def ensure_document_folder(upload_folder: str) -> str:
    folder = os.path.join(upload_folder, 'gestion_pedagogica')
    os.makedirs(folder, exist_ok=True)
    return folder


def save_uploaded_document(file_storage, upload_folder: str, prefix: str = 'GP_DOCUMENTO') -> dict[str, Any]:
    folder = ensure_document_folder(upload_folder)
    original = secure_filename(file_storage.filename or 'documento')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    saved = f"{prefix}_{timestamp}_{original}"
    path = os.path.join(folder, saved)
    file_storage.save(path)
    return {
        'nombre_original': original,
        'nombre_guardado': saved,
        'ruta_archivo': path,
        'fecha_carga': datetime.now().isoformat(timespec='seconds'),
    }
