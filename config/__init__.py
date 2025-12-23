# config/__init__.py
# ⭐ AGREGAR ESTAS LÍNEAS AL ARCHIVO

from .celery import app as celery_app

__all__ = ('celery_app',)