# apps/empresas/admin.py
from django.contrib import admin
from .models import Empresa

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'ruc', 'pais_display', 'sector_display', 
        'tamanio_display', 'total_usuarios', 'activo', 'fecha_creacion'
    ]
    search_fields = ['nombre', 'ruc', 'razon_social', 'email', 'pais_otro', 'sector_otro']
    list_filter = ['activo', 'pais', 'sector', 'tamanio', 'fecha_creacion']
    readonly_fields = [
        'fecha_creacion', 'fecha_actualizacion', 
        'total_usuarios', 'total_encuestas',
        'pais_display', 'sector_display', 'tamanio_display'
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'razon_social', 'ruc')
        }),
        ('Clasificación', {
            'fields': (
                ('pais', 'pais_otro'),
                ('tamanio', 'tamanio_otro'),
                ('sector', 'sector_otro')
            ),
            'description': 'Complete el campo "otro" solo si selecciona la opción "Otro"'
        }),
        ('Contacto', {
            'fields': ('direccion', 'telefono', 'email')
        }),
        ('Configuración', {
            'fields': ('timezone', 'logo', 'activo')
        }),
        ('Estadísticas', {
            'fields': ('total_usuarios', 'total_encuestas'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': (
                'fecha_creacion', 'fecha_actualizacion',
                'pais_display', 'sector_display', 'tamanio_display'
            ),
            'classes': ('collapse',)
        }),
    )