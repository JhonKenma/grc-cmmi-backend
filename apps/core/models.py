# apps/core/models.py
from django.db import models

class BaseModel(models.Model):
    """Modelo base abstracto con campos comunes de auditoría"""
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        abstract = True
        ordering = ['-fecha_creacion']