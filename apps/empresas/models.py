# apps/empresas/models.py
from django.db import models
from django.utils import timezone      # ← django.utils, NO datetime
from datetime import timedelta         # ← timedelta sí viene de datetime
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
    
# ─────────────────────────────────────────────
# NUEVO: PlanEmpresa
# ─────────────────────────────────────────────    
class PlanEmpresa(BaseModel):
    """
    Define el plan contratado por cada empresa.
    Centraliza límites de usuarios, roles y vigencia.
    """

    TIPOS = [
        ('demo',        'Demo'),
        ('basico',      'Básico'),
        ('profesional', 'Profesional'),
        ('enterprise',  'Enterprise'),
    ]

    empresa = models.OneToOneField(
        Empresa,
        on_delete=models.CASCADE,
        related_name='plan',
        verbose_name='Empresa'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS,
        default='demo',
        verbose_name='Tipo de Plan'
    )
    fecha_inicio     = models.DateTimeField(default=timezone.now, verbose_name='Fecha de Inicio')
    fecha_expiracion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Expiración')
    max_usuarios     = models.PositiveIntegerField(default=3, verbose_name='Máx. Usuarios')
    max_administradores = models.PositiveIntegerField(default=1, verbose_name='Máx. Administradores')
    max_auditores    = models.PositiveIntegerField(default=1, verbose_name='Máx. Auditores')

    class Meta:
        db_table  = 'planes_empresa'
        verbose_name = 'Plan de Empresa'
        verbose_name_plural = 'Planes de Empresa'

    def __str__(self):
        return f"{self.empresa.nombre} — {self.get_tipo_display()}"

    # ── Propiedades de estado ──────────────────

    @property
    def esta_activo(self):
        """Sin fecha de expiración = plan sin límite (enterprise)"""
        if not self.fecha_expiracion:
            return True
        return timezone.now() < self.fecha_expiracion

    @property
    def dias_restantes(self):
        if not self.fecha_expiracion:
            return None
        delta = self.fecha_expiracion - timezone.now()
        return max(delta.days, 0)

    # ── Lógica de límites ──────────────────────

    def puede_crear_usuario(self, rol: str) -> tuple:
        """
        Verifica si la empresa puede crear un usuario del rol dado.
        Retorna (True, '') o (False, 'motivo').
        """
        if not self.esta_activo:
            return False, 'El plan de la empresa ha expirado'

        empresa = self.empresa
        limites = {
            'usuario':       ('usuario',       self.max_usuarios),
            'administrador': ('administrador',  self.max_administradores),
            'auditor':       ('auditor',        self.max_auditores),
        }

        if rol not in limites:
            return True, ''  # superadmin u otros sin límite

        rol_filtro, maximo = limites[rol]
        actuales = empresa.usuarios.filter(rol=rol_filtro, activo=True).count()

        if actuales >= maximo:
            return False, f'Límite de {maximo} {rol}(s) alcanzado para este plan'

        return True, ''

    # ── Factories ─────────────────────────────

    @classmethod
    def crear_demo(cls, empresa):
        """Crea un plan demo: 3 usuarios, 1 admin, 1 auditor, 60 días"""
        return cls.objects.create(
            empresa=empresa,
            tipo='demo',
            max_usuarios=3,
            max_administradores=1,
            max_auditores=1,
            fecha_expiracion=timezone.now() + timedelta(days=60)
        )

    @classmethod
    def crear_plan(cls, empresa, tipo, max_usuarios,
                   max_administradores, max_auditores, dias_vigencia=None):
        """Factory genérico para cualquier plan"""
        expiracion = None
        if dias_vigencia:
            expiracion = timezone.now() + timedelta(days=dias_vigencia)
        return cls.objects.create(
            empresa=empresa,
            tipo=tipo,
            max_usuarios=max_usuarios,
            max_administradores=max_administradores,
            max_auditores=max_auditores,
            fecha_expiracion=expiracion
        )