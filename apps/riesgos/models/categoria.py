# apps/riesgos/models/categoria.py
"""
Catálogo de categorías de riesgo.
Permite clasificar riesgos según estándares COSO ERM / ISO 31000.
"""

import uuid
from django.db import models
from apps.core.models import BaseModel
from apps.empresas.models import Empresa


class CategoriaRiesgo(BaseModel):
    """
    Categorías para clasificar riesgos.

    Hay dos tipos:
    - Globales (empresa=None): creadas por el SuperAdmin, disponibles para todas las empresas.
      Ejemplos: Operacional, Financiero, Legal, TI, RRHH, Estratégico, Cumplimiento, Reputacional
    - Propias (empresa=X): creadas por el Administrador de la empresa para sus necesidades específicas.

    Están alineadas con COSO ERM (8 categorías) e ISO 31000.
    """

    ESTANDAR_CHOICES = [
        ('coso',     'COSO ERM'),
        ('iso31000', 'ISO 31000'),
        ('nist',     'NIST SP 800-30'),
        ('propio',   'Propio'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='categorias_riesgo',
        null=True,
        blank=True,
        verbose_name='Empresa',
        help_text='Null = categoría global disponible para todas las empresas'
    )

    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre',
        help_text='Ej: Operacional, Financiero, TI, Legal, RRHH'
    )

    descripcion = models.TextField(
        blank=True,
        default='',
        verbose_name='Descripción'
    )

    estandar = models.CharField(
        max_length=20,
        choices=ESTANDAR_CHOICES,
        default='coso',
        verbose_name='Estándar de referencia'
    )

    icono = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='Icono',
        help_text='Nombre del icono para el frontend (ej: shield, alert-triangle)'
    )

    color = models.CharField(
        max_length=7,
        blank=True,
        default='#6B7280',
        verbose_name='Color HEX',
        help_text='Color para identificar visualmente la categoría en dashboards'
    )

    orden = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Orden de visualización'
    )

    class Meta:
        db_table = 'riesgo_categorias'
        verbose_name = 'Categoría de Riesgo'
        verbose_name_plural = 'Categorías de Riesgo'
        ordering = ['orden', 'nombre']
        unique_together = [['empresa', 'nombre']]
        indexes = [
            models.Index(fields=['empresa', 'activo']),
        ]

    def __str__(self):
        scope = self.empresa.nombre if self.empresa else 'Global'
        return f"{self.nombre} ({scope})"

    @property
    def es_global(self):
        return self.empresa is None