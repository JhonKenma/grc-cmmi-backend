# apps/encuestas/models.py
from django.db import models
from apps.core.models import BaseModel
from apps.empresas.models import Empresa
import uuid

class Encuesta(BaseModel):
    """
    Plantilla base de encuesta que puede ser reutilizada por múltiples empresas
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=300, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    version = models.CharField(max_length=20, default='1.0', verbose_name='Versión')
    es_plantilla = models.BooleanField(default=True, verbose_name='Es Plantilla')
    
    class Meta:
        db_table = 'encuestas'
        verbose_name = 'Encuesta'
        verbose_name_plural = 'Encuestas'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['es_plantilla', 'activo']),
        ]
    
    def __str__(self):
        return f"{self.nombre} v{self.version}"
    
    @property
    def total_dimensiones(self):
        return self.dimensiones.filter(activo=True).count()
    
    @property
    def total_preguntas(self):
        from .models import Pregunta
        return Pregunta.objects.filter(
            dimension__encuesta=self,
            activo=True
        ).count()


class Dimension(BaseModel):
    """
    Dimensiones o Secciones de una encuesta
    Ejemplo: Gobernanza, Datos, Desarrollo
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encuesta = models.ForeignKey(
        Encuesta,
        on_delete=models.CASCADE,
        related_name='dimensiones',
        verbose_name='Encuesta'
    )
    codigo = models.CharField(max_length=20, verbose_name='Código')
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')
    
    class Meta:
        db_table = 'dimensiones'
        verbose_name = 'Dimensión'
        verbose_name_plural = 'Dimensiones'
        ordering = ['encuesta', 'orden', 'codigo']
        unique_together = [['encuesta', 'codigo']]
        indexes = [
            models.Index(fields=['encuesta', 'orden']),
            models.Index(fields=['codigo']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @property
    def total_preguntas(self):
        return self.preguntas.filter(activo=True).count()


class Pregunta(BaseModel):
    """
    Preguntas de la encuesta
    Cada pregunta pertenece a una dimensión
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dimension = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name='preguntas',
        verbose_name='Dimensión'
    )
    codigo = models.CharField(max_length=50, verbose_name='Código')
    titulo = models.CharField(max_length=500, verbose_name='Título')
    texto = models.TextField(verbose_name='Texto de la Pregunta')
    peso = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        verbose_name='Peso',
        help_text='Ponderación de la pregunta en el cálculo'
    )
    obligatoria = models.BooleanField(default=True, verbose_name='Obligatoria')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')
    
    class Meta:
        db_table = 'preguntas'
        verbose_name = 'Pregunta'
        verbose_name_plural = 'Preguntas'
        ordering = ['dimension', 'orden', 'codigo']
        unique_together = [['dimension', 'codigo']]
        indexes = [
            models.Index(fields=['dimension', 'orden']),
            models.Index(fields=['codigo']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.titulo}"


class NivelReferencia(BaseModel):
    """
    Los 5 niveles de madurez para cada pregunta
    Son REFERENCIA, no respuestas del usuario
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='niveles_referencia',
        verbose_name='Pregunta'
    )
    numero = models.IntegerField(
        choices=[(i, f'Nivel {i}') for i in range(1, 6)],
        verbose_name='Número de Nivel'
    )
    descripcion = models.TextField(verbose_name='Descripción del Nivel')
    recomendaciones = models.TextField(
        blank=True,
        verbose_name='Recomendaciones',
        help_text='Qué hacer para alcanzar este nivel'
    )
    
    class Meta:
        db_table = 'niveles_referencia'
        verbose_name = 'Nivel de Referencia'
        verbose_name_plural = 'Niveles de Referencia'
        ordering = ['pregunta', 'numero']
        unique_together = [['pregunta', 'numero']]
        indexes = [
            models.Index(fields=['pregunta', 'numero']),
        ]
    
    def __str__(self):
        return f"{self.pregunta.codigo} - Nivel {self.numero}"


class ConfigNivelDeseado(BaseModel):
    """
    Configuración del nivel deseado por dimensión y empresa
    Cada empresa puede tener objetivos diferentes
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dimension = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name='configuraciones_nivel',
        verbose_name='Dimensión'
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='configuraciones_nivel',
        verbose_name='Empresa'
    )
    nivel_deseado = models.IntegerField(
        choices=[(i, f'Nivel {i}') for i in range(1, 6)],
        verbose_name='Nivel Deseado'
    )
    configurado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='configuraciones_realizadas',
        verbose_name='Configurado Por'
    )
    motivo_cambio = models.TextField(
        blank=True,
        verbose_name='Motivo del Cambio',
        help_text='Razón por la que se estableció este nivel'
    )
    
    class Meta:
        db_table = 'config_niveles_deseados'
        verbose_name = 'Configuración Nivel Deseado'
        verbose_name_plural = 'Configuraciones Niveles Deseados'
        ordering = ['-fecha_creacion']
        unique_together = [['dimension', 'empresa']]
        indexes = [
            models.Index(fields=['dimension', 'empresa']),
            models.Index(fields=['empresa']),
        ]
    
    def __str__(self):
        return f"{self.empresa.nombre} - {self.dimension.nombre} - Nivel {self.nivel_deseado}"