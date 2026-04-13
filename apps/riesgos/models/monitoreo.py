# apps/riesgos/models/monitoreo.py
"""
Monitoreo de riesgos y KRIs (Key Risk Indicators).
Permite hacer seguimiento continuo a los riesgos aprobados.
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from apps.core.models import BaseModel
from .riesgo import Riesgo


class KRI(BaseModel):
    """
    Key Risk Indicator — Indicador Clave de Riesgo.

    Un KRI es una métrica que alerta cuando un riesgo está
    aumentando o está a punto de materializarse.

    Ejemplo:
    - Riesgo: Ciberataque
    - KRI: Número de intentos de acceso fallidos por día
    - Umbral Amarillo: > 100 intentos/día
    - Umbral Rojo: > 500 intentos/día
    """

    TIPO_METRICA_CHOICES = [
        ('numero',      'Número'),
        ('porcentaje',  'Porcentaje (%)'),
        ('monetario',   'Monetario ($)'),
        ('booleano',    'Sí/No'),
        ('tiempo',      'Tiempo (días)'),
    ]

    ESTADO_CHOICES = [
        ('verde',     'Verde — Dentro del umbral'),
        ('amarillo',  'Amarillo — En zona de alerta'),
        ('rojo',      'Rojo — Umbral crítico superado'),
    ]

    FRECUENCIA_MEDICION_CHOICES = [
        ('diaria',     'Diaria'),
        ('semanal',    'Semanal'),
        ('mensual',    'Mensual'),
        ('trimestral', 'Trimestral'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    riesgo = models.ForeignKey(
        Riesgo,
        on_delete=models.CASCADE,
        related_name='kris',
        verbose_name='Riesgo asociado'
    )

    codigo = models.CharField(
        max_length=20,
        verbose_name='Código',
        help_text='Ej: KRI-001, KRI-TI-002'
    )

    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del Indicador'
    )

    descripcion = models.TextField(
        verbose_name='Descripción',
        help_text='¿Qué mide este indicador y por qué es relevante para el riesgo?'
    )

    tipo_metrica = models.CharField(
        max_length=20,
        choices=TIPO_METRICA_CHOICES,
        default='numero',
        verbose_name='Tipo de Métrica'
    )

    unidad_medida = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='Unidad de Medida',
        help_text='Ej: intentos/día, %, días, $'
    )

    # ── Umbrales ───────────────────────────────────────────────────────────────
    umbral_amarillo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Umbral Amarillo (Alerta)',
        help_text='Valor a partir del cual se activa la alerta amarilla'
    )

    umbral_rojo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Umbral Rojo (Crítico)',
        help_text='Valor a partir del cual se activa la alerta roja'
    )

    # ── Valor actual ───────────────────────────────────────────────────────────
    valor_actual = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Valor Actual'
    )

    estado_actual = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='verde',
        verbose_name='Estado Actual'
    )

    fecha_ultima_medicion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Última Medición'
    )

    # ── Configuración ──────────────────────────────────────────────────────────
    frecuencia_medicion = models.CharField(
        max_length=20,
        choices=FRECUENCIA_MEDICION_CHOICES,
        default='mensual',
        verbose_name='Frecuencia de Medición'
    )

    responsable_medicion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kris_a_medir',
        verbose_name='Responsable de Medición'
    )

    notificar_al_superar = models.BooleanField(
        default=True,
        verbose_name='Notificar al superar umbral'
    )

    class Meta:
        db_table = 'riesgo_kris'
        verbose_name = 'KRI'
        verbose_name_plural = 'KRIs'
        ordering = ['riesgo', 'codigo']
        unique_together = [['riesgo', 'codigo']]
        indexes = [
            models.Index(fields=['riesgo', 'estado_actual']),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.nombre} [{self.get_estado_actual_display()}]"

    def actualizar_valor(self, nuevo_valor):
        """
        Actualiza el valor actual y recalcula el estado del KRI.
        Llama a esto cada vez que se registra una nueva medición.
        """
        from django.utils import timezone
        self.valor_actual = nuevo_valor
        self.fecha_ultima_medicion = timezone.now()

        # Calcular estado según umbrales
        if float(nuevo_valor) >= float(self.umbral_rojo):
            self.estado_actual = 'rojo'
        elif float(nuevo_valor) >= float(self.umbral_amarillo):
            self.estado_actual = 'amarillo'
        else:
            self.estado_actual = 'verde'

        self.save()
        return self.estado_actual


class RegistroMonitoreo(BaseModel):
    """
    Historial de revisiones periódicas de un riesgo.
    Cada vez que el analista revisa el riesgo, crea un registro aquí.
    """

    RESULTADO_CHOICES = [
        ('sin_cambios',  'Sin Cambios'),
        ('mejora',       'Mejora — nivel de riesgo bajó'),
        ('deterioro',    'Deterioro — nivel de riesgo subió'),
        ('materializado','Materializado — el riesgo ocurrió'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    riesgo = models.ForeignKey(
        Riesgo,
        on_delete=models.CASCADE,
        related_name='registros_monitoreo',
        verbose_name='Riesgo'
    )

    # ── Evaluación en esta revisión ────────────────────────────────────────────
    probabilidad_revisada = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
        verbose_name='Probabilidad Revisada',
        null=True,
        blank=True
    )

    impacto_revisado = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Impacto Revisado'
    )

    nivel_riesgo_revisado = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Nivel de Riesgo Revisado'
    )

    resultado = models.CharField(
        max_length=20,
        choices=RESULTADO_CHOICES,
        default='sin_cambios',
        verbose_name='Resultado de la Revisión'
    )

    # ── Observaciones ──────────────────────────────────────────────────────────
    observaciones = models.TextField(
        verbose_name='Observaciones de la Revisión'
    )

    acciones_adicionales = models.TextField(
        blank=True,
        default='',
        verbose_name='Acciones Adicionales Sugeridas'
    )

    # ── Auditoría ──────────────────────────────────────────────────────────────
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='revisiones_riesgo',
        verbose_name='Revisado por'
    )

    fecha_revision = models.DateField(
        verbose_name='Fecha de Revisión'
    )

    proxima_revision = models.DateField(
        null=True,
        blank=True,
        verbose_name='Próxima Revisión'
    )

    class Meta:
        db_table = 'riesgo_registros_monitoreo'
        verbose_name = 'Registro de Monitoreo'
        verbose_name_plural = 'Registros de Monitoreo'
        ordering = ['-fecha_revision']
        indexes = [
            models.Index(fields=['riesgo', 'fecha_revision']),
            models.Index(fields=['revisado_por', 'fecha_revision']),
        ]

    def __str__(self):
        return f"Revisión {self.riesgo.codigo} — {self.fecha_revision} ({self.get_resultado_display()})"