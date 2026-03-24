# apps/asignaciones_iq/models.py
"""
Modelos para Asignación de Evaluaciones Inteligentes a Usuarios
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from apps.empresas.models import Empresa
from apps.evaluaciones.models import Evaluacion, PreguntaEvaluacion
import uuid


class AsignacionEvaluacionIQ(models.Model):
    """
    Asignación de una Evaluación a un Usuario específico.

    Flujo:
    1. Admin asigna evaluación a usuarios
    2. Usuario responde preguntas (borrador → enviado por pregunta)
    3. Al enviar TODAS → asignación pasa a 'completada' y notifica al Auditor
    4. Auditor califica cada respuesta → cierra revisión → calcula GAP
    5. Admin ve reporte → remedia brechas
    """

    ESTADO_CHOICES = [
        ('pendiente',   'Pendiente'),      # Asignada pero no iniciada
        ('en_progreso', 'En Progreso'),    # Usuario respondiendo
        ('completada',  'Completada'),     # Usuario terminó, esperando auditor
        ('auditada',    'Auditada'),       # Auditor cerró revisión, GAP calculado
        ('aprobada',    'Aprobada'),       # Aprobada por Admin
        ('rechazada',   'Rechazada'),      # Rechazada, requiere correcciones
        ('vencida',     'Vencida'),        # Pasó fecha límite sin completar
    ]

    # ── Relaciones ─────────────────────────────────────────────────────────────
    evaluacion = models.ForeignKey(
        Evaluacion,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Evaluación'
    )
    usuario_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='evaluaciones_iq_asignadas',
        verbose_name='Usuario Asignado'
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='asignaciones_evaluaciones_iq',
        verbose_name='Empresa'
    )

    # ── Fechas ──────────────────────────────────────────────────────────────────
    fecha_asignacion  = models.DateTimeField(auto_now_add=True)
    fecha_inicio      = models.DateField(verbose_name='Fecha de Inicio')
    fecha_limite      = models.DateField(verbose_name='Fecha Límite')
    fecha_inicio_real = models.DateTimeField(null=True, blank=True)
    fecha_completado  = models.DateTimeField(null=True, blank=True)
    fecha_auditada    = models.DateTimeField(null=True, blank=True)

    # ── Estado y progreso ───────────────────────────────────────────────────────
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='pendiente'
    )
    total_preguntas        = models.IntegerField(default=0)
    preguntas_respondidas  = models.IntegerField(default=0)
    porcentaje_completado  = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # ── Gestión ─────────────────────────────────────────────────────────────────
    asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='asignaciones_iq_creadas'
    )
    auditado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asignaciones_iq_auditadas'
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asignaciones_iq_revisadas'
    )

    # ── Opciones ────────────────────────────────────────────────────────────────
    requiere_revision  = models.BooleanField(default=True)
    notificar_usuario  = models.BooleanField(default=True)
    recordatorio_enviado = models.BooleanField(default=False)

    # ── Notas ───────────────────────────────────────────────────────────────────
    notas_asignacion = models.TextField(blank=True)
    notas_revision   = models.TextField(blank=True)
    notas_auditoria  = models.TextField(blank=True)

    # ── Metadata ────────────────────────────────────────────────────────────────
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asignación de Evaluación IQ'
        verbose_name_plural = 'Asignaciones de Evaluaciones IQ'
        ordering = ['-fecha_asignacion']
        unique_together = ['evaluacion', 'usuario_asignado']
        indexes = [
            models.Index(fields=['estado', 'fecha_limite']),
            models.Index(fields=['usuario_asignado', 'estado']),
            models.Index(fields=['empresa', 'estado']),
        ]

    def __str__(self):
        return f"{self.evaluacion.nombre} → {self.usuario_asignado.get_full_name()} ({self.get_estado_display()})"

    def save(self, *args, **kwargs):
        if not self.empresa_id:
            self.empresa = self.usuario_asignado.empresa
        if not self.total_preguntas and self.evaluacion_id:
            self.total_preguntas = self.evaluacion.total_preguntas
        if self.total_preguntas > 0:
            self.porcentaje_completado = (self.preguntas_respondidas / self.total_preguntas) * 100
        super().save(*args, **kwargs)

    # ── Properties ──────────────────────────────────────────────────────────────

    @property
    def esta_vencida(self):
        from django.utils import timezone
        return (
            self.estado in ['pendiente', 'en_progreso'] and
            timezone.now().date() > self.fecha_limite
        )

    @property
    def dias_restantes(self):
        from django.utils import timezone
        if self.estado in ['completada', 'auditada', 'aprobada']:
            return 0
        return max(0, (self.fecha_limite - timezone.now().date()).days)

    # ── Métodos de flujo ─────────────────────────────────────────────────────────

    def iniciar(self):
        if self.estado == 'pendiente':
            from django.utils import timezone
            self.estado = 'en_progreso'
            self.fecha_inicio_real = timezone.now()
            self.save()

    def actualizar_progreso(self):
        """Recuenta respuestas enviadas/auditadas y actualiza estado si corresponde."""
        self.preguntas_respondidas = RespuestaEvaluacionIQ.objects.filter(
            asignacion=self,
            estado__in=['enviado', 'auditado']
        ).count()

        if self.total_preguntas > 0:
            self.porcentaje_completado = (self.preguntas_respondidas / self.total_preguntas) * 100

        # Si todas están enviadas → completar y notificar auditor
        if (
            self.preguntas_respondidas >= self.total_preguntas
            and self.estado == 'en_progreso'
        ):
            self._completar()

        self.save()

    def _completar(self):
        """Marca como completada y notifica al auditor."""
        from django.utils import timezone
        self.estado = 'completada'
        self.fecha_completado = timezone.now()

        # Notificar al Auditor de la empresa
        try:
            from apps.asignaciones_iq.services import NotificacionAsignacionIQService
            NotificacionAsignacionIQService.notificar_pendiente_auditoria_iq(
                asignacion=self
            )
        except Exception as e:
            print(f'⚠️  Error al notificar auditor IQ: {e}')

    def cerrar_revision_auditoria(self, auditor, notas=''):
        """
        Llamado cuando el auditor termina de calificar todas las respuestas.
        1. Marca respuestas sin calificar como NO_CUMPLE automáticamente
        2. Calcula GAP por sección/framework
        3. Cambia estado a 'auditada'
        """
        from django.utils import timezone

        # 1. Marcar sin calificar como NO_CUMPLE
        sin_calificar = RespuestaEvaluacionIQ.objects.filter(
            asignacion=self,
            estado='enviado',
            calificacion_auditor__isnull=True
        )
        for resp in sin_calificar:
            resp.marcar_no_cumple_automatico(auditor)

        # 2. Calcular GAP
        self._calcular_gap_iq()

        # 3. Cerrar
        self.estado = 'auditada'
        self.auditado_por = auditor
        self.fecha_auditada = timezone.now()
        if notas:
            self.notas_auditoria = notas
        self.save()

    def _calcular_gap_iq(self):
        """
        Calcula el GAP por sección_general (equivalente a dimensión en encuestas).
        Crea/actualiza registros CalculoNivelIQ.
        """
        from django.db.models import Avg
        nivel_deseado = self.evaluacion.nivel_deseado

        # Agrupar respuestas por sección_general de la pregunta
        secciones = (
            RespuestaEvaluacionIQ.objects
            .filter(asignacion=self, estado='auditado')
            .values('pregunta__seccion_general', 'pregunta__framework__id', 'pregunta__framework__nombre')
            .annotate(promedio_nivel=Avg('nivel_madurez'))
        )

        for seccion in secciones:
            nivel_actual = float(seccion['promedio_nivel'] or 0)
            CalculoNivelIQ.objects.update_or_create(
                asignacion=self,
                seccion=seccion['pregunta__seccion_general'],
                framework_id=seccion['pregunta__framework__id'],
                defaults={
                    'empresa': self.empresa,
                    'usuario': self.usuario_asignado,
                    'framework_nombre': seccion['pregunta__framework__nombre'],
                    'nivel_deseado': nivel_deseado,
                    'nivel_actual': nivel_actual,
                    # gap y clasificacion se calculan en CalculoNivelIQ.save()
                    **self._contar_respuestas_seccion(seccion['pregunta__seccion_general']),
                }
            )

    def _contar_respuestas_seccion(self, seccion):
        qs = RespuestaEvaluacionIQ.objects.filter(
            asignacion=self,
            pregunta__seccion_general=seccion,
            estado='auditado'
        )
        total = qs.count()
        si    = qs.filter(calificacion_auditor='SI_CUMPLE').count()
        parc  = qs.filter(calificacion_auditor='CUMPLE_PARCIAL').count()
        no    = qs.filter(calificacion_auditor='NO_CUMPLE').count()
        na    = qs.filter(respuesta='NO_APLICA').count()
        cump  = ((si + parc) / max(total - na, 1)) * 100

        return {
            'total_preguntas': total,
            'respuestas_si_cumple': si,
            'respuestas_cumple_parcial': parc,
            'respuestas_no_cumple': no,
            'respuestas_no_aplica': na,
            'porcentaje_cumplimiento': round(cump, 2),
        }

    def aprobar(self, revisor, notas=''):
        from django.utils import timezone
        self.estado = 'aprobada'
        self.revisado_por = revisor
        if notas:
            self.notas_revision = notas
        self.save()

    def rechazar(self, revisor, notas=''):
        from django.utils import timezone
        self.estado = 'rechazada'
        self.revisado_por = revisor
        if notas:
            self.notas_revision = notas
        self.save()


# ─────────────────────────────────────────────────────────────────────────────
# RESPUESTA EVALUACIÓN IQ
# ─────────────────────────────────────────────────────────────────────────────

class RespuestaEvaluacionIQ(models.Model):
    """
    Respuesta de un usuario a una pregunta de evaluación inteligente.

    FLUJO (idéntico al módulo de encuestas):
    - Usuario marca: null (sube evidencias) / 'NO_CUMPLE' / 'NO_APLICA'
    - Estado: borrador → enviado
    - Auditor califica: SI_CUMPLE / CUMPLE_PARCIAL / NO_CUMPLE
    - Estado: auditado
    """

    # ── Opciones del USUARIO ────────────────────────────────────────────────────
    OPCIONES_USUARIO = [
        ('NO_APLICA',  'No Aplica'),
        ('NO_CUMPLE',  'No Cumple'),   # el usuario reconoce que no cumple
    ]

    # ── Calificaciones del AUDITOR ──────────────────────────────────────────────
    CALIFICACIONES_AUDITOR = [
        ('SI_CUMPLE',      'Sí Cumple'),
        ('CUMPLE_PARCIAL', 'Cumple Parcialmente'),
        ('NO_CUMPLE',      'No Cumple'),
    ]

    ESTADOS = [
        ('borrador',  'Borrador'),
        ('enviado',   'Enviado'),
        ('auditado',  'Auditado'),
    ]

    #id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    asignacion = models.ForeignKey(
        AsignacionEvaluacionIQ,
        on_delete=models.CASCADE,
        related_name='respuestas_iq',
        verbose_name='Asignación'
    )
    pregunta = models.ForeignKey(
        'evaluaciones.PreguntaEvaluacion',
        on_delete=models.CASCADE,
        related_name='respuestas_iq',
        verbose_name='Pregunta'
    )

    # ── Respuesta del USUARIO ───────────────────────────────────────────────────
    # null  → subió evidencias ("Sí"), el auditor califica
    # 'NO_CUMPLE' → reconoce que no cumple
    # 'NO_APLICA' → criterio no aplica
    respuesta = models.CharField(
        max_length=20,
        choices=OPCIONES_USUARIO,
        null=True, blank=True, default=None,
        verbose_name='Respuesta del Usuario'
    )
    justificacion = models.TextField(
        verbose_name='Justificación',
        help_text='Mínimo 10 caracteres. Obligatorio siempre.'
    )
    comentarios_adicionales = models.TextField(blank=True, default='')

    # ── Calificación del AUDITOR ────────────────────────────────────────────────
    calificacion_auditor = models.CharField(
        max_length=20,
        choices=CALIFICACIONES_AUDITOR,
        null=True, blank=True,
        verbose_name='Calificación del Auditor'
    )
    comentarios_auditor    = models.TextField(blank=True, default='')
    recomendaciones_auditor = models.TextField(blank=True, default='')
    fecha_auditoria        = models.DateTimeField(null=True, blank=True)
    auditado_por           = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='respuestas_iq_auditadas'
    )

    # ── Nivel de madurez (lo asigna el Auditor) ─────────────────────────────────
    nivel_madurez = models.DecimalField(
        max_digits=2, decimal_places=1, default=0.0,
        verbose_name='Nivel de Madurez',
        help_text='Asignado por el auditor (0–5, incrementos de 0.5)'
    )

    # ── Estado ──────────────────────────────────────────────────────────────────
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default='borrador'
    )

    # ── Propagación (feature de evaluaciones compartidas) ───────────────────────
    es_respuesta_original = models.BooleanField(default=True)
    propagada_desde = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='respuestas_propagadas'
    )

    # ── Auditoría de registro ────────────────────────────────────────────────────
    respondido_por    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='respuestas_iq_creadas'
    )
    respondido_at     = models.DateTimeField(auto_now_add=True)
    modificado_por    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='respuestas_iq_modificadas'
    )
    modificado_at     = models.DateTimeField(null=True, blank=True)
    version           = models.IntegerField(default=1)

    class Meta:
        db_table = 'respuestas_evaluacion_iq'
        verbose_name = 'Respuesta Evaluación IQ'
        verbose_name_plural = 'Respuestas Evaluación IQ'
        unique_together = ['asignacion', 'pregunta']
        ordering = ['-respondido_at']
        indexes = [
            models.Index(fields=['asignacion', 'estado']),
            models.Index(fields=['pregunta']),
            models.Index(fields=['respondido_por']),
        ]

    def __str__(self):
        cal = self.calificacion_auditor or self.respuesta or 'sin calificar'
        return f"{self.pregunta.codigo_control} - {cal}"

    # ── Validaciones ─────────────────────────────────────────────────────────────

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}

        if not self.justificacion or len(self.justificacion.strip()) < 10:
            errors['justificacion'] = 'Mínimo 10 caracteres'

        if self.respuesta == 'NO_APLICA' and self.calificacion_auditor:
            errors['calificacion_auditor'] = 'NO_APLICA no puede tener calificación de auditor'

        if self.calificacion_auditor == 'NO_CUMPLE' and self.nivel_madurez != 0:
            errors['nivel_madurez'] = 'Debe ser 0 para NO_CUMPLE'

        if self.nivel_madurez and (self.nivel_madurez * 2) % 1 != 0:
            errors['nivel_madurez'] = 'Debe ser múltiplo de 0.5'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # ── Helpers ───────────────────────────────────────────────────────────────────

    def get_puntaje(self):
        if self.respuesta == 'NO_APLICA':
            return None
        return {
            'SI_CUMPLE':      1.0,
            'CUMPLE_PARCIAL': 0.5,
            'NO_CUMPLE':      0.0,
        }.get(self.calificacion_auditor)

    def enviar(self):
        """Cambia estado de borrador a enviado."""
        if self.estado != 'borrador':
            raise ValueError('Solo se puede enviar desde borrador')
        self.estado = 'enviado'
        self.save()
        # Actualizar progreso de la asignación
        self.asignacion.actualizar_progreso()

    def calificar(self, auditor, calificacion, nivel_madurez,
                  comentarios='', recomendaciones=''):
        """El auditor califica la respuesta."""
        from django.utils import timezone
        self.calificacion_auditor    = calificacion
        self.nivel_madurez           = nivel_madurez
        self.comentarios_auditor     = comentarios
        self.recomendaciones_auditor = recomendaciones
        self.auditado_por            = auditor
        self.fecha_auditoria         = timezone.now()
        self.estado                  = 'auditado'
        self.save()

    def marcar_no_cumple_automatico(self, auditor=None):
        """Llamado al cerrar revisión si quedó sin calificar."""
        from django.utils import timezone
        self.calificacion_auditor    = 'NO_CUMPLE'
        self.nivel_madurez           = 0.0
        self.comentarios_auditor     = 'Sin calificación del auditor — marcado automáticamente.'
        self.auditado_por            = auditor
        self.fecha_auditoria         = timezone.now()
        self.estado                  = 'auditado'
        super().save()   # saltar full_clean para evitar loop


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO DE NIVEL IQ  (equivalente a CalculoNivel en encuestas)
# ─────────────────────────────────────────────────────────────────────────────

class CalculoNivelIQ(models.Model):
    """
    GAP por sección/framework para una asignación IQ.
    Equivalente a CalculoNivel del módulo de encuestas.
    Se crea/actualiza al cerrar la revisión de auditoría.
    """

    CLASIFICACION_GAP = [
        ('critico',  'Crítico'),   # GAP >= 3
        ('alto',     'Alto'),      # GAP >= 2
        ('medio',    'Medio'),     # GAP >= 1
        ('bajo',     'Bajo'),      # GAP < 1
        ('cumplido', 'Cumplido'),  # GAP == 0
        ('superado', 'Superado'),  # GAP < 0
    ]

    #id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    asignacion = models.ForeignKey(
        AsignacionEvaluacionIQ,
        on_delete=models.CASCADE,
        related_name='calculos_nivel_iq',
        verbose_name='Asignación IQ'
    )
    empresa  = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name='calculos_nivel_iq'
    )
    usuario  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='calculos_nivel_iq'
    )
    framework_id     = models.IntegerField(verbose_name='Framework ID')
    framework_nombre = models.CharField(max_length=200)
    seccion          = models.CharField(max_length=300, verbose_name='Sección / Dominio')

    nivel_deseado = models.DecimalField(max_digits=2, decimal_places=1)
    nivel_actual  = models.DecimalField(max_digits=2, decimal_places=1)
    gap           = models.DecimalField(max_digits=3, decimal_places=1)
    clasificacion_gap = models.CharField(max_length=20, choices=CLASIFICACION_GAP)

    # Estadísticas de respuestas
    total_preguntas           = models.IntegerField(default=0)
    respuestas_si_cumple      = models.IntegerField(default=0)
    respuestas_cumple_parcial = models.IntegerField(default=0)
    respuestas_no_cumple      = models.IntegerField(default=0)
    respuestas_no_aplica      = models.IntegerField(default=0)
    porcentaje_cumplimiento   = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    calculado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'calculos_nivel_iq'
        verbose_name = 'Cálculo de Nivel IQ'
        verbose_name_plural = 'Cálculos de Nivel IQ'
        ordering = ['-calculado_at']
        unique_together = ['asignacion', 'seccion', 'framework_id']
        indexes = [
            models.Index(fields=['empresa', 'framework_id']),
            models.Index(fields=['usuario', 'framework_id']),
            models.Index(fields=['clasificacion_gap']),
        ]

    def __str__(self):
        return f"{self.seccion} — GAP {self.gap} ({self.clasificacion_gap})"

    def save(self, *args, **kwargs):
        self.gap = float(self.nivel_deseado) - float(self.nivel_actual)
        if self.gap >= 3:
            self.clasificacion_gap = 'critico'
        elif self.gap >= 2:
            self.clasificacion_gap = 'alto'
        elif self.gap >= 1:
            self.clasificacion_gap = 'medio'
        elif self.gap > 0:
            self.clasificacion_gap = 'bajo'
        elif self.gap == 0:
            self.clasificacion_gap = 'cumplido'
        else:
            self.clasificacion_gap = 'superado'
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# SIGNALS
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=RespuestaEvaluacionIQ)
def actualizar_progreso_asignacion(sender, instance, created, **kwargs):
    """Actualiza contadores de la asignación al guardar respuesta."""
    if instance.estado in ['enviado', 'auditado']:
        # Evitar recursión: actualizar sin disparar señales de nuevo
        AsignacionEvaluacionIQ.objects.filter(pk=instance.asignacion_id).update(
            preguntas_respondidas=RespuestaEvaluacionIQ.objects.filter(
                asignacion_id=instance.asignacion_id,
                estado__in=['enviado', 'auditado']
            ).count()
        )