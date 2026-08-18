"""Punto de entrada WSGI para Gunicorn/Waitress.

Ejemplos:
  gunicorn --chdir backend 'wsgi:application'
  waitress-serve --chdir=backend --call wsgi:create_application
"""
from __future__ import annotations

import os

from app import create_app


def create_application():
    return create_app(os.getenv("APP_ENV"))


application = create_application()
app = application
