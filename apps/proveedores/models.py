# apps/proveedores/models.py

from django.db import models
from apps.core.models import BaseModel
import uuid

class Proveedor(BaseModel):
    """
    Proveedor de servicios
    Solo gestionable por superadmin y administradores
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
    
    # Información Básica del Proveedor
    razon_social = models.CharField(max_length=200, verbose_name='Razón Social')
    ruc = models.CharField(max_length=20, unique=True, verbose_name='RUC/Tax ID')
    
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
    
    # Estado (activo/inactivo)
    # activo ya viene de BaseModel, pero lo configuramos en el save()
    
    class Meta:
        db_table = 'proveedores'
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['ruc']),
            models.Index(fields=['tipo_proveedor']),
            models.Index(fields=['activo']),
        ]
    
    def __str__(self):
        return f"{self.razon_social} ({self.get_tipo_proveedor_display()})"
    
    def save(self, *args, **kwargs):
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