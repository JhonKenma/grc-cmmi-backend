# apps/respuestas/models.py - CON CÓDIGO DE DOCUMENTO

from django.db import models
from apps.core.models import BaseModel
from apps.asignaciones.models import Asignacion
from apps.encuestas.models import Pregunta, Dimension
from django.core.exceptions import ValidationError
import uuid
import os


class TipoDocumento(BaseModel):
    """
    Catálogo de tipos de documentos para evidencias
    Configurable por empresa
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='tipos_documento',
        verbose_name='Empresa'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre del Tipo')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    requiere_fecha = models.BooleanField(
        default=True,
        verbose_name='Requiere Fecha de Creación'
    )
    
    class Meta:
        db_table = 'tipos_documento'
        verbose_name = 'Tipo de Documento'
        verbose_name_plural = 'Tipos de Documento'
        ordering = ['empresa', 'nombre']
        unique_together = [['empresa', 'nombre']]
        indexes = [
            models.Index(fields=['empresa', 'activo']),
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.empresa.nombre})"


class Respuesta(BaseModel):
    """
    Respuesta de un usuario a una pregunta específica
    ⭐ ACTUALIZADO: Con 4 opciones de respuesta según puntaje CMMI
    """
    
    # ⭐ ACTUALIZADO: 4 opciones de respuesta
    OPCIONES_RESPUESTA = [
        ('SI_CUMPLE', 'Sí Cumple'),              # 1.0 punto
        ('CUMPLE_PARCIAL', 'Cumple Parcialmente'), # 0.5 puntos
        ('NO_CUMPLE', 'No Cumple'),              # 0.0 puntos
        ('NO_APLICA', 'No Aplica'),              # Excluido del cálculo
    ]
    
    ESTADOS = [
        ('borrador', 'Borrador'),
        ('enviado', 'Enviado'),
        ('modificado_admin', 'Modificado por Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asignacion = models.ForeignKey(
        Asignacion,
        on_delete=models.CASCADE,
        related_name='respuestas',
        verbose_name='Asignación'
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='respuestas',
        verbose_name='Pregunta'
    )
    respuesta = models.CharField(
        max_length=20,
        choices=OPCIONES_RESPUESTA,
        verbose_name='Respuesta',
        help_text='Nivel de cumplimiento: Sí (1.0), Parcial (0.5), No (0.0), N/A (excluido)'
    )
    justificacion = models.TextField(
        verbose_name='Justificación',
        blank=True,
        default='',
        help_text='Obligatorio para "Sí Cumple" (mínimo 10 caracteres)'
    )
    comentarios_adicionales = models.TextField(
        blank=True,
        default='',
        verbose_name='Comentarios Adicionales'
    )
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='borrador',
        verbose_name='Estado'
    )
    
    # CAMPOS DE AUDITORÍA
    respondido_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='respuestas_creadas',
        verbose_name='Respondido por'
    )
    respondido_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name='Fecha de Respuesta'
    )
    
    modificado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_modificadas',
        verbose_name='Última modificación por'
    )
    modificado_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de última modificación'
    )
    
    version = models.IntegerField(
        default=1,
        verbose_name='Versión'
    )
    
    class Meta:
        db_table = 'respuestas'
        verbose_name = 'Respuesta'
        verbose_name_plural = 'Respuestas'
        ordering = ['-respondido_at']
        unique_together = [['asignacion', 'pregunta']]
        indexes = [
            models.Index(fields=['asignacion', 'estado']),
            models.Index(fields=['pregunta']),
            models.Index(fields=['respondido_por']),
            models.Index(fields=['modificado_por']),
        ]
    
    def __str__(self):
        return f"{self.pregunta.codigo} - {self.get_respuesta_display()}"
    
    def clean(self):
        """Validaciones personalizadas"""
        # Validar que pregunta pertenezca a dimensión
        if self.pregunta.dimension != self.asignacion.dimension:
            raise ValidationError({
                'pregunta': 'La pregunta no pertenece a la dimensión de esta asignación'
            })
        
        # ⭐ VALIDACIÓN OBLIGATORIA: Para "Sí Cumple", justificación mínima 10 caracteres
        if self.respuesta == 'SI_CUMPLE':
            if not self.justificacion or len(self.justificacion.strip()) < 10:
                raise ValidationError({
                    'justificacion': 'Para respuestas "Sí Cumple", la justificación debe tener al menos 10 caracteres'
                })
        
        # Validación general de justificación (para todas las respuestas)
        if self.estado in ['enviado', 'modificado_admin']:
            if not self.justificacion or len(self.justificacion.strip()) < 10:
                raise ValidationError({
                    'justificacion': 'La justificación debe tener al menos 10 caracteres'
                })
        
        # ⭐ VALIDACIÓN: Para "Sí Cumple" enviado, debe tener evidencias
        if self.pk and self.respuesta == 'SI_CUMPLE' and self.estado in ['enviado', 'modificado_admin']:
            if not self.evidencias.filter(activo=True).exists():
                raise ValidationError({
                    'evidencias': 'Las respuestas "Sí Cumple" requieren al menos una evidencia'
                })
        
        # Máximo 3 evidencias
        if self.pk and self.evidencias.count() > 3:
            raise ValidationError({
                'evidencias': 'Se permiten máximo 3 archivos de evidencia por respuesta'
            })
    
    def save(self, *args, **kwargs):
        if self.pk:
            self.full_clean()
        super().save(*args, **kwargs)
        
        # Actualizar contador de preguntas respondidas en asignación
        if self.estado in ['enviado', 'modificado_admin']:
            asignacion = self.asignacion
            asignacion.preguntas_respondidas = asignacion.respuestas.filter(
                estado__in=['enviado', 'modificado_admin']
            ).count()
            asignacion.save()
    
    def get_puntaje(self):
        """
        ⭐ NUEVO MÉTODO: Retorna el puntaje según la respuesta
        - SI_CUMPLE: 1.0
        - CUMPLE_PARCIAL: 0.5
        - NO_CUMPLE: 0.0
        - NO_APLICA: None (se excluye del cálculo)
        """
        puntajes = {
            'SI_CUMPLE': 1.0,
            'CUMPLE_PARCIAL': 0.5,
            'NO_CUMPLE': 0.0,
            'NO_APLICA': None,  # Excluido
        }
        return puntajes.get(self.respuesta, 0.0)


class HistorialRespuesta(models.Model):
    """
    Registro de auditoría para cambios en respuestas
    """
    
    TIPOS_CAMBIO = [
        ('creacion', 'Creación Inicial'),
        ('modificacion_respuesta', 'Modificación de Respuesta'),
        ('modificacion_justificacion', 'Modificación de Justificación'),
        ('agregado_evidencia', 'Agregado de Evidencia'),
        ('eliminado_evidencia', 'Eliminación de Evidencia'),
        ('modificacion_comentarios', 'Modificación de Comentarios'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    respuesta = models.ForeignKey(
        Respuesta,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='Respuesta'
    )
    
    tipo_cambio = models.CharField(
        max_length=50,
        choices=TIPOS_CAMBIO,
        verbose_name='Tipo de Cambio'
    )
    
    usuario = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Usuario que realizó el cambio'
    )
    
    # Valores anteriores
    valor_anterior_respuesta = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Respuesta Anterior'
    )
    valor_anterior_justificacion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Justificación Anterior'
    )
    valor_anterior_comentarios = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentarios Anteriores'
    )
    
    # Valores nuevos
    valor_nuevo_respuesta = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Respuesta Nueva'
    )
    valor_nuevo_justificacion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Justificación Nueva'
    )
    valor_nuevo_comentarios = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentarios Nuevos'
    )
    
    motivo = models.TextField(
        blank=True,
        verbose_name='Motivo del Cambio'
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='User Agent'
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora del Cambio'
    )
    
    class Meta:
        db_table = 'historial_respuestas'
        verbose_name = 'Historial de Respuesta'
        verbose_name_plural = 'Historial de Respuestas'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['respuesta', '-timestamp']),
            models.Index(fields=['usuario', '-timestamp']),
            models.Index(fields=['tipo_cambio']),
        ]
    
    def __str__(self):
        return f"{self.tipo_cambio} por {self.usuario} - {self.timestamp}"


def evidencia_upload_path(instance, filename):
    """
    Genera ruta para guardar evidencias
    """
    ext = os.path.splitext(filename)[1]
    nuevo_nombre = f"{uuid.uuid4()}{ext}"
    return f"evidencias/{instance.respuesta.asignacion.empresa_id}/{instance.respuesta.asignacion_id}/{nuevo_nombre}"


class Evidencia(BaseModel):
    """
    Archivos de evidencia adjuntos a una respuesta
    """
    
    TIPOS_DOCUMENTO_CHOICES = [
        ('politica', 'Política'),
        ('norma', 'Norma'),
        ('procedimiento', 'Procedimiento'),
        ('formato_interno', 'Formato Interno'),
        ('otro', 'Otro'),
    ]
    
    EXTENSIONES_PERMITIDAS = [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
        '.ppt', '.pptx', '.jpg', '.jpeg', '.png', 
        '.zip', '.rar', '.txt'
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    respuesta = models.ForeignKey(
        Respuesta,
        on_delete=models.CASCADE,
        related_name='evidencias',
        verbose_name='Respuesta'
    )
    
    # ⭐ CAMPO 1: Código de Documento (PRIMERO)
    codigo_documento = models.CharField(
        max_length=50,
        default='SIN-CODIGO',
        verbose_name='Código de Documento',
        help_text='Código único del documento (ej: POL-SEG-001, PROC-TI-045)',
        db_index=True
    )
    
    # ⭐ CAMPO 2: Tipo de Documento
    tipo_documento_enum = models.CharField(
        max_length=50,
        choices=TIPOS_DOCUMENTO_CHOICES,
        verbose_name='Tipo de Documento',
        default='otro'
    )
    
    # ⭐ CAMPO 3: Título del Documento
    titulo_documento = models.CharField(
        max_length=60,
        verbose_name='Título del Documento',
        default='Documento sin título'
    )
    
    objetivo_documento = models.CharField(
        max_length=180,
        verbose_name='Objetivo del Documento',
        default='Sin objetivo especificado'
    )
    
    fecha_ultima_actualizacion = models.DateField(
        verbose_name='Fecha de Última Actualización',
        auto_now_add=True
    )
    
    nombre_archivo_original = models.CharField(
        max_length=255,
        verbose_name='Nombre Archivo Original',
        blank=True,
        default=''
    )
    archivo = models.FileField(
        upload_to=evidencia_upload_path,
        verbose_name='Archivo'
    )
    tamanio_bytes = models.BigIntegerField(
        default=0,
        verbose_name='Tamaño en Bytes'
    )
    
    subido_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evidencias_subidas',
        verbose_name='Subido por'
    )
    
    class Meta:
        db_table = 'evidencias'
        verbose_name = 'Evidencia'
        verbose_name_plural = 'Evidencias'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['respuesta']),
            models.Index(fields=['tipo_documento_enum']),
            models.Index(fields=['subido_por']),
            models.Index(fields=['codigo_documento']),  # ⭐ Solo campos propios
            # ❌ ELIMINAR: models.Index(fields=['codigo_documento', 'respuesta__asignacion__empresa'])
            # Los índices NO pueden usar lookups de relaciones
        ]
    
    def __str__(self):
        return f"{self.codigo_documento} - {self.titulo_documento}"
    
    def clean(self):
        """Validaciones"""
        # Máximo 3 evidencias por respuesta
        if self.respuesta and not self.pk:
            if self.respuesta.evidencias.count() >= 3:
                raise ValidationError({
                    'respuesta': 'Solo se permiten máximo 3 archivos por respuesta'
                })
        
        # Validar archivo
        if self.archivo:
            ext = os.path.splitext(self.nombre_archivo_original or self.archivo.name)[1].lower()
            if ext not in self.EXTENSIONES_PERMITIDAS:
                raise ValidationError({
                    'archivo': f'Extensión no permitida. Válidas: {", ".join(self.EXTENSIONES_PERMITIDAS)}'
                })
            
            if self.archivo.size > 10 * 1024 * 1024:
                raise ValidationError({
                    'archivo': 'El archivo no puede superar los 10MB'
                })
    
    def save(self, *args, **kwargs):
        if self.archivo:
            if not self.nombre_archivo_original:
                self.nombre_archivo_original = self.archivo.name
            self.tamanio_bytes = self.archivo.size
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def url_archivo(self):
        if self.archivo:
            return self.archivo.url
        return None
    
    @property
    def tamanio_mb(self):
        return round(self.tamanio_bytes / (1024 * 1024), 2)
    
    @classmethod
    def buscar_por_codigo(cls, codigo_documento, empresa):
        """
        ⭐ MÉTODO DE BÚSQUEDA: Buscar evidencias existentes por código en la empresa
        Retorna todas las evidencias con ese código para alertar al usuario
        """
        return cls.objects.filter(
            codigo_documento__iexact=codigo_documento,  # Case-insensitive
            respuesta__asignacion__empresa=empresa,  # ✅ En el queryset SÍ funciona
            activo=True
        ).select_related(
            'respuesta',
            'respuesta__pregunta',
            'respuesta__pregunta__dimension',
            'respuesta__asignacion',
            'subido_por'
        ).order_by('-fecha_creacion')

class CalculoNivel(BaseModel):
    """
    Resultados calculados del nivel de madurez
    """
    
    CLASIFICACION_GAP = [
        ('cumplido', 'Cumplido'),
        ('superado', 'Superado'),
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto'),
        ('critico', 'Crítico'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asignacion = models.OneToOneField(
        Asignacion,
        on_delete=models.CASCADE,
        related_name='calculo_nivel',
        verbose_name='Asignación'
    )
    dimension = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name='calculos',
        verbose_name='Dimensión'
    )
    
    nivel_actual = models.IntegerField(
        choices=[(i, f'Nivel {i}') for i in range(1, 6)],
        verbose_name='Nivel Actual'
    )
    nivel_deseado = models.IntegerField(
        choices=[(i, f'Nivel {i}') for i in range(1, 6)],
        verbose_name='Nivel Deseado'
    )
    gap = models.IntegerField(verbose_name='GAP')
    
    total_preguntas = models.IntegerField(default=0)
    respuestas_yes = models.IntegerField(default=0)
    respuestas_no = models.IntegerField(default=0)
    respuestas_na = models.IntegerField(default=0)
    
    porcentaje_cumplimiento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    clasificacion_gap = models.CharField(
        max_length=20,
        choices=CLASIFICACION_GAP
    )
    
    calculado_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'calculos_nivel'
        verbose_name = 'Cálculo de Nivel'
        verbose_name_plural = 'Cálculos de Nivel'
        ordering = ['-calculado_at']
        indexes = [
            models.Index(fields=['asignacion']),
            models.Index(fields=['dimension']),
        ]
    
    def __str__(self):
        return f"{self.dimension.nombre} - Nivel {self.nivel_actual}"
    
    @staticmethod
    def calcular_nivel_desde_porcentaje(porcentaje):
        if porcentaje <= 20:
            return 1
        elif porcentaje <= 40:
            return 2
        elif porcentaje <= 60:
            return 3
        elif porcentaje <= 80:
            return 4
        else:
            return 5
    
    @staticmethod
    def clasificar_gap(gap):
        if gap == 0:
            return 'cumplido'
        elif gap < 0:
            return 'superado'
        elif gap == 1:
            return 'bajo'
        elif gap == 2:
            return 'medio'
        elif gap == 3:
            return 'alto'
        else:
            return 'critico'


class Iniciativa(BaseModel):
    """
    Iniciativa de remediación para un GAP
    """
    
    ESTADOS = [
        ('planificada', 'Planificada'),
        ('en_progreso', 'En Progreso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
        ('retrasada', 'Retrasada'),
    ]
    
    PRIORIDADES = [
        ('critica', 'Crítica'),
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    calculo_nivel = models.ForeignKey(
        CalculoNivel,
        on_delete=models.CASCADE,
        related_name='iniciativas'
    )
    
    dimension = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name='iniciativas'
    )
    
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='iniciativas'
    )
    
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    objetivo = models.TextField()
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='planificada'
    )
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDADES,
        default='media'
    )
    
    responsable = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='iniciativas_asignadas'
    )
    asignado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='iniciativas_creadas'
    )
    
    fecha_inicio_estimada = models.DateField()
    fecha_termino_estimada = models.DateField()
    fecha_inicio_real = models.DateField(null=True, blank=True)
    fecha_termino_real = models.DateField(null=True, blank=True)
    
    presupuesto_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    costo_real = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    moneda = models.CharField(max_length=3, default='USD')
    
    dias_alerta_previo = models.IntegerField(default=7)
    alerta_enviada = models.BooleanField(default=False)
    fecha_alerta_enviada = models.DateTimeField(null=True, blank=True)
    
    porcentaje_avance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    class Meta:
        db_table = 'iniciativas'
        verbose_name = 'Iniciativa'
        verbose_name_plural = 'Iniciativas'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['calculo_nivel']),
            models.Index(fields=['responsable', 'estado']),
            models.Index(fields=['fecha_termino_estimada']),
        ]
    
    def __str__(self):
        return self.titulo
    
    @property
    def dias_restantes(self):
        from django.utils import timezone
        if self.fecha_termino_estimada:
            delta = self.fecha_termino_estimada - timezone.now().date()
            return delta.days
        return None
    
    @property
    def requiere_alerta(self):
        if self.alerta_enviada or self.estado in ['completada', 'cancelada']:
            return False
        
        dias_restantes = self.dias_restantes
        if dias_restantes is not None and dias_restantes <= self.dias_alerta_previo:
            return True
        return False