# apps/empresas/models.py
from django.db import models
from apps.core.models import BaseModel

class Empresa(BaseModel):
    """
    Modelo para gestión multiempresa
    Cada empresa tiene sus propios usuarios, encuestas y datos aislados
    """
    
    # Tamaños de empresa
    TAMANIO_CHOICES = [
        ('micro', 'Microempresa'),
        ('pequena', 'Pequeña Empresa'),
        ('mediana', 'Mediana Empresa'),
        ('grande', 'Gran Empresa'),
        ('otro', 'Otro'),  # <-- AGREGAR ESTA OPCIÓN
    ]
    
    # Países
    PAIS_CHOICES = [
        ('PE', 'Perú'),
        ('CO', 'Colombia'),
        ('CL', 'Chile'),
        ('AR', 'Argentina'),
        ('MX', 'México'),
        ('EC', 'Ecuador'),
        ('BO', 'Bolivia'),
        ('VE', 'Venezuela'),
        ('BR', 'Brasil'),
        ('PY', 'Paraguay'),
        ('UY', 'Uruguay'),
        ('US', 'Estados Unidos'),
        ('ES', 'España'),
        ('OT', 'Otro'),  # <-- AGREGAR ESTA OPCIÓN
    ]
    
    # Sectores empresariales
    SECTOR_CHOICES = [
        ('tecnologia', 'Tecnología'),
        ('financiero', 'Financiero y Seguros'),
        ('manufactura', 'Manufactura'),
        ('retail', 'Retail y Comercio'),
        ('servicios', 'Servicios Profesionales'),
        ('salud', 'Salud y Farmacéutico'),
        ('educacion', 'Educación'),
        ('construccion', 'Construcción'),
        ('energia', 'Energía y Utilities'),
        ('telecomunicaciones', 'Telecomunicaciones'),
        ('agricultura', 'Agricultura y Ganadería'),
        ('mineria', 'Minería'),
        ('transporte', 'Transporte y Logística'),
        ('turismo', 'Turismo y Hospitalidad'),
        ('inmobiliario', 'Inmobiliario'),
        ('medios', 'Medios y Entretenimiento'),
        ('gobierno', 'Gobierno y Sector Público'),
        ('ong', 'ONG y Sin Fines de Lucro'),
        ('otro', 'Otro'),  # <-- AGREGAR ESTA OPCIÓN
    ]
    
    # Campos básicos
    nombre = models.CharField(max_length=200, unique=True, verbose_name='Nombre')
    razon_social = models.CharField(max_length=300, blank=True, verbose_name='Razón Social')
    
    # RUC o ID Fiscal
    ruc = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name='RUC / ID Fiscal',
        help_text='Número de identificación tributaria (RUC, RFC, NIT, etc.)'
    )
    
    # Campos con opciones
    pais = models.CharField(
        max_length=2,
        choices=PAIS_CHOICES,
        default='PE',
        verbose_name='País'
    )
    
    # ⭐ NUEVO: Campo para especificar otro país
    pais_otro = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Otro País (especificar)',
        help_text='Complete este campo si seleccionó "Otro" en País'
    )
    
    tamanio = models.CharField(
        max_length=20,
        choices=TAMANIO_CHOICES,
        blank=True,
        null=True,
        verbose_name='Tamaño de Empresa'
    )
    
    # ⭐ NUEVO: Campo para especificar otro tamaño
    tamanio_otro = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Otro Tamaño (especificar)',
        help_text='Complete este campo si seleccionó "Otro" en Tamaño'
    )
    
    sector = models.CharField(
        max_length=50,
        choices=SECTOR_CHOICES,
        blank=True,
        null=True,
        verbose_name='Sector o Rubro Empresarial'
    )
    
    # ⭐ NUEVO: Campo para especificar otro sector
    sector_otro = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Otro Sector (especificar)',
        help_text='Complete este campo si seleccionó "Otro" en Sector'
    )
    
    # Campos de contacto
    direccion = models.TextField(blank=True, verbose_name='Dirección')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Email')
    
    # Configuración
    timezone = models.CharField(max_length=50, default='America/Lima', verbose_name='Zona Horaria')
    logo = models.ImageField(upload_to='empresas/logos/', null=True, blank=True, verbose_name='Logo')
    
    class Meta:
        db_table = 'empresas'
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['pais']),
            models.Index(fields=['sector']),
            models.Index(fields=['tamanio']),
        ]
    
    def __str__(self):
        return self.nombre
    
    @property
    def total_usuarios(self):
        return self.usuarios.filter(activo=True).count()
    
    @property
    def total_encuestas(self):
        return self.encuestas.filter(activo=True).count()
    
    @property
    def pais_display(self):
        """Retorna el país, considerando el campo 'otro'"""
        if self.pais == 'OT' and self.pais_otro:
            return self.pais_otro
        return dict(self.PAIS_CHOICES).get(self.pais, self.pais)
    
    @property
    def tamanio_display(self):
        """Retorna el tamaño, considerando el campo 'otro'"""
        if not self.tamanio:
            return None
        if self.tamanio == 'otro' and self.tamanio_otro:
            return self.tamanio_otro
        return dict(self.TAMANIO_CHOICES).get(self.tamanio, self.tamanio)
    
    @property
    def sector_display(self):
        """Retorna el sector, considerando el campo 'otro'"""
        if not self.sector:
            return None
        if self.sector == 'otro' and self.sector_otro:
            return self.sector_otro
        return dict(self.SECTOR_CHOICES).get(self.sector, self.sector)
    
    # Mantener compatibilidad con nombres anteriores
    @property
    def pais_nombre(self):
        return self.pais_display
    
    @property
    def tamanio_nombre(self):
        return self.tamanio_display
    
    @property
    def sector_nombre(self):
        return self.sector_display