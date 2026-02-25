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


class AsignacionEvaluacionIQ(models.Model):
    """
    Asignación de una Evaluación a un Usuario específico.
    
    Flujo:
    1. Admin crea evaluación (usar_todas_preguntas o selección manual)
    2. Admin asigna evaluación a usuarios de su empresa
    3. Usuario responde preguntas
    4. Admin/Auditor revisa progreso
    """
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),           # Asignada pero no iniciada
        ('en_progreso', 'En Progreso'),       # Usuario respondiendo
        ('completada', 'Completada'),         # Usuario terminó de responder
        ('revisada', 'Revisada'),             # Auditor revisó
        ('aprobada', 'Aprobada'),             # Aprobada por Admin
        ('rechazada', 'Rechazada'),           # Rechazada, requiere correcciones
        ('vencida', 'Vencida'),               # Pasó la fecha límite sin completar
    ]
    
    # Relaciones principales
    evaluacion = models.ForeignKey(
        Evaluacion,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Evaluación'
    )
    usuario_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='evaluaciones_asignadas',
        verbose_name='Usuario Asignado'
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='asignaciones_evaluaciones',
        verbose_name='Empresa'
    )
    
    # Fechas de asignación
    fecha_asignacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Asignación'
    )
    fecha_inicio = models.DateField(
        verbose_name='Fecha de Inicio',
        help_text='Fecha desde la cual el usuario puede empezar'
    )
    fecha_limite = models.DateField(
        verbose_name='Fecha Límite',
        help_text='Fecha máxima para completar la evaluación'
    )
    
    # Control de progreso
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado'
    )
    fecha_inicio_real = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Real de Inicio',
        help_text='Momento en que el usuario comenzó a responder'
    )
    fecha_completado = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Completado'
    )
    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Revisión'
    )
    
    # Tracking de progreso
    total_preguntas = models.IntegerField(
        default=0,
        verbose_name='Total de Preguntas'
    )
    preguntas_respondidas = models.IntegerField(
        default=0,
        verbose_name='Preguntas Respondidas'
    )
    porcentaje_completado = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Porcentaje Completado'
    )
    
    # Gestión de asignación
    asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='asignaciones_iq_creadas',
        verbose_name='Asignado Por'
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asignaciones_iq_revisadas',
        verbose_name='Revisado Por'
    )
    
    # Observaciones
    notas_asignacion = models.TextField(
        blank=True,
        verbose_name='Notas de Asignación',
        help_text='Instrucciones o comentarios para el usuario'
    )
    notas_revision = models.TextField(
        blank=True,
        verbose_name='Notas de Revisión',
        help_text='Comentarios del revisor'
    )
    
    # ⭐ NUEVO CAMPO
    requiere_revision = models.BooleanField(
        default=True,
        verbose_name='Requiere Revisión',
        help_text='Si es True, el Admin debe aprobar/rechazar. Si es False, se auto-aprueba al completar.'
    )
    
    # Flags adicionales
    notificar_usuario = models.BooleanField(
        default=True,
        verbose_name='Notificar al Usuario',
        help_text='Enviar email al asignar'
    )
    recordatorio_enviado = models.BooleanField(
        default=False,
        verbose_name='Recordatorio Enviado'
    )
    
    # Metadata
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    
    class Meta:
        verbose_name = 'Asignación de Evaluación'
        verbose_name_plural = 'Asignaciones de Evaluaciones'
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
        # Auto-asignar empresa desde el usuario
        if not self.empresa_id:
            self.empresa = self.usuario_asignado.empresa
        
        # Calcular total de preguntas
        if not self.total_preguntas and self.evaluacion_id:
            self.total_preguntas = self.evaluacion.total_preguntas
        
        # Calcular porcentaje
        if self.total_preguntas > 0:
            self.porcentaje_completado = (self.preguntas_respondidas / self.total_preguntas) * 100
        
        super().save(*args, **kwargs)
    
    @property
    def esta_vencida(self):
        """Verifica si la asignación está vencida"""
        from django.utils import timezone
        return (
            self.estado in ['pendiente', 'en_progreso'] and
            timezone.now().date() > self.fecha_limite
        )
    
    @property
    def dias_restantes(self):
        """Calcula días restantes para completar"""
        from django.utils import timezone
        if self.estado in ['completada', 'aprobada']:
            return 0
        delta = self.fecha_limite - timezone.now().date()
        return max(0, delta.days)
    
    @property
    def tiempo_usado(self):
        """Calcula tiempo usado para responder (en horas)"""
        if self.fecha_inicio_real and self.fecha_completado:
            delta = self.fecha_completado - self.fecha_inicio_real
            return delta.total_seconds() / 3600  # horas
        return None
    
    def actualizar_progreso(self):
        """Actualiza el conteo de preguntas respondidas"""
        # ⭐ CORREGIDO: Usar RespuestaEvaluacionIQ en lugar de RespuestaEvaluacion
        from apps.asignaciones_iq.models import RespuestaEvaluacionIQ
        
        # Contar respuestas para ESTA asignación
        self.preguntas_respondidas = RespuestaEvaluacionIQ.objects.filter(
            asignacion=self  # ⭐ Filtrar por asignación, no por evaluación
        ).count()
        
        # Actualizar porcentaje
        if self.total_preguntas > 0:
            self.porcentaje_completado = (self.preguntas_respondidas / self.total_preguntas) * 100
        
        # Actualizar estado si completó todas
        if self.preguntas_respondidas >= self.total_preguntas and self.estado == 'en_progreso':
            self.estado = 'completada'
            from django.utils import timezone
            self.fecha_completado = timezone.now()
        
        self.save()
    
    def iniciar(self):
        """Marca la asignación como iniciada"""
        if self.estado == 'pendiente':
            from django.utils import timezone
            self.estado = 'en_progreso'
            self.fecha_inicio_real = timezone.now()
            self.save()
    
    def completar(self):
        """Marca la asignación como completada"""
        if self.estado == 'en_progreso':
            from django.utils import timezone
            self.fecha_completado = timezone.now()
            
            # ⭐ AUTO-APROBAR si no requiere revisión
            if not self.requiere_revision:
                self.estado = 'aprobada'
                self.revisado_por = self.asignado_por  # El que asignó la auto-aprueba
                self.fecha_revision = timezone.now()
                self.notas_revision = 'Auto-aprobada (no requiere revisión manual)'
            else:
                self.estado = 'completada'
            
            self.save()
    
    def aprobar(self, revisor, notas=''):
        """Aprueba la asignación"""
        from django.utils import timezone
        self.estado = 'aprobada'
        self.revisado_por = revisor
        self.fecha_revision = timezone.now()
        if notas:
            self.notas_revision = notas
        self.save()
    
    def rechazar(self, revisor, notas=''):
        """Rechaza la asignación"""
        from django.utils import timezone
        self.estado = 'rechazada'
        self.revisado_por = revisor
        self.fecha_revision = timezone.now()
        if notas:
            self.notas_revision = notas
        self.save()

    def propagar_respuestas_previas(self):
        """
        Propaga respuestas de evaluaciones anteriores del mismo usuario.
        Se ejecuta automáticamente al crear la asignación.
        
        Busca:
        1. Respuestas originales del usuario en otras evaluaciones
        2. Preguntas relacionadas vía RelacionFramework
        3. Preguntas con mismo framework + mismo código
        
        Solo propaga si:
        - La evaluación permite usar_respuestas_compartidas=True
        - La pregunta relacionada está en esta evaluación
        - No existe ya una respuesta
        """
        if not self.evaluacion.usar_respuestas_compartidas:
            return 0
        
        from apps.asignaciones_iq.models import RespuestaEvaluacionIQ
        from apps.evaluaciones.models import RelacionFramework, PreguntaEvaluacion
        
        # Respuestas previas del usuario (solo originales)
        respuestas_previas = RespuestaEvaluacionIQ.objects.filter(
            respondido_por=self.usuario_asignado,
            es_respuesta_original=True
        ).exclude(
            asignacion=self
        ).select_related('pregunta', 'pregunta__framework')
        
        if not respuestas_previas.exists():
            return 0
        
        preguntas_actuales = set(self.evaluacion.get_preguntas_a_responder())
        contador = 0
        
        for resp_prev in respuestas_previas:
            # 1. Buscar vía RelacionFramework
            relaciones = RelacionFramework.objects.filter(
                pregunta_origen=resp_prev.pregunta
            ).select_related('framework_destino')
            
            for rel in relaciones:
                preguntas_rel = PreguntaEvaluacion.objects.filter(
                    framework=rel.framework_destino,
                    codigo_control=rel.codigo_control_referenciado,
                    activo=True
                )
                
                for preg in preguntas_rel:
                    if preg not in preguntas_actuales:
                        continue
                    
                    if RespuestaEvaluacionIQ.objects.filter(
                        asignacion=self, pregunta=preg
                    ).exists():
                        continue
                    
                    RespuestaEvaluacionIQ.objects.create(
                        asignacion=self,
                        pregunta=preg,
                        respuesta=resp_prev.respuesta,
                        justificacion=f"[IMPORTADO] {resp_prev.justificacion}",
                        nivel_madurez=resp_prev.nivel_madurez,
                        justificacion_madurez=resp_prev.justificacion_madurez,
                        es_respuesta_original=False,
                        propagada_desde=resp_prev,
                        respondido_por=self.usuario_asignado
                    )
                    contador += 1
            
            # 2. Mismo framework + mismo código
            preguntas_mismo = PreguntaEvaluacion.objects.filter(
                framework=resp_prev.pregunta.framework,
                codigo_control=resp_prev.pregunta.codigo_control,
                activo=True
            ).exclude(id=resp_prev.pregunta.id)
            
            for preg in preguntas_mismo:
                if preg not in preguntas_actuales:
                    continue
                
                if RespuestaEvaluacionIQ.objects.filter(
                    asignacion=self, pregunta=preg
                ).exists():
                    continue
                
                RespuestaEvaluacionIQ.objects.create(
                    asignacion=self,
                    pregunta=preg,
                    respuesta=resp_prev.respuesta,
                    justificacion=f"[IMPORTADO] {resp_prev.justificacion}",
                    nivel_madurez=resp_prev.nivel_madurez,
                    es_respuesta_original=False,
                    propagada_desde=resp_prev,
                    respondido_por=self.usuario_asignado
                )
                contador += 1
        
        if contador > 0:
            self.actualizar_progreso()
        
        return contador

