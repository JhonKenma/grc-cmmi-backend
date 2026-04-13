# apps/riesgos/models/tratamiento.py
"""
Plan de Tratamiento de Riesgos.
Define qué acción se toma para cada riesgo aprobado.
"""

import uuid
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from .riesgo import Riesgo


class PlanTratamiento(BaseModel):
    """
    Plan de acción para tratar un riesgo aprobado.

    Tipos de tratamiento (COSO ERM / ISO 31000):
    - Mitigar:    Reducir probabilidad o impacto mediante controles
    - Transferir: Contratar seguro o tercerizar la actividad
    - Evitar:     Eliminar la actividad que genera el riesgo
    - Aceptar:    Asumir el riesgo conscientemente (documentado)

    Un riesgo puede tener un plan activo y un historial de planes anteriores.
    """

    TIPO_TRATAMIENTO_CHOICES = [
        ('mitigar',    'Mitigar'),
        ('transferir', 'Transferir'),
        ('evitar',     'Evitar'),
        ('aceptar',    'Aceptar'),
    ]

    ESTADO_CHOICES = [
        ('no_iniciada', 'No Iniciada'),
        ('en_curso',    'En Curso'),
        ('completada',  'Completada'),
        ('atrasada',    'Atrasada'),
        ('cancelada',   'Cancelada'),
    ]

    PRIORIDAD_CHOICES = [
        ('critica', 'Crítica'),
        ('alta',    'Alta'),
        ('media',   'Media'),
        ('baja',    'Baja'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    riesgo = models.ForeignKey(
        Riesgo,
        on_delete=models.CASCADE,
        related_name='planes_tratamiento',
        verbose_name='Riesgo'
    )

    # ── Tipo y descripción ─────────────────────────────────────────────────────
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_TRATAMIENTO_CHOICES,
        verbose_name='Tipo de Tratamiento'
    )

    descripcion_accion = models.TextField(
        verbose_name='Descripción de la Acción',
        help_text='¿Qué acción específica se tomará?'
    )

    objetivos = models.TextField(
        blank=True,
        default='',
        verbose_name='Objetivos del Plan',
        help_text='¿Qué se espera lograr con este tratamiento?'
    )

    controles_propuestos = models.TextField(
        blank=True,
        default='',
        verbose_name='Controles Propuestos',
        help_text='Controles específicos a implementar'
    )

    # ── Responsables ───────────────────────────────────────────────────────────
    responsable_accion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='planes_tratamiento_a_cargo',
        verbose_name='Responsable de la Acción'
    )

    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planes_tratamiento_aprobados',
        verbose_name='Aprobado por'
    )

    # ── Fechas ─────────────────────────────────────────────────────────────────
    fecha_inicio = models.DateField(
        verbose_name='Fecha de Inicio'
    )

    fecha_fin_plan = models.DateField(
        verbose_name='Fecha Planificada de Fin'
    )

    fecha_fin_real = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha Real de Fin'
    )

    fecha_aprobacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Aprobación'
    )

    # ── Estado y progreso ──────────────────────────────────────────────────────
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='no_iniciada',
        verbose_name='Estado'
    )

    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default='media',
        verbose_name='Prioridad'
    )

    porcentaje_avance = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='% de Avance',
        help_text='0 a 100'
    )

    # ── Presupuesto y recursos ─────────────────────────────────────────────────
    recursos_requeridos = models.TextField(
        blank=True,
        default='',
        verbose_name='Recursos Requeridos',
        help_text='Ej: $5,000 - Software de seguridad, 2 personas TI'
    )

    costo_estimado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Costo Estimado ($)'
    )

    costo_real = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Costo Real ($)'
    )

    moneda = models.CharField(
        max_length=5,
        default='USD',
        choices=[('USD', 'USD'), ('PEN', 'PEN'), ('EUR', 'EUR')],
        verbose_name='Moneda'
    )

    # ── Eficacia esperada y real ───────────────────────────────────────────────
    eficacia_esperada = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Eficacia Esperada (%)',
        help_text='% de reducción de riesgo esperada con este tratamiento'
    )

    eficacia_real = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Eficacia Real (%)',
        help_text='% de reducción de riesgo obtenida (se calcula al completar)'
    )

    # ── Nivel residual esperado ────────────────────────────────────────────────
    nivel_riesgo_objetivo = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Nivel de Riesgo Objetivo',
        help_text='Nivel de riesgo residual que se espera alcanzar'
    )

    # ── Notas y evidencias ─────────────────────────────────────────────────────
    notas_avance = models.TextField(
        blank=True,
        default='',
        verbose_name='Notas de Avance'
    )

    evidencia_completado = models.TextField(
        blank=True,
        default='',
        verbose_name='Evidencia de Completado',
        help_text='Referencias a documentos que evidencian la completitud'
    )

    class Meta:
        db_table = 'riesgo_planes_tratamiento'
        verbose_name = 'Plan de Tratamiento'
        verbose_name_plural = 'Planes de Tratamiento'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['riesgo', 'estado']),
            models.Index(fields=['responsable_accion', 'estado']),
            models.Index(fields=['fecha_fin_plan', 'estado']),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.riesgo.codigo} ({self.get_estado_display()})"

    def save(self, *args, **kwargs):
        # Si se completó, marcar fecha real si no está
        from django.utils import timezone
        if self.estado == 'completada' and not self.fecha_fin_real:
            self.fecha_fin_real = timezone.now().date()

        # Si avance es 100%, marcar como completada
        if self.porcentaje_avance >= 100 and self.estado == 'en_curso':
            self.estado = 'completada'

        super().save(*args, **kwargs)

        # Actualizar estado del riesgo si el plan se completó
        if self.estado == 'completada':
            self._actualizar_estado_riesgo()

    def _actualizar_estado_riesgo(self):
        """Actualiza el estado del riesgo cuando el plan se completa."""
        riesgo = self.riesgo
        if self.tipo == 'aceptar':
            riesgo.estado = 'aceptado'
        else:
            riesgo.estado = 'mitigado'
        riesgo.save()

    @property
    def esta_atrasado(self):
        from django.utils import timezone
        if self.estado in ['completada', 'cancelada']:
            return False
        return timezone.now().date() > self.fecha_fin_plan

    @property
    def dias_restantes(self):
        from django.utils import timezone
        if self.estado in ['completada', 'cancelada']:
            return 0
        return max(0, (self.fecha_fin_plan - timezone.now().date()).days)