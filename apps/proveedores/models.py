# apps/proveedores/models.py

from django.db import models
from apps.core.models import BaseModel
from apps.empresas.models import Empresa
import uuid

class Proveedor(BaseModel):
    """
    Proveedor de servicios
    - Superadmin: Puede crear proveedores globales (sin empresa)
    - Administrador: Puede crear proveedores para su empresa
    """
    
    TIPOS_PROVEEDOR = [
        ('consultoria', 'Consultoría CMMI/GRC'),
        ('software', 'Software/Herramientas'),
        ('capacitacion', 'Capacitación y Entrenamiento'),
        ('auditoria', 'Auditoría y Certificación'),
        ('infraestructura', 'Infraestructura TI'),
        ('otro', 'Otro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # ⭐ NUEVO: Relación con Empresa
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='proveedores',
        verbose_name='Empresa',
        null=True,
        blank=True,
        help_text='Si está vacío, es un proveedor global (solo superadmin)'
    )
    
    # Información Básica del Proveedor
    razon_social = models.CharField(max_length=200, verbose_name='Razón Social')
    ruc = models.CharField(max_length=20, verbose_name='RUC/Tax ID')
    
    # Tipo de Proveedor
    tipo_proveedor = models.CharField(
        max_length=50,
        choices=TIPOS_PROVEEDOR,
        verbose_name='Tipo de Proveedor'
    )
    
    # Contacto
    contacto_email = models.EmailField(verbose_name='Email de Contacto')
    contacto_telefono = models.CharField(max_length=20, verbose_name='Teléfono')
    
    # Usuario que creó el proveedor
    creado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='proveedores_creados',
        verbose_name='Creado Por'
    )
    
    class Meta:
        db_table = 'proveedores'
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['ruc']),
            models.Index(fields=['tipo_proveedor']),
            models.Index(fields=['activo']),
            models.Index(fields=['empresa']),  # ⭐ NUEVO índice
        ]
        # ⭐ NUEVO: RUC único por empresa (permite duplicados entre empresas)
        constraints = [
            models.UniqueConstraint(
                fields=['ruc', 'empresa'],
                name='unique_ruc_por_empresa'
            )
        ]
    
    def __str__(self):
        empresa_str = f" - {self.empresa.nombre}" if self.empresa else " (Global)"
        return f"{self.razon_social}{empresa_str}"
    
    def save(self, *args, **kwargs):
        # Validar lógica de empresa según el rol del creador
        if self.creado_por:
            # Si el creador es superadmin, puede crear proveedores globales
            if self.creado_por.rol == 'superadmin':
                # Superadmin puede dejar empresa = None (proveedor global)
                pass
            else:
                # Otros roles (administrador) DEBEN asignar su empresa
                if not self.empresa:
                    if self.creado_por.empresa:
                        self.empresa = self.creado_por.empresa
                    else:
                        raise ValueError('Los administradores deben tener una empresa asignada para crear proveedores')
        
        # Si es nuevo proveedor, inicia desactivado
        if not self.pk:
            self.activo = False
        
        super().save(*args, **kwargs)
    
    def activar(self):
        """Activar proveedor"""
        self.activo = True
        self.save()
    
    def desactivar(self):
        """Desactivar proveedor"""
        self.activo = False
        self.save()
    
    @property
    def es_global(self):
        """Verifica si es un proveedor global (sin empresa)"""
        return self.empresa is None