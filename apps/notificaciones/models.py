# apps/notificaciones/models.py
from django.db import models
from apps.core.models import BaseModel
from apps.usuarios.models import Usuario
import uuid

class Notificacion(BaseModel):
    """
    Sistema de notificaciones reutilizable
    Soporta notificaciones internas (campanita) y emails
    """
    
    TIPOS = [
        ('asignacion_evaluacion', 'Asignación de Evaluación'),
        ('asignacion_dimension', 'Asignación de Dimensión'),
        ('recordatorio_plazo', 'Recordatorio de Plazo'),
        ('evaluacion_completada', 'Evaluación Completada'),
        ('evaluacion_vencida', 'Evaluación Vencida'),
        ('comentario', 'Nuevo Comentario'),
        ('aprobacion', 'Solicitud de Aprobación'),
        ('sistema', 'Notificación del Sistema'),
    ]
    
    PRIORIDADES = [
        ('baja', 'Baja'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Usuario que recibe la notificación
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='notificaciones',
        verbose_name='Usuario'
    )
    
    # Tipo y contenido
    tipo = models.CharField(
        max_length=50,
        choices=TIPOS,
        verbose_name='Tipo'
    )
    titulo = models.CharField(max_length=255, verbose_name='Título')
    mensaje = models.TextField(verbose_name='Mensaje')
    
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDADES,
        default='normal',
        verbose_name='Prioridad'
    )
    
    # Estado
    leida = models.BooleanField(default=False, verbose_name='Leída')
    fecha_leida = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Lectura')
    
    # Email
    email_enviado = models.BooleanField(default=False, verbose_name='Email Enviado')
    fecha_email_enviado = models.DateTimeField(null=True, blank=True, verbose_name='Fecha Email Enviado')
    
    # Metadata adicional (JSON para flexibilidad)
    datos_adicionales = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos Adicionales',
        help_text='Información adicional como IDs, enlaces, etc.'
    )
    
    # URL de acción (opcional)
    url_accion = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='URL de Acción',
        help_text='URL a la que redirigir cuando se hace clic en la notificación'
    )
    
    class Meta:
        db_table = 'notificaciones'
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['usuario', 'leida']),
            models.Index(fields=['tipo']),
            models.Index(fields=['prioridad']),
            models.Index(fields=['fecha_creacion']),
        ]
    
    def __str__(self):
        return f"{self.titulo} - {self.usuario.email} ({'Leída' if self.leida else 'No leída'})"
    
    def marcar_como_leida(self):
        """Marca la notificación como leída"""
        if not self.leida:
            from django.utils import timezone
            self.leida = True
            self.fecha_leida = timezone.now()
            self.save(update_fields=['leida', 'fecha_leida'])
    
    def marcar_email_enviado(self):
        """Marca que el email fue enviado"""
        if not self.email_enviado:
            from django.utils import timezone
            self.email_enviado = True
            self.fecha_email_enviado = timezone.now()
            self.save(update_fields=['email_enviado', 'fecha_email_enviado'])


class PlantillaNotificacion(BaseModel):
    """
    Plantillas para notificaciones y emails
    Permite personalizar mensajes por tipo
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Tipo de Notificación'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    
    # Plantilla para notificación interna
    titulo_plantilla = models.CharField(
        max_length=255,
        verbose_name='Plantilla de Título',
        help_text='Usa {{variable}} para variables dinámicas'
    )
    mensaje_plantilla = models.TextField(
        verbose_name='Plantilla de Mensaje',
        help_text='Usa {{variable}} para variables dinámicas'
    )
    
    # Plantilla para email
    asunto_email = models.CharField(
        max_length=255,
        verbose_name='Asunto del Email'
    )
    cuerpo_email = models.TextField(
        verbose_name='Cuerpo del Email (HTML)',
        help_text='Soporta HTML. Usa {{variable}} para variables dinámicas'
    )
    
    # Configuración
    enviar_email = models.BooleanField(
        default=True,
        verbose_name='Enviar Email'
    )
    prioridad_default = models.CharField(
        max_length=20,
        choices=Notificacion.PRIORIDADES,
        default='normal',
        verbose_name='Prioridad por Defecto'
    )
    
    class Meta:
        db_table = 'plantillas_notificacion'
        verbose_name = 'Plantilla de Notificación'
        verbose_name_plural = 'Plantillas de Notificación'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.tipo})"
    
    def renderizar(self, contexto):
        """
        Renderiza la plantilla con el contexto dado
        
        Args:
            contexto (dict): Variables para reemplazar en la plantilla
        
        Returns:
            dict: {'titulo', 'mensaje', 'asunto_email', 'cuerpo_email'}
        """
        titulo = self.titulo_plantilla
        mensaje = self.mensaje_plantilla
        asunto = self.asunto_email
        cuerpo = self.cuerpo_email
        
        # Reemplazar variables {{variable}} con valores del contexto
        for key, value in contexto.items():
            placeholder = f"{{{{{key}}}}}"
            titulo = titulo.replace(placeholder, str(value))
            mensaje = mensaje.replace(placeholder, str(value))
            asunto = asunto.replace(placeholder, str(value))
            cuerpo = cuerpo.replace(placeholder, str(value))
        
        return {
            'titulo': titulo,
            'mensaje': mensaje,
            'asunto_email': asunto,
            'cuerpo_email': cuerpo
        }