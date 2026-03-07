# apps/asignaciones/models.py
from django.db import models
from apps.core.models import BaseModel
from apps.empresas.models import Empresa
from apps.usuarios.models import Usuario
from apps.encuestas.models import Encuesta, Dimension
from django.utils import timezone
import uuid

class Asignacion(BaseModel):
    """
    Asignación de dimensión específica a un usuario dentro de una evaluación.
    
    Cada asignación ahora está vinculada a una EvaluacionEmpresa específica,
    lo que permite separar datos entre diferentes evaluaciones de la misma empresa.
    """
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_progreso', 'En Progreso'),
        ('completado', 'Completado'),
        ('vencido', 'Vencido'),
        ('pendiente_revision', 'Pendiente de Revisión'),  
        ('pendiente_auditoria',  'Pendiente de Auditoría'),
        ('rechazado', 'Rechazado'),  
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # ⭐ NUEVO CAMPO - Vínculo a la evaluación específica
    evaluacion_empresa = models.ForeignKey(
        'encuestas.EvaluacionEmpresa',
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Evaluación Empresa',
        null=True,        # ⭐ AGREGAR TEMPORALMENTE
        blank=True,       # ⭐ AGREGAR TEMPORALMENTE
        help_text='Evaluación específica a la que pertenece esta asignación'
    )
    
    # Campos heredados (se mantienen por compatibilidad y queries)
    encuesta = models.ForeignKey(
        Encuesta,
        on_delete=models.CASCADE,
        related_name='asignaciones_directas',  # ⭐ Cambiar nombre para evitar conflicto
        verbose_name='Encuesta'
    )
    
    dimension = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Dimensión',
        null=True,
        blank=True,
        help_text='Dimensión asignada (NULL si es evaluación completa)'
    )
    
    usuario_asignado = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='asignaciones_recibidas',
        verbose_name='Usuario Asignado'
    )
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='asignaciones_directas',  # ⭐ Cambiar nombre para evitar conflicto
        verbose_name='Empresa'
    )
    
    asignado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asignaciones_creadas',
        verbose_name='Asignado Por'
    )
    
    fecha_asignacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Asignación'
    )
    
    fecha_limite = models.DateField(
        verbose_name='Fecha Límite'
    )
    
    fecha_completado = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Completado'
    )
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado'
    )
    
    total_preguntas = models.IntegerField(
        default=0,
        verbose_name='Total de Preguntas'
    )
    
    preguntas_respondidas = models.IntegerField(
        default=0,
        verbose_name='Preguntas Respondidas'
    )
    
    porcentaje_avance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Porcentaje de Avance'
    )
    
    observaciones = models.TextField(
        blank=True,
        default='',
        verbose_name='Observaciones'
    )
    
    # Campos de revisión
    requiere_revision = models.BooleanField(
        default=False,
        verbose_name='Requiere Revisión',
        help_text='Si TRUE, el administrador debe revisar antes de marcar como completado'
    )
    
    fecha_envio_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Envío a Revisión',
        help_text='Fecha en que el usuario envió para revisión'
    )
    
    revisado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asignaciones_revisadas',
        verbose_name='Revisado Por'
    )
    
    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Revisión'
    )
    
    comentarios_revision = models.TextField(
        blank=True,
        default='',
        verbose_name='Comentarios de Revisión',
        help_text='Observaciones del revisor al aprobar o rechazar'
    )
    
    class Meta:
        db_table = 'asignaciones'
        verbose_name = 'Asignación'
        verbose_name_plural = 'Asignaciones'
        ordering = ['-fecha_asignacion']
        
        # ⭐ CONSTRAINTS ACTUALIZADOS - Únicos por evaluación
        constraints = [
            models.UniqueConstraint(
                fields=['evaluacion_empresa', 'dimension', 'usuario_asignado'],
                name='unique_asignacion_evaluacion_dimension_usuario',
                condition=models.Q(dimension__isnull=False, activo=True)
            ),
        ]
        
        # ⭐ INDEXES ACTUALIZADOS
        indexes = [
            models.Index(fields=['evaluacion_empresa', 'estado']),
            models.Index(fields=['usuario_asignado', 'estado']),
            models.Index(fields=['empresa', 'estado']),
            models.Index(fields=['fecha_limite']),
            models.Index(fields=['dimension']),
        ]
    
    def __str__(self):
        if self.dimension:
            return f"{self.evaluacion_empresa} - {self.dimension.nombre} - {self.usuario_asignado.nombre_completo} ({self.estado})"
        return f"{self.evaluacion_empresa} (Completa) - {self.usuario_asignado.nombre_completo} ({self.estado})"
    
    def save(self, *args, **kwargs):
        # Calcular total de preguntas
        if not self.total_preguntas:
            if self.dimension:
                self.total_preguntas = self.dimension.preguntas.filter(activo=True).count()
            else:
                self.total_preguntas = sum(
                    dim.preguntas.filter(activo=True).count() 
                    for dim in self.encuesta.dimensiones.filter(activo=True)
                )
        
        # Lógica de estado
        # ⭐ AGREGAR 'pendiente_auditoria' a los estados que no se tocan automáticamente
        if self.estado not in ['completado', 'rechazado', 'pendiente_revision', 'pendiente_auditoria', 'auditado']:
            if self.preguntas_respondidas >= self.total_preguntas and self.total_preguntas > 0:
                # ⭐ NUEVO FLUJO: siempre va a pendiente_auditoria al completar
                # El estado 'completado' solo lo pone el Auditor al cerrar revisión
                self.estado = 'pendiente_auditoria'
                if not self.fecha_envio_revision:
                    self.fecha_envio_revision = timezone.now()
            elif self.preguntas_respondidas > 0:
                self.estado = 'en_progreso'
        
        # Calcular porcentaje
        if self.total_preguntas > 0:
            self.porcentaje_avance = (self.preguntas_respondidas / self.total_preguntas) * 100
        
        # Verificar si está vencido
        # ⭐ AGREGAR 'pendiente_auditoria' a los estados protegidos del vencimiento
        if self.estado not in ['completado', 'rechazado', 'pendiente_auditoria', 'auditado'] and self.fecha_limite < timezone.now().date():
         #if self.estado not in ['completado', 'rechazado', 'pendiente_auditoria'] and self.fecha_limite < timezone.now().date():
            self.estado = 'vencido'
        
        super().save(*args, **kwargs)
        
        # Actualizar progreso de la evaluación
        if self.evaluacion_empresa_id:
            try:
                self.evaluacion_empresa.actualizar_progreso()
            except Exception as e:
                print(f"⚠️ Error al actualizar progreso de evaluación: {e}")
    
    @property
    def dias_restantes(self):
        """Calcula días restantes hasta la fecha límite"""
        if self.estado == 'completado':
            return 0
        delta = self.fecha_limite - timezone.now().date()
        return delta.days
    
    @property
    def esta_vencido(self):
        """Verifica si la asignación está vencida"""
        return self.estado == 'vencido' or (
            self.estado != 'completado' and 
            self.fecha_limite < timezone.now().date()
        )
    
    @property
    def es_evaluacion_completa(self):
        """Indica si es una asignación de evaluación completa"""
        return self.dimension is None
    
    def actualizar_progreso(self):
        """
        Actualiza el progreso de la asignación basado en respuestas
        """
        from apps.respuestas.models import Respuesta
        from apps.encuestas.models import Pregunta
        
        # Contar preguntas totales de la dimensión
        if self.dimension:
            total_preguntas = Pregunta.objects.filter(
                dimension=self.dimension,
                activo=True
            ).count()
        else:
            # Si es evaluación completa
            total_preguntas = sum(
                dim.preguntas.filter(activo=True).count() 
                for dim in self.encuesta.dimensiones.filter(activo=True)
            )
        
        # Contar respuestas activas de esta asignación
        respuestas_enviadas = Respuesta.objects.filter(
            asignacion=self,
            activo=True
        ).count()
        
        # Actualizar campos
        self.total_preguntas = total_preguntas
        self.preguntas_respondidas = respuestas_enviadas
        
        # Calcular porcentaje
        if total_preguntas > 0:
            self.porcentaje_avance = (respuestas_enviadas / total_preguntas) * 100
        else:
            self.porcentaje_avance = 0
        
        # Actualizar estado si estaba pendiente y ahora tiene progreso
        if self.estado == 'pendiente' and respuestas_enviadas > 0:
            self.estado = 'en_progreso'
        
        print(f"📊 Progreso actualizado: {respuestas_enviadas}/{total_preguntas} ({self.porcentaje_avance:.0f}%)")