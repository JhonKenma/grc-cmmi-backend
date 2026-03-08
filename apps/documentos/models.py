import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

# ==========================================
# 0. BASE MODEL (Abstracto)
# ==========================================
class BaseModel(models.Model):
    """Modelo base abstracto con UUID, timestamps y multitenancy"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    
    # Relación con Empresa (Multi-tenancy)
    empresa = models.ForeignKey(
        'empresas.Empresa', 
        on_delete=models.CASCADE, 
        null=True, blank=True
    )

    class Meta:
        abstract = True

# ==========================================
# 1. MODELOS DE APOYO (Procesos y Normas)
# ==========================================

class TipoDocumento(BaseModel):
    """
    Maestro de Tipos de Documentos (Políticas, Manuales, etc.)
    """
    nombre = models.CharField(max_length=100, verbose_name='Nombre del Tipo')
    
    # CAMPOS LÓGICOS
    abreviatura = models.CharField(max_length=10, help_text="Ej: POL, MAN, REG")
    nivel_jerarquico = models.PositiveSmallIntegerField(
        default=3, 
        help_text="1: Estratégico, 2: Táctico, 3: Operativo, 4: Instructivo"
    )
    requiere_word_y_pdf = models.BooleanField(
        default=True, 
        help_text="Si es True, el sistema exigirá subir ambos archivos (.pdf y .docx)"
    )

    class Meta:
        verbose_name = 'Tipo de Documento'
        verbose_name_plural = 'Tipos de Documento'
        db_table = 'tipos_documento'

    def __str__(self):
        return f"{self.abreviatura} - {self.nombre}"


class Proceso(BaseModel):
    nombre = models.CharField(max_length=255, verbose_name='Nombre del Proceso')
    sigla = models.CharField(max_length=10, verbose_name='Sigla', help_text='Ej: TI, RRHH')
    
    class Meta:
        verbose_name = 'Proceso'
        verbose_name_plural = 'Procesos'
        db_table = 'procesos'

    def __str__(self):
        return f"{self.sigla} - {self.nombre}"


class Norma(BaseModel):
    nombre = models.CharField(max_length=255, verbose_name='Nombre de la Norma')
    descripcion = models.TextField(verbose_name='Descripción', blank=True, null=True)

    class Meta:
        verbose_name = 'Norma'
        verbose_name_plural = 'Normas'
        db_table = 'normas'

    def __str__(self):
        return self.nombre

# ==========================================
# 2. MODELO PRINCIPAL (Documento Maestro)
# ==========================================

class Documento(BaseModel):
    
    ESTADOS = [
        ('borrador', 'Borrador'),
        ('en_revision', 'En Revisión'),
        ('vigente', 'Vigente'),
        ('obsoleto', 'Obsoleto'),
    ]

    CONFIDENCIALIDAD_CHOICES = [
        ('publico', 'Público'),
        ('interno', 'Uso Interno'),
        ('confidencial', 'Confidencial'),
        ('secreto', 'Secreto'),
        ('estrategico', 'Estratégico'),
    ]

    FRECUENCIA_CHOICES = [
        ('mensual', 'Mensual'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
        ('no_aplica', 'No Aplica'),
    ]

    # --- RELACIONES ---
    tipo = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        related_name='documentos',
        verbose_name='Tipo de Documento'
    )
    proceso = models.ForeignKey(
        Proceso,
        on_delete=models.PROTECT,
        related_name='documentos',
        verbose_name='Proceso Dueño', 
        null=True, blank=True
    )
    norma = models.ForeignKey(
        Norma,
        on_delete=models.SET_NULL,
        related_name='documentos',
        verbose_name='Referencia Normativa', 
        null=True, blank=True
    )

    # --- ATRIBUTOS PRINCIPALES ---
    codigo = models.CharField(max_length=50, verbose_name='Código de Documento')
    titulo = models.CharField(max_length=255, verbose_name='Título')
    
    # CAMBIO SOLICITADO: versión ahora es CharField para permitir decimales
    version = models.CharField(
        max_length=10, 
        default="1.0", 
        verbose_name='Versión',
        help_text='Permite decimales ej: 1.0, 1.1, 2.0'
    )
    
    # --- METADATOS DE GESTIÓN ---
    objetivo = models.TextField(verbose_name='Objetivo / Propósito', blank=True)
    alcance = models.TextField(verbose_name='Alcance (Org/Depto/Proceso)', blank=True)
    
    nivel_confidencialidad = models.CharField(
        max_length=20, choices=CONFIDENCIALIDAD_CHOICES, default='interno'
    )
    frecuencia_revision = models.CharField(
        max_length=20, choices=FRECUENCIA_CHOICES, default='anual'
    )
    periodo_retencion = models.PositiveIntegerField(
        default=5, verbose_name='Periodo de Retención (Años)'
    )

    # --- RESPONSABLES ---
    elaborado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='docs_elaborados'
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='docs_revisados'
    )
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='docs_aprobados'
    )
    
    # --- ARCHIVOS (Rutas guardadas en Supabase/S3) ---
    archivo_pdf = models.CharField(max_length=500, verbose_name='Ruta PDF (.pdf)', blank=True, null=True)
    archivo_editable = models.CharField(
        max_length=500, blank=True, null=True, verbose_name='Ruta Editable (.docx, .xlsx)'
    )

    # --- ESTADO Y FECHAS ---
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    fecha_emision = models.DateField(null=True, blank=True)
    fecha_proxima_revision = models.DateField(null=True, blank=True, verbose_name='Fecha Próxima Revisión')

    # --- LÓGICA INTERNA ---

    def clean(self):
        super().clean()
        
        # 1. Validación de Formato de Código (Opcional, pero recomendada)
        if hasattr(self, 'tipo') and self.tipo and self.codigo:
            prefijo = getattr(self.tipo, 'abreviatura', '').upper()
            # Validamos que el código empiece con el prefijo correcto
            if prefijo and not self.codigo.upper().startswith(f"{prefijo}"):
                # Esto es solo un warning visual si usas Admin, en API lo maneja el serializer
                pass 

        # NOTA IMPORTANTE SOBRE ARCHIVOS:
        # Se han eliminado las validaciones estrictas de archivos aquí (Raise ValidationError)
        # porque el flujo de creación en la API requiere guardar primero el objeto para obtener
        # el ID y luego subir los archivos.
        # La validación de obligatoriedad se maneja en el Serializer (apps/documentos/serializers.py).

    def save(self, *args, **kwargs):
        # Asegurar mayúsculas en el código
        if self.codigo:
            self.codigo = self.codigo.upper()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        db_table = 'documentos_maestros'
        ordering = ['-fecha_creacion']
        unique_together = ('empresa', 'codigo') 

    def __str__(self):
        return f"{self.codigo} - {self.titulo} (v{self.version})"