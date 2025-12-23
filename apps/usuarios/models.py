# apps/usuarios/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.empresas.models import Empresa

class Usuario(AbstractUser):
    """
    Usuario extendido con soporte multiempresa y roles
    Extiende el User de Django para agregar empresa y rol
    """
    
    ROLES = [
        ('superadmin', 'Super Administrador'),  # <-- NUEVO ROL
        ('administrador', 'Administrador'),
        ('usuario', 'Usuario'),
        ('auditor', 'Auditor'),
    ]
    
    # Email obligatorio y único
    email = models.EmailField(unique=True, verbose_name='Email')
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='usuarios',
        verbose_name='Empresa',
        null=True,
        blank=True
    )
    rol = models.CharField(
        max_length=20,
        choices=ROLES,
        default='usuario',
        verbose_name='Rol'
    )
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    cargo = models.CharField(max_length=100, blank=True, verbose_name='Cargo')
    departamento = models.CharField(max_length=100, blank=True, verbose_name='Departamento')
    avatar = models.ImageField(upload_to='usuarios/avatars/', null=True, blank=True, verbose_name='Avatar')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')
    
    # Configurar email como campo de autenticación
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['email']
        indexes = [
            models.Index(fields=['empresa', 'rol']),
            models.Index(fields=['email']),
            models.Index(fields=['rol']),
        ]
    
    def __str__(self):
        if self.empresa:
            return f"{self.get_full_name() or self.email} ({self.empresa.nombre})"
        return f"{self.get_full_name() or self.email}"
    
    def save(self, *args, **kwargs):
        # Sincronizar is_active con activo
        self.is_active = self.activo
        
        # Generar username automático si no existe
        if not self.username:
            self.username = self.email.split('@')[0]
        
        # Superadmin siempre es is_superuser y sin empresa
        if self.rol == 'superadmin':
            self.is_superuser = True
            self.is_staff = True
            self.empresa = None
        
        # Validar que usuarios con rol != superadmin tengan empresa
        if self.rol != 'superadmin' and not self.empresa:
            raise ValueError('Usuarios que no son superadmin deben tener una empresa asignada')
        
        super().save(*args, **kwargs)
    
    @property
    def es_superadmin(self):
        return self.rol == 'superadmin'
    
    @property
    def es_administrador(self):
        return self.rol == 'administrador'
    
    @property
    def es_auditor(self):
        return self.rol == 'auditor'
    
    @property
    def nombre_completo(self):
        return self.get_full_name() or self.email
    
    @property
    def total_asignaciones(self):
        if self.rol == 'superadmin':
            return 0
        return self.asignaciones.count()
    
    @property
    def asignaciones_pendientes(self):
        if self.rol == 'superadmin':
            return 0
        return self.asignaciones.filter(estado='pendiente').count()