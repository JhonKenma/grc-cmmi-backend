# apps/respuestas/models.py

from django.db import models
from apps.core.models import BaseModel
from apps.core.services.storage_service import StorageService
from apps.asignaciones.models import Asignacion
from apps.encuestas.models import Pregunta, Dimension
from django.core.exceptions import ValidationError
import uuid
import os

# =============================================================================
# IMPORTANTE: Importamos TipoDocumento desde la nueva app 'documentos'
# =============================================================================
from apps.documentos.models import TipoDocumento


class Respuesta(BaseModel):
    """
    Respuesta de un usuario a una pregunta.

    NUEVO FLUJO:
    - El usuario SOLO puede marcar NO_APLICA (con justificación obligatoria)
      O dejar respuesta=None y subir evidencias + justificación.
    - Las opciones SI_CUMPLE / CUMPLE_PARCIAL / NO_CUMPLE
      SOLO las asigna el Auditor después de revisar.
    - Estados del ciclo de vida:
        borrador            → El usuario está respondiendo
        enviado             → El usuario envió, esperando revisión del auditor
        pendiente_auditoria → Notificación enviada al auditor (alias de enviado)
        auditado            → El auditor calificó todas las preguntas
        modificado_admin    → El administrador hizo ajustes
    """

    # ── Opciones que SOLO usa el Auditor ────────────────────────────────────
    CALIFICACIONES_AUDITOR = [
        ('SI_CUMPLE',      'Sí Cumple'),           # 1.0 punto
        ('CUMPLE_PARCIAL', 'Cumple Parcialmente'),  # 0.5 puntos
        ('NO_CUMPLE',      'No Cumple'),            # 0.0 puntos
    ]

    # ── Opción que usa el Usuario ────────────────────────────────────────────
    OPCIONES_USUARIO = [
        ('NO_APLICA', 'No Aplica'),   # Excluido del cálculo; requiere justificación
    ]

    # ── Todas las opciones posibles (para el campo respuesta) ────────────────
    OPCIONES_RESPUESTA = OPCIONES_USUARIO + CALIFICACIONES_AUDITOR

    ESTADOS = [
        ('borrador',            'Borrador'),
        ('enviado',             'Enviado'),
        ('pendiente_auditoria', 'Pendiente de Auditoría'),
        ('auditado',            'Auditado'),
        ('modificado_admin',    'Modificado por Admin'),
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

    # ── Campo de respuesta del USUARIO ───────────────────────────────────────
    # null=True → cuando el usuario sube evidencias sin marcar NO_APLICA
    # Solo valor permitido para el usuario: 'NO_APLICA'
    respuesta = models.CharField(
        max_length=20,
        choices=OPCIONES_RESPUESTA,
        null=True,
        blank=True,
        verbose_name='Respuesta del Usuario',
        help_text='El usuario solo puede marcar NO_APLICA. '
                  'Si deja vacío, sube evidencias para que el auditor califique.'
    )

    justificacion = models.TextField(
        verbose_name='Justificación del Usuario',
        blank=True,
        default='',
        help_text='Obligatorio siempre (mínimo 10 caracteres). '
                  'Para NO_APLICA: explica por qué no aplica.'
    )

    comentarios_adicionales = models.TextField(
        blank=True,
        default='',
        verbose_name='Comentarios Adicionales del Usuario'
    )

    # ── Campos de AUDITORÍA (solo los rellena el Auditor) ───────────────────
    calificacion_auditor = models.CharField(
        max_length=20,
        choices=CALIFICACIONES_AUDITOR,
        null=True,
        blank=True,
        verbose_name='Calificación del Auditor',
        help_text='SI_CUMPLE / CUMPLE_PARCIAL / NO_CUMPLE — asignado por el Auditor'
    )

    comentarios_auditor = models.TextField(
        blank=True,
        default='',
        verbose_name='Comentarios del Auditor',
        help_text='Observaciones del auditor sobre la respuesta'
    )

    recomendaciones_auditor = models.TextField(
        blank=True,
        default='',
        verbose_name='Recomendaciones del Auditor',
        help_text='Qué debe mejorar la empresa para subir de nivel'
    )

    fecha_auditoria = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Auditoría',
        help_text='Fecha en que el auditor calificó esta respuesta'
    )

    auditado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_auditadas',
        verbose_name='Auditado Por'
    )

    # ── Nivel de madurez (lo asigna el Auditor, no el usuario) ──────────────
    nivel_madurez = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=0.0,
        verbose_name='Nivel de Madurez',
        help_text='Asignado por el auditor (0–5 en incrementos de 0.5)'
    )

    # ── Auditoría de registro ────────────────────────────────────────────────
    estado = models.CharField(
        max_length=25,
        choices=ESTADOS,
        default='borrador',
        verbose_name='Estado'
    )

    respondido_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='respuestas_creadas',
        verbose_name='Respondido por'
    )
    respondido_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Respuesta')

    modificado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_modificadas',
        verbose_name='Última modificación por'
    )
    modificado_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de última modificación')

    version = models.IntegerField(default=1, verbose_name='Versión')

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
            models.Index(fields=['auditado_por']),
        ]

    def __str__(self):
        # Usamos getattr para evitar error si pregunta no está cargada
        codigo = getattr(self.pregunta, 'codigo', 'SIN-COD') if self.pregunta_id else 'SIN-PREG'
        return f"{codigo} - {self.get_respuesta_display()}"
    
    def clean(self):
        """Validaciones personalizadas"""
        # Validar que pregunta pertenezca a dimensión (si los objetos están cargados)
        if self.asignacion_id and self.pregunta_id:
            # Nota: Accedemos solo si existen para evitar errores en creación
            if hasattr(self.pregunta, 'dimension') and hasattr(self.asignacion, 'dimension'):
                if self.pregunta.dimension != self.asignacion.dimension:
                    raise ValidationError({
                        'pregunta': 'La pregunta no pertenece a la dimensión de esta asignación'
                    })
        
        # ⭐ VALIDACIÓN 1: Para "Sí Cumple", justificación mínima 10 caracteres
        if self.respuesta == 'SI_CUMPLE':
            if not self.justificacion or len(self.justificacion.strip()) < 10:
                raise ValidationError({
                    'justificacion': 'Para respuestas "Sí Cumple", la justificación debe tener al menos 10 caracteres'
                })
        
        # Validación general de justificación (para todas las respuestas) cuando se envía
        if self.estado in ['enviado', 'modificado_admin']:
            if not self.justificacion or len(self.justificacion.strip()) < 10:
                raise ValidationError({
                    'justificacion': 'La justificación debe tener al menos 10 caracteres'
                })
        
        # ⭐ VALIDACIÓN 2: Nivel de madurez debe ser 0 si NO_CUMPLE o NO_APLICA
        if self.respuesta in ['NO_CUMPLE', 'NO_APLICA']:
            if self.nivel_madurez != 0:
                raise ValidationError({
                    'nivel_madurez': 'El nivel de madurez debe ser 0 para "No Cumple" o "No Aplica"'
                })
        
        # ⭐ VALIDACIÓN 4: Para SI_CUMPLE o CUMPLE_PARCIAL, nivel de madurez debe ser > 0
        if self.estado in ['enviado', 'modificado_admin']:
            if self.respuesta in ['SI_CUMPLE', 'CUMPLE_PARCIAL']:
                if self.nivel_madurez == 0:
                    raise ValidationError({
                        'nivel_madurez': 'Debes indicar un nivel de madurez mayor a 0 si cumples total o parcialmente'
                    })
        
        # ⭐ VALIDACIÓN 5: Nivel de madurez debe ser múltiplo de 0.5
        if (self.nivel_madurez * 2) % 1 != 0:
            raise ValidationError({
                'calificacion_auditor': 'Una respuesta NO_APLICA no puede ser calificada por el auditor'
            })
        
        # ⭐ VALIDACIÓN 6: Para "Sí Cumple" o "Cumple Parcial" enviado, debe tener evidencias
        # Nota: Esta validación requiere que la instancia ya tenga PK para consultar la relación inversa
        if self.pk and self.respuesta in ['SI_CUMPLE', 'CUMPLE_PARCIAL'] and self.estado in ['enviado', 'modificado_admin']:
            if not self.evidencias.filter(activo=True).exists():
                raise ValidationError({
                    'evidencias': f'Las respuestas "{self.get_respuesta_display()}" requieren al menos una evidencia'
                })
        
        # Máximo 3 evidencias
        if self.pk and self.evidencias.count() > 3:
            raise ValidationError({
                'respuesta': 'SI_CUMPLE y CUMPLE_PARCIAL solo los asigna el Auditor.'
            })

        # 4. Nivel de madurez: solo el auditor lo asigna
        #    Solo se valida si ya hay calificación de auditor
        if self.calificacion_auditor:
            if self.calificacion_auditor == 'NO_CUMPLE' and self.nivel_madurez != 0:
                raise ValidationError({
                    'nivel_madurez': 'El nivel de madurez debe ser 0 para NO_CUMPLE'
                })
            if (self.nivel_madurez * 2) % 1 != 0:
                raise ValidationError({
                    'nivel_madurez': 'El nivel de madurez debe ser múltiplo de 0.5'
                })

    def save(self, *args, **kwargs):
        self.full_clean()  # Siempre validar
        super().save(*args, **kwargs)
        
        # Actualizar contador en asignación si se envía
        if self.estado in ['enviado', 'modificado_admin']:
            try:
                asignacion = self.asignacion
                asignacion.preguntas_respondidas = asignacion.respuestas.filter(
                    estado__in=['enviado', 'modificado_admin']
                ).count()
                asignacion.save()
            except Exception:
                pass # Evitar romper save si falla la actualización del contador
    
    def get_puntaje(self):
        """
        Puntaje basado en la calificación del auditor.
        - SI_CUMPLE      → 1.0
        - CUMPLE_PARCIAL → 0.5
        - NO_CUMPLE      → 0.0
        - NO_APLICA      → None (excluido del cálculo)
        - Sin calificar  → None
        """
        if self.respuesta == 'NO_APLICA':
            return None
        puntajes = {
            'SI_CUMPLE':      1.0,
            'CUMPLE_PARCIAL': 0.5,
            'NO_CUMPLE':      0.0,
        }
        return puntajes.get(self.respuesta, 0.0)
    
    def get_nivel_madurez_display_verbose(self):
        """Retorna solo el número del nivel de madurez"""
        return str(self.nivel_madurez)


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
    Función legacy para migraciones antiguas
    NO SE USA - Solo existe para compatibilidad con migraciones
    """
    ext = os.path.splitext(filename)[1]
    nuevo_nombre = f"{uuid.uuid4()}{ext}"
    try:
        # Intentamos obtener IDs de forma segura
        empresa_id = instance.respuesta.asignacion.empresa_id
        asignacion_id = instance.respuesta.asignacion_id
        return f"evidencias/{empresa_id}/{asignacion_id}/{nuevo_nombre}"
    except:
        return f"evidencias/temp/{nuevo_nombre}"


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
        null=True,  # ⭐ AÑADIR
        blank=True,  # ⭐ AÑADIR
        related_name='evidencias',
        verbose_name='Respuesta'
    )

    # NUEVO CAMPO: Vínculo al Maestro de Documentos
    documento_oficial = models.ForeignKey(
        'documentos.Documento', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='evidencias_utilizadas',
        verbose_name='Documento del Maestro',
        help_text='Si selecciona un documento del Módulo de Gestión Documental, se vinculará aquí.'
    )
    
    # ⭐ CAMPO 1: Código de Documento
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
    # CONFIGURACIÓN DEL CAMPO archivo PARA UPLOAD A SUPABASE
    archivo = models.CharField(
        max_length=500,
        verbose_name='Ruta del Archivo en Supabase',
        help_text='Ruta del archivo en Supabase Storage (ej: evidencias/empresa_123/archivo.pdf)'
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
            models.Index(fields=['codigo_documento']), 
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
                
    def clean(self):
        """Validaciones avanzadas"""

        super().clean()

        # ==========================================
        # 1️⃣ Máximo 3 evidencias por respuesta
        # ==========================================
        if self.respuesta_id and not self.pk:
            # Usamos filter count para evitar error de acceso antes de guardar
            count = Evidencia.objects.filter(respuesta_id=self.respuesta_id).count()
            if count >= 3:
                raise ValidationError({
                    'respuesta': 'Solo se permiten máximo 3 archivos por respuesta'
                })

        # ==========================================
        # 2️⃣ Si se vincula Documento Maestro
        # ==========================================
        if self.documento_oficial:

            doc = self.documento_oficial

            # 🔄 Sincronizar datos automáticamente
            self.codigo_documento = doc.codigo
            self.titulo_documento = doc.titulo
            self.objetivo_documento = doc.objetivo

            # ==========================================
            # 3️⃣ Validar si requiere Word + PDF (AJUSTE 2)
            # ==========================================
            # Verificamos si doc.tipo existe y tiene el flag
            if doc.tipo and doc.tipo.requiere_word_y_pdf:
                # Verificamos los campos del modelo Documento
                if not doc.archivo_pdf or not doc.archivo_editable:
                    raise ValidationError(
                        f"El documento maestro '{doc.codigo}' está incompleto. "
                        "Este tipo de documento requiere archivo PDF y Editable en el Maestro."
                    )

            # ==========================================
            # 4️⃣ Validación dinámica (ELIMINADA)
            # ==========================================
            # NOTA: Se eliminó el bloque que validaba 'configuracion_campos' 
            # porque ese campo JSON ya no existe en el modelo TipoDocumento actual.
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def url_archivo(self):
        """
        ⭐ OBTENER URL FIRMADA TEMPORAL DEL ARCHIVO
        """
        if self.archivo:
            # 1. Determinar la ruta real del archivo
            ruta_a_buscar = self.archivo
            
            # Si es vinculado, sacamos la ruta del PDF del documento maestro
            if self.archivo == 'VINCULADO_MAESTRO':
                if self.documento_oficial and self.documento_oficial.archivo_pdf:
                    ruta_a_buscar = str(self.documento_oficial.archivo_pdf)
                else:
                    return None # No hay archivo físico para generar URL
                    
            # 2. Pedir URL a Supabase
            try:
                from apps.core.services.storage_service import StorageService
                storage = StorageService()
                return storage.get_file_url(ruta_a_buscar, expires_in=3600)  # 1 hora
            except Exception as e:
                print(f"Error generando URL: {e}")
                return None
        return None
    
    @property
    def tamanio_mb(self):
        """Tamaño en MB"""
        return round(self.tamanio_bytes / (1024 * 1024), 2)
    
    @property
    def extension_archivo(self):
        """Obtener extensión del archivo"""
        if self.nombre_archivo_original:
            return os.path.splitext(self.nombre_archivo_original)[1].lower()
        return ''
    
    def delete(self, *args, **kwargs):
        """
        ⭐ ELIMINAR ARCHIVO DE SUPABASE ANTES DE ELIMINAR REGISTRO
        """
        if self.archivo:
            try:
                from apps.core.services.storage_service import StorageService
                storage = StorageService()
                result = storage.delete_file(self.archivo)
                if not result['success']:
                    print(f"⚠️ Advertencia: No se pudo eliminar archivo de Supabase: {result.get('error')}")
            except Exception as e:
                print(f"Error al eliminar archivo: {e}")
        
        super().delete(*args, **kwargs)
    
    @classmethod
    def buscar_por_codigo(cls, codigo_documento, empresa):
        """
        Buscar evidencias existentes por código en la empresa
        Retorna todas las evidencias con ese código para alertar al usuario
        """
        return cls.objects.filter(
            codigo_documento__iexact=codigo_documento,
            respuesta__asignacion__empresa=empresa,
            activo=True
        ).select_related(
            'respuesta',
            'respuesta__pregunta',
            'respuesta__pregunta__dimension',
            'respuesta__asignacion',
            'subido_por'
        ).order_by('-fecha_creacion')
        
    @staticmethod
    def validar_extension(filename):
        """Validar que la extensión sea permitida"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in Evidencia.EXTENSIONES_PERMITIDAS
    
    @staticmethod
    def validar_tamanio(file_size):
        """Validar tamaño máximo (10MB)"""
        MAX_SIZE = 10 * 1024 * 1024  # 10MB
        return file_size <= MAX_SIZE


