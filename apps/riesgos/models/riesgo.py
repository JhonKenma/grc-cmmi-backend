# apps/riesgos/models/riesgo.py
"""
Modelo principal de Riesgo.
Soporta tanto versión básica (COSO) como avanzada (ISO 31000 + NIST).
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from apps.core.models import BaseModel
from apps.empresas.models import Empresa
from .categoria import CategoriaRiesgo


class Riesgo(BaseModel):
    """
    Riesgo identificado en una empresa.

    Flujo:
    1. Analista identifica y registra el riesgo (estado: borrador)
    2. Analista evalúa probabilidad e impacto → sistema calcula nivel
    3. Administrador revisa y aprueba (estado: aprobado)
    4. Se crea plan de tratamiento
    5. Dueño del riesgo ejecuta el tratamiento
    6. Analista monitorea y actualiza estado
    """

    # ── Estados ────────────────────────────────────────────────────────────────
    ESTADO_CHOICES = [
        ('borrador',   'Borrador'),       # Recién creado, sin aprobar
        ('en_revision','En Revisión'),    # Enviado al administrador
        ('aprobado',   'Aprobado'),       # Aprobado, activo para tratamiento
        ('en_tratamiento', 'En Tratamiento'),  # Con plan de tratamiento activo
        ('mitigado',   'Mitigado'),       # Tratamiento completado
        ('aceptado',   'Aceptado'),       # Aceptado conscientemente
        ('cerrado',    'Cerrado'),        # Ya no aplica
    ]

    # ── Nivel de riesgo calculado ──────────────────────────────────────────────
    NIVEL_CHOICES = [
        ('bajo',    'Bajo'),      # 1-5
        ('medio',   'Medio'),     # 6-10
        ('alto',    'Alto'),      # 11-15
        ('critico', 'Crítico'),   # 16-25
    ]

    # ── Fuente del riesgo (ISO 31000) ──────────────────────────────────────────
    FUENTE_CHOICES = [
        ('interno',  'Interno'),
        ('externo',  'Externo'),
        ('mixto',    'Mixto'),
    ]

    # ── Velocidad de materialización (NIST) ────────────────────────────────────
    VELOCIDAD_CHOICES = [
        ('inmediata',  'Inmediata (días)'),
        ('corto_plazo','Corto Plazo (semanas)'),
        ('medio_plazo','Medio Plazo (meses)'),
        ('largo_plazo','Largo Plazo (años)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identificación ─────────────────────────────────────────────────────────
    codigo = models.CharField(
        max_length=20,
        verbose_name='Código',
        help_text='Ej: R-001, R-TI-001'
    )

    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del Riesgo',
        help_text='Ej: Fuga de información de clientes'
    )

    descripcion = models.TextField(
        verbose_name='Descripción detallada'
    )

    # ── Relaciones ─────────────────────────────────────────────────────────────
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='riesgos',
        verbose_name='Empresa'
    )

    categoria = models.ForeignKey(
        CategoriaRiesgo,
        on_delete=models.PROTECT,
        related_name='riesgos',
        verbose_name='Categoría'
    )

    # ── Análisis causal ────────────────────────────────────────────────────────
    causa_raiz = models.TextField(
        verbose_name='Causa Raíz',
        help_text='¿Por qué podría ocurrir este riesgo?'
    )

    consecuencia = models.TextField(
        verbose_name='Consecuencia',
        help_text='¿Qué pasaría si el riesgo se materializa?'
    )

    escenarios = models.TextField(
        blank=True,
        default='',
        verbose_name='Escenarios posibles',
        help_text='ISO 31000: descripción de escenarios de materialización'
    )

    fuente = models.CharField(
        max_length=20,
        choices=FUENTE_CHOICES,
        default='interno',
        verbose_name='Fuente del Riesgo'
    )

    velocidad_materializacion = models.CharField(
        max_length=20,
        choices=VELOCIDAD_CHOICES,
        blank=True,
        default='',
        verbose_name='Velocidad de Materialización',
        help_text='NIST: ¿Qué tan rápido podría materializarse?'
    )

    # ── Evaluación básica (5x5) ────────────────────────────────────────────────
    probabilidad = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Probabilidad',
        help_text='1=Muy Baja, 2=Baja, 3=Media, 4=Alta, 5=Muy Alta'
    )

    impacto = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Impacto',
        help_text='1=Muy Bajo, 2=Bajo, 3=Medio, 4=Alto, 5=Crítico'
    )

    # Calculado automáticamente en save()
    nivel_riesgo = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Nivel de Riesgo',
        help_text='Probabilidad × Impacto (1-25). Calculado automáticamente.'
    )

    clasificacion = models.CharField(
        max_length=10,
        choices=NIVEL_CHOICES,
        default='bajo',
        verbose_name='Clasificación',
        help_text='Calculado automáticamente según nivel_riesgo'
    )

    # ── Evaluación avanzada (COSO ERM) ─────────────────────────────────────────
    nivel_riesgo_inherente = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Nivel de Riesgo Inherente',
        help_text='Nivel de riesgo SIN controles aplicados'
    )

    nivel_riesgo_residual = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Nivel de Riesgo Residual',
        help_text='Nivel de riesgo CON controles aplicados'
    )

    apetito_riesgo = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(25)],
        verbose_name='Apetito de Riesgo',
        help_text='COSO ERM: nivel máximo de riesgo aceptable para la empresa'
    )

    tolerancia_riesgo = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(25)],
        verbose_name='Tolerancia de Riesgo',
        help_text='COSO ERM: límite máximo antes de acción inmediata'
    )

    eficacia_controles = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Eficacia de Controles (%)',
        help_text='% de efectividad de los controles aplicados'
    )

    # ── Evaluación cuantitativa (ALE) ──────────────────────────────────────────
    sle = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='SLE - Pérdida por Evento Único ($)',
        help_text='Single Loss Expectancy: cuánto se perdería si ocurre una vez'
    )

    aro = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='ARO - Frecuencia Anual',
        help_text='Annual Rate of Occurrence: veces que ocurre por año (ej: 0.5 = cada 2 años)'
    )

    ale = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='ALE - Pérdida Anual Esperada ($)',
        help_text='Annual Loss Expectancy = SLE × ARO. Calculado automáticamente.'
    )

    moneda = models.CharField(
        max_length=5,
        default='USD',
        verbose_name='Moneda',
        choices=[('USD', 'USD'), ('PEN', 'PEN'), ('EUR', 'EUR')]
    )

    # ── Responsables ───────────────────────────────────────────────────────────
    identificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='riesgos_identificados',
        verbose_name='Identificado por'
    )

    dueno_riesgo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='riesgos_a_cargo',
        verbose_name='Dueño del Riesgo',
        help_text='Responsable de ejecutar el tratamiento'
    )

    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='riesgos_aprobados',
        verbose_name='Aprobado por'
    )

    # ── Estado y fechas ────────────────────────────────────────────────────────
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='borrador',
        verbose_name='Estado'
    )

    fecha_identificacion = models.DateField(
        verbose_name='Fecha de Identificación'
    )

    fecha_aprobacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Aprobación'
    )

    fecha_revision = models.DateField(
        null=True,
        blank=True,
        verbose_name='Próxima Revisión'
    )

    frecuencia_revision = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=[
            ('mensual',    'Mensual'),
            ('trimestral', 'Trimestral'),
            ('semestral',  'Semestral'),
            ('anual',      'Anual'),
        ],
        verbose_name='Frecuencia de Revisión',
        help_text='ISO 31000: se sugiere automáticamente según clasificación'
    )

    # ── Contexto adicional (ISO 31000) ─────────────────────────────────────────
    contexto = models.TextField(
        blank=True,
        default='',
        verbose_name='Contexto interno/externo',
        help_text='ISO 31000: contexto organizacional del riesgo'
    )

    criterio_riesgo = models.TextField(
        blank=True,
        default='',
        verbose_name='Criterio de Riesgo',
        help_text='ISO 31000: criterios usados para evaluar este riesgo'
    )

    documentacion = models.TextField(
        blank=True,
        default='',
        verbose_name='Documentación / Evidencia',
        help_text='Referencias a documentos o evidencias relacionadas'
    )

    notas = models.TextField(
        blank=True,
        default='',
        verbose_name='Notas adicionales'
    )

    class Meta:
        db_table = 'riesgos'
        verbose_name = 'Riesgo'
        verbose_name_plural = 'Riesgos'
        ordering = ['-nivel_riesgo', '-fecha_identificacion']
        unique_together = [['empresa', 'codigo']]
        indexes = [
            models.Index(fields=['empresa', 'estado']),
            models.Index(fields=['empresa', 'clasificacion']),
            models.Index(fields=['dueno_riesgo', 'estado']),
            models.Index(fields=['categoria', 'clasificacion']),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre} ({self.get_clasificacion_display()})"

    # ── Lógica de negocio ──────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        # 1. Calcular nivel de riesgo
        self.nivel_riesgo = self.probabilidad * self.impacto

        # 2. Clasificar automáticamente
        self.clasificacion = self._calcular_clasificacion(self.nivel_riesgo)

        # 3. Calcular ALE si hay SLE y ARO
        if self.sle is not None and self.aro is not None:
            self.ale = float(self.sle) * float(self.aro)

        # 4. Sugerir frecuencia de revisión si no está definida
        if not self.frecuencia_revision:
            self.frecuencia_revision = self._sugerir_frecuencia_revision()

        super().save(*args, **kwargs)

    @staticmethod
    def _calcular_clasificacion(nivel):
        if nivel <= 5:
            return 'bajo'
        elif nivel <= 10:
            return 'medio'
        elif nivel <= 15:
            return 'alto'
        else:
            return 'critico'

    def _sugerir_frecuencia_revision(self):
        """ISO 31000: frecuencia de revisión según nivel de riesgo."""
        return {
            'critico': 'mensual',
            'alto':    'trimestral',
            'medio':   'semestral',
            'bajo':    'anual',
        }.get(self.clasificacion, 'trimestral')

    @property
    def esta_sobre_apetito(self):
        """COSO ERM: ¿el riesgo supera el apetito definido?"""
        if self.apetito_riesgo is None:
            return None
        return self.nivel_riesgo > self.apetito_riesgo

    @property
    def estado_apetito(self):
        """COSO ERM: estado respecto al apetito de riesgo."""
        if self.apetito_riesgo is None:
            return 'sin_configurar'
        residual = self.nivel_riesgo_residual or self.nivel_riesgo
        if residual > self.tolerancia_riesgo if self.tolerancia_riesgo else False:
            return 'requiere_tratamiento_inmediato'
        if residual > self.apetito_riesgo:
            return 'requiere_tratamiento'
        return 'dentro_de_apetito'