# apps/proveedores/models.py

from django.db import models
from apps.core.models import BaseModel
from apps.empresas.models import Empresa
import uuid


class TipoProveedor(BaseModel):
    """
    Catálogo de tipos de proveedores
    Se carga inicialmente con los 36 tipos definidos
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='Nombre del Tipo'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )
    orden = models.IntegerField(
        default=0,
        verbose_name='Orden',
        help_text='Orden alfabético o de prioridad'
    )
    
    class Meta:
        db_table = 'tipos_proveedor'
        verbose_name = 'Tipo de Proveedor'
        verbose_name_plural = 'Tipos de Proveedor'
        ordering = ['orden', 'nombre']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['activo']),
        ]
    
    def __str__(self):
        return self.nombre


class ClasificacionProveedor(BaseModel):
    """
    Catálogo de clasificaciones de criticidad
    - Estratégico
    - Crítico
    - No crítico
    - Temporal
    """
    NIVELES_CRITICIDAD = [
        ('estrategico', 'Proveedor Estratégico'),
        ('critico', 'Proveedor Crítico'),
        ('no_critico', 'Proveedor No Crítico'),
        ('temporal', 'Proveedor Temporal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(
        max_length=50,
        unique=True,
        choices=NIVELES_CRITICIDAD,
        verbose_name='Código'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )
    color = models.CharField(
        max_length=7,
        default='#6B7280',
        verbose_name='Color (Hex)',
        help_text='Color en formato hexadecimal para UI'
    )
    
    class Meta:
        db_table = 'clasificaciones_proveedor'
        verbose_name = 'Clasificación de Proveedor'
        verbose_name_plural = 'Clasificaciones de Proveedor'
        ordering = ['codigo']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['activo']),
        ]
    
    def __str__(self):
        return self.nombre


class Proveedor(BaseModel):
    """
    Proveedor de servicios con información completa GRC
    - Superadmin: Puede crear proveedores globales (sin empresa)
    - Administrador: Puede crear proveedores para su empresa
    """
    
    NIVELES_RIESGO = [
        ('alto', 'Alto'),
        ('medio', 'Medio'),
        ('bajo', 'Bajo'),
    ]
    
    ESTADOS_PROVEEDOR = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('suspendido', 'Suspendido'),
    ]
    
    TIPOS_CONTRATO = [
        ('servicio', 'Contrato de Servicios'),
        ('compra', 'Contrato de Compra'),
        ('licencia', 'Licenciamiento'),
        ('outsourcing', 'Outsourcing'),
        ('consultoria', 'Consultoría'),
        ('mantenimiento', 'Mantenimiento'),
        ('otro', 'Otro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # ============================================================
    # RELACIONES
    # ============================================================
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='proveedores',
        verbose_name='Empresa',
        null=True,
        blank=True,
        help_text='Si está vacío, es un proveedor global (solo superadmin)'
    )
    
    tipo_proveedor = models.ForeignKey(
        TipoProveedor,
        on_delete=models.PROTECT,
        related_name='proveedores',
        verbose_name='Tipo de Proveedor'
    )
    
    clasificacion = models.ForeignKey(
        ClasificacionProveedor,
        on_delete=models.PROTECT,
        related_name='proveedores',
        verbose_name='Clasificación',
        null=True,
        blank=True,
        help_text='Clasificación de criticidad del proveedor'
    )
    
    creado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='proveedores_creados',
        verbose_name='Creado Por'
    )
    
    # ============================================================
    # INFORMACIÓN BÁSICA
    # ============================================================
    
    razon_social = models.CharField(max_length=200, verbose_name='Razón Social')
    nombre_comercial = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Nombre Comercial'
    )
    
    # ============================================================
    # INFORMACIÓN LEGAL Y FISCAL
    # ============================================================
    
    pais = models.CharField(
        max_length=100,
        default='Perú',
        verbose_name='País'
    )
    tipo_documento_fiscal = models.CharField(
        max_length=50,
        default='RUC',
        verbose_name='Tipo de Documento Fiscal',
        help_text='RUC, Tax ID, NIT, etc.'
    )
    numero_documento_fiscal = models.CharField(
        max_length=50,
        verbose_name='Número de Documento Fiscal'
    )
    direccion_legal = models.TextField(
        blank=True,
        null=True,
        verbose_name='Dirección Legal'
    )
    
    # ============================================================
    # CONTACTO
    # ============================================================
    
    nombre_contacto_principal = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Nombre del Contacto Principal'
    )
    cargo_contacto = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Cargo del Contacto'
    )
    email_contacto = models.EmailField(verbose_name='Email de Contacto')
    telefono_contacto = models.CharField(
        max_length=20,
        verbose_name='Teléfono de Contacto'
    )
    
    # ============================================================
    # RELACIÓN CONTRACTUAL
    # ============================================================
    
    numero_contrato = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Número de Contrato'
    )
    fecha_inicio_contrato = models.DateField(
        blank=True,
        null=True,
        verbose_name='Fecha de Inicio del Contrato'
    )
    fecha_fin_contrato = models.DateField(
        blank=True,
        null=True,
        verbose_name='Fecha de Fin del Contrato'
    )
    tipo_contrato = models.CharField(
        max_length=50,
        choices=TIPOS_CONTRATO,
        blank=True,
        null=True,
        verbose_name='Tipo de Contrato'
    )
    sla_aplica = models.BooleanField(
        default=False,
        verbose_name='¿Aplica SLA?'
    )
    
    # ============================================================
    # ESTADO Y CLASIFICACIÓN GRC
    # ============================================================
    
    nivel_riesgo = models.CharField(
        max_length=20,
        choices=NIVELES_RIESGO,
        default='medio',
        verbose_name='Nivel de Riesgo'
    )
    proveedor_estrategico = models.BooleanField(
        default=False,
        verbose_name='¿Es Proveedor Estratégico?'
    )
    estado_proveedor = models.CharField(
        max_length=20,
        choices=ESTADOS_PROVEEDOR,
        default='activo',
        verbose_name='Estado del Proveedor'
    )
    fecha_alta = models.DateField(
        auto_now_add=True,
        verbose_name='Fecha de Alta'
    )
    fecha_baja = models.DateField(
        blank=True,
        null=True,
        verbose_name='Fecha de Baja'
    )
    
    # ============================================================
    # CUMPLIMIENTO Y CONTROL
    # ============================================================
    
    requiere_certificaciones = models.BooleanField(
        default=False,
        verbose_name='¿Requiere Certificaciones?'
    )
    certificaciones = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Certificaciones',
        help_text='Lista de certificaciones: ISO 9001, ISO 27001, SOC 2, etc.'
    )
    cumple_compliance = models.BooleanField(
        default=True,
        verbose_name='¿Cumple Compliance?'
    )
    ultima_evaluacion_riesgo = models.DateField(
        blank=True,
        null=True,
        verbose_name='Última Evaluación de Riesgo'
    )
    proxima_evaluacion_riesgo = models.DateField(
        blank=True,
        null=True,
        verbose_name='Próxima Evaluación de Riesgo'
    )
    
    # ============================================================
    # OBSERVACIONES
    # ============================================================
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones'
    )
    
    class Meta:
        db_table = 'proveedores'
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['numero_documento_fiscal']),
            models.Index(fields=['tipo_proveedor']),
            models.Index(fields=['clasificacion']),
            models.Index(fields=['activo']),
            models.Index(fields=['empresa']),
            models.Index(fields=['nivel_riesgo']),
            models.Index(fields=['estado_proveedor']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['numero_documento_fiscal', 'empresa'],
                name='unique_documento_fiscal_por_empresa'
            )
        ]
    
    def __str__(self):
        empresa_str = f" - {self.empresa.nombre}" if self.empresa else " (Global)"
        return f"{self.razon_social}{empresa_str}"
    
    def save(self, *args, **kwargs):
        # Validar lógica de empresa según el rol del creador
        if self.creado_por:
            if self.creado_por.rol == 'superadmin':
                pass
            else:
                if not self.empresa:
                    if self.creado_por.empresa:
                        self.empresa = self.creado_por.empresa
                    else:
                        raise ValueError('Los administradores deben tener una empresa asignada para crear proveedores')
        
        super().save(*args, **kwargs)
    
    def activar(self):
        """Activar proveedor"""
        self.estado_proveedor = 'activo'
        self.activo = True
        self.save()
    
    def desactivar(self):
        """Desactivar proveedor"""
        self.estado_proveedor = 'inactivo'
        self.activo = False
        self.save()
    
    def suspender(self):
        """Suspender proveedor"""
        self.estado_proveedor = 'suspendido'
        self.activo = False
        self.save()
    
    @property
    def es_global(self):
        """Verifica si es un proveedor global (sin empresa)"""
        return self.empresa is None
    
    @property
    def nivel_criticidad(self):
        """Retorna el nivel de criticidad basado en la clasificación"""
        if self.clasificacion:
            return self.clasificacion.nombre
        return 'No definido'
    
    @property
    def contrato_vigente(self):
        """Verifica si el contrato está vigente"""
        if not self.fecha_inicio_contrato or not self.fecha_fin_contrato:
            return None
        
        from django.utils import timezone
        hoy = timezone.now().date()
        return self.fecha_inicio_contrato <= hoy <= self.fecha_fin_contrato