class CalculoNivel(BaseModel):
    """
    Almacena el cálculo del nivel de madurez alcanzado vs deseado por dimensión
    Se recalcula cada vez que se completa/aprueba una asignación
    """
    
    CLASIFICACION_GAP = [
        ('critico', 'Crítico'),        # GAP >= 3
        ('alto', 'Alto'),              # GAP >= 2
        ('medio', 'Medio'),            # GAP >= 1
        ('bajo', 'Bajo'),              # GAP < 1
        ('cumplido', 'Cumplido'),      # GAP <= 0
        ('superado', 'Superado'),      # Nivel actual > nivel deseado
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    evaluacion_empresa = models.ForeignKey(
        'encuestas.EvaluacionEmpresa',
        on_delete=models.CASCADE,
        related_name='calculos_nivel',
        verbose_name='Evaluación Empresa',
        null=True,           # ⭐ AGREGAR
        blank=True,          # ⭐ AGREGAR
    )
    
    # ⭐ CORRECCIÓN CRÍTICA: Cambiado de OneToOneField a ForeignKey
    # Porque una asignación puede tener varios cálculos (uno por cada dimensión)
    asignacion = models.ForeignKey(
        'asignaciones.Asignacion',
        on_delete=models.CASCADE,
        related_name='calculos_nivel',
        verbose_name='Asignación'
    )
    
    dimension = models.ForeignKey(
        'encuestas.Dimension',
        on_delete=models.CASCADE,
        related_name='calculos',
        verbose_name='Dimensión'
    )
    
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='calculos_nivel',
        verbose_name='Empresa'
    )
    
    usuario = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.CASCADE,
        related_name='calculos_nivel',
        verbose_name='Usuario'
    )
    
    # ⭐ NIVELES
    nivel_deseado = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        verbose_name='Nivel Deseado',
        help_text='Nivel objetivo definido por el administrador (1-5)'
    )
    
    nivel_actual = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        verbose_name='Nivel Actual',
        help_text='Promedio de nivel_madurez de todas las respuestas del usuario'
    )
    
    gap = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        verbose_name='GAP',
        help_text='Diferencia: Nivel Deseado - Nivel Actual'
    )
    
    clasificacion_gap = models.CharField(
        max_length=20,
        choices=CLASIFICACION_GAP,
        verbose_name='Clasificación del GAP'
    )
    
    # ⭐ ESTADÍSTICAS DE RESPUESTAS
    total_preguntas = models.IntegerField(
        default=0,
        verbose_name='Total de Preguntas'
    )
    
    respuestas_si_cumple = models.IntegerField(
        default=0,
        verbose_name='Respuestas Sí Cumple'
    )
    
    respuestas_cumple_parcial = models.IntegerField(
        default=0,
        verbose_name='Respuestas Cumple Parcial'
    )
    
    respuestas_no_cumple = models.IntegerField(
        default=0,
        verbose_name='Respuestas No Cumple'
    )
    
    respuestas_no_aplica = models.IntegerField(
        default=0,
        verbose_name='Respuestas No Aplica'
    )
    
    porcentaje_cumplimiento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='% Cumplimiento',
        help_text='Porcentaje de preguntas con Sí Cumple o Cumple Parcial'
    )
    
    calculado_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Cálculo'
    )
    
    class Meta:
        db_table = 'calculos_nivel'
        verbose_name = 'Cálculo de Nivel'
        verbose_name_plural = 'Cálculos de Nivel'
        ordering = ['-calculado_at']
        unique_together = [['asignacion', 'dimension']]
        indexes = [
            models.Index(fields=['empresa', 'dimension']),
            models.Index(fields=['usuario', 'dimension']),
            models.Index(fields=['clasificacion_gap']),
            models.Index(fields=['calculado_at']),
        ]
    
    def __str__(self):
        return f"{self.usuario.nombre_completo} - {self.dimension.nombre} (GAP: {self.gap})"
    
    def save(self, *args, **kwargs):
        # Calcular GAP
        self.gap = self.nivel_deseado - self.nivel_actual
        
        # Clasificar GAP
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
        else:  # gap < 0
            self.clasificacion_gap = 'superado'
        
        super().save(*args, **kwargs)