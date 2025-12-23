# apps/notificaciones/admin.py
from django.contrib import admin
from .models import Notificacion, PlantillaNotificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'usuario', 'tipo', 'prioridad', 'leida', 'email_enviado', 'fecha_creacion']
    list_filter = ['tipo', 'prioridad', 'leida', 'email_enviado', 'fecha_creacion']
    search_fields = ['titulo', 'mensaje', 'usuario__email', 'usuario__first_name', 'usuario__last_name']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'fecha_leida', 'fecha_email_enviado']
    ordering = ['-fecha_creacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('usuario', 'tipo', 'prioridad')
        }),
        ('Contenido', {
            'fields': ('titulo', 'mensaje', 'url_accion', 'datos_adicionales')
        }),
        ('Estado', {
            'fields': ('leida', 'fecha_leida', 'email_enviado', 'fecha_email_enviado', 'activo')
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PlantillaNotificacion)
class PlantillaNotificacionAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'enviar_email', 'prioridad_default', 'activo']
    list_filter = ['tipo', 'enviar_email', 'prioridad_default', 'activo']
    search_fields = ['nombre', 'tipo', 'titulo_plantilla']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('tipo', 'nombre')
        }),
        ('Plantilla de Notificación', {
            'fields': ('titulo_plantilla', 'mensaje_plantilla')
        }),
        ('Plantilla de Email', {
            'fields': ('asunto_email', 'cuerpo_email')
        }),
        ('Configuración', {
            'fields': ('enviar_email', 'prioridad_default', 'activo')
        }),
    )