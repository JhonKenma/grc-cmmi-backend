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
    Asignación de una evaluación completa o dimensión específica a un usuario.
    
    - Si dimension=NULL: Asignación de evaluación completa (SuperAdmin → Administrador)
    - Si dimension=UUID: Asignación de dimensión específica (Administrador → Usuario)
    """
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_progreso', 'En Progreso'),
        ('completado', 'Completado'),
        ('vencido', 'Vencido'),
        ('pendiente_revision', 'Pendiente de Revisión'),  
        ('rechazado', 'Rechazado'),  
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    encuesta = models.ForeignKey(
        Encuesta,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Encuesta'
    )
    
    # ⭐ CAMBIO PRINCIPAL: Permitir NULL en dimension
    dimension = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Dimensión',
        null=True,          # ⭐ AGREGAR
        blank=True,         # ⭐ AGREGAR
        help_text='Si es NULL, la asignación es de la evaluación completa'
    )
    
    usuario_asignado = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='asignaciones_recibidas',  # ⭐ CAMBIAR related_name para evitar conflicto
        verbose_name='Usuario Asignado'
    )
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name='Empresa'
    )
    
    asignado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # ⭐ AGREGAR
        related_name='asignaciones_creadas',
        verbose_name='Asignado Por'
    )
    
    fecha_asignacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Asignación')
    fecha_limite = models.DateField(verbose_name='Fecha Límite')
    fecha_completado = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Completado')
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado'
    )
    
    total_preguntas = models.IntegerField(default=0, verbose_name='Total de Preguntas')
    preguntas_respondidas = models.IntegerField(default=0, verbose_name='Preguntas Respondidas')
    porcentaje_avance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Porcentaje de Avance'
    )
    
    observaciones = models.TextField(blank=True, default='', verbose_name='Observaciones')  # ⭐ AGREGAR default=''
    
    class Meta:
        db_table = 'asignaciones'
        verbose_name = 'Asignación'
        verbose_name_plural = 'Asignaciones'
        ordering = ['-fecha_asignacion']
        
        # ⭐ CAMBIAR unique_together a constraints para manejar NULL
        constraints = [
            models.UniqueConstraint(
                fields=['encuesta', 'dimension', 'usuario_asignado'],
                name='unique_asignacion_dimension',
                condition=models.Q(dimension__isnull=False)  # Solo aplica cuando dimension NO es NULL
            ),
            models.UniqueConstraint(
                fields=['encuesta', 'usuario_asignado'],
                name='unique_asignacion_evaluacion',
                condition=models.Q(dimension__isnull=True)  # Solo aplica cuando dimension ES NULL
            ),
        ]
        
        indexes = [
            models.Index(fields=['usuario_asignado', 'estado']),
            models.Index(fields=['empresa', 'estado']),
            models.Index(fields=['fecha_limite']),
            models.Index(fields=['dimension']),  # ⭐ AGREGAR índice
        ]
        
    # ⭐ NUEVOS CAMPOS
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
    
    def __str__(self):
        if self.dimension:
            return f"{self.dimension.nombre} - {self.usuario_asignado.nombre_completo} ({self.estado})"
        return f"{self.encuesta.nombre} (Completa) - {self.usuario_asignado.nombre_completo} ({self.estado})"
    
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
        
        # ⭐ LÓGICA ACTUALIZADA DE ESTADO
        if self.preguntas_respondidas >= self.total_preguntas and self.total_preguntas > 0:
            if self.requiere_revision and self.estado != 'rechazado':
                # Si requiere revisión, pasar a pendiente_revision
                if self.estado != 'pendiente_revision':
                    self.estado = 'pendiente_revision'
                    self.fecha_envio_revision = timezone.now()
            else:
                # Sin revisión, marcar como completado directamente
                self.estado = 'completado'
                if not self.fecha_completado:
                    self.fecha_completado = timezone.now()
        elif self.preguntas_respondidas > 0:
            if self.estado not in ['pendiente_revision', 'rechazado', 'completado']:
                self.estado = 'en_progreso'
        
        # Calcular porcentaje
        if self.total_preguntas > 0:
            self.porcentaje_avance = (self.preguntas_respondidas / self.total_preguntas) * 100
        
        # Verificar si está vencido (excepto si ya está completado)
        if self.estado not in ['completado', 'rechazado'] and self.fecha_limite < timezone.now().date():
            self.estado = 'vencido'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.dimension:
            return f"{self.dimension.nombre} - {self.usuario_asignado.nombre_completo} ({self.estado})"
        return f"{self.encuesta.nombre} (Completa) - {self.usuario_asignado.nombre_completo} ({self.estado})"
    
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