class ProgresoAsignacion(models.Model):
    """
    Tracking detallado del progreso por pregunta.
    Opcional pero útil para analytics.
    """
    
    asignacion = models.ForeignKey(
        AsignacionEvaluacionIQ,
        on_delete=models.CASCADE,
        related_name='progreso_detallado',
        verbose_name='Asignación'
    )
    pregunta = models.ForeignKey(
        PreguntaEvaluacion,
        on_delete=models.CASCADE,
        verbose_name='Pregunta'
    )
    respondida = models.BooleanField(
        default=False,
        verbose_name='Respondida'
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Respuesta'
    )
    tiempo_respuesta_minutos = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Tiempo de Respuesta (min)'
    )
    
    class Meta:
        verbose_name = 'Progreso de Asignación'
        verbose_name_plural = 'Progreso de Asignaciones'
        unique_together = ['asignacion', 'pregunta']
        ordering = ['pregunta__correlativo']
    
    def __str__(self):
        return f"{self.asignacion} - Pregunta {self.pregunta.correlativo}"
    

class RespuestaEvaluacionIQ(models.Model):
    """
    Respuesta a una pregunta de evaluación inteligente.
    Soporta propagación automática a preguntas relacionadas entre frameworks.
    """
    
    RESPUESTA_CHOICES = [
        ('SI_CUMPLE', 'Sí Cumple'),
        ('CUMPLE_PARCIAL', 'Cumple Parcialmente'),
        ('NO_CUMPLE', 'No Cumple'),
        ('NO_APLICA', 'No Aplica'),
    ]
    
    asignacion = models.ForeignKey(
        'AsignacionEvaluacionIQ',
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
    respuesta = models.CharField(max_length=20, choices=RESPUESTA_CHOICES)
    justificacion = models.TextField()
    nivel_madurez = models.DecimalField(max_digits=2, decimal_places=1, default=0.0)
    justificacion_madurez = models.TextField(blank=True, default='')
    comentarios_adicionales = models.TextField(blank=True, default='')
    
    # Propagación
    es_respuesta_original = models.BooleanField(default=True)
    propagada_desde = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_propagadas'
    )
    
    # Auditoría
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='respuestas_iq_creadas'
    )
    fecha_respuesta = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'respuestas_evaluacion_iq'
        verbose_name = 'Respuesta Evaluación IQ'
        verbose_name_plural = 'Respuestas Evaluación IQ'
        unique_together = ['asignacion', 'pregunta']
        ordering = ['-fecha_respuesta']
    
    def __str__(self):
        return f"{self.pregunta.codigo_control} - {self.get_respuesta_display()}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        
        if not self.justificacion or len(self.justificacion.strip()) < 10:
            errors['justificacion'] = 'Mínimo 10 caracteres'
        
        if self.respuesta in ['NO_CUMPLE', 'NO_APLICA'] and self.nivel_madurez != 0:
            errors['nivel_madurez'] = 'Debe ser 0 para No Cumple/No Aplica'
        
        if self.respuesta in ['SI_CUMPLE', 'CUMPLE_PARCIAL'] and self.nivel_madurez == 0:
            errors['nivel_madurez'] = 'Debe ser mayor a 0'
        
        if (self.nivel_madurez * 2) % 1 != 0:
            errors['nivel_madurez'] = 'Incrementos de 0.5'
        
        if self.nivel_madurez < 0 or self.nivel_madurez > 5:
            errors['nivel_madurez'] = 'Entre 0 y 5'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = not self.pk
        super().save(*args, **kwargs)
        self.asignacion.actualizar_progreso()
        
        if is_new and self.es_respuesta_original:
            self._propagar_a_relacionadas()
    
    def _propagar_a_relacionadas(self):
        """Propaga respuesta a preguntas relacionadas"""
        if not self.asignacion.evaluacion.usar_respuestas_compartidas:
            return
        
        from apps.evaluaciones.models import RelacionFramework, PreguntaEvaluacion
        
        relaciones = RelacionFramework.objects.filter(
            pregunta_origen=self.pregunta
        ).select_related('framework_destino')
        
        preguntas_eval = set(self.asignacion.evaluacion.get_preguntas_a_responder())
        
        for rel in relaciones:
            preguntas_rel = PreguntaEvaluacion.objects.filter(
                framework=rel.framework_destino,
                codigo_control=rel.codigo_control_referenciado,
                activo=True
            )
            
            for preg in preguntas_rel:
                if preg not in preguntas_eval:
                    continue
                
                if RespuestaEvaluacionIQ.objects.filter(
                    asignacion=self.asignacion,
                    pregunta=preg
                ).exists():
                    continue
                
                RespuestaEvaluacionIQ.objects.create(
                    asignacion=self.asignacion,
                    pregunta=preg,
                    respuesta=self.respuesta,
                    justificacion=f"[AUTO] {self.justificacion}",
                    nivel_madurez=self.nivel_madurez,
                    justificacion_madurez=self.justificacion_madurez,
                    es_respuesta_original=False,
                    propagada_desde=self,
                    respondido_por=self.respondido_por
                )
    
    def get_puntaje(self):
        return {
            'SI_CUMPLE': 1.0,
            'CUMPLE_PARCIAL': 0.5,
            'NO_CUMPLE': 0.0,
            'NO_APLICA': None,
        }.get(self.respuesta, 0.0)
        
@receiver(post_save, sender=RespuestaEvaluacionIQ)
def actualizar_progreso_al_guardar(sender, instance, created, **kwargs):
    """Actualizar progreso cuando se guarda una respuesta"""
    instance.asignacion.actualizar_progreso()

@receiver(post_delete, sender=RespuestaEvaluacionIQ)
def actualizar_progreso_al_eliminar(sender, instance, **kwargs):
    """Actualizar progreso cuando se elimina una respuesta"""
    instance.asignacion.actualizar_progreso()