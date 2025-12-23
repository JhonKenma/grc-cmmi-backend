# apps/usuarios/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Usuario

@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'nombre_completo', 'empresa', 'rol', 'activo', 'fecha_creacion']
    list_filter = ['rol', 'empresa', 'activo', 'fecha_creacion']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['email']
    
    # Reemplazar completamente fieldsets porque ahora usamos EMAIL
    fieldsets = (
        (None, {
            'fields': ('email', 'password')  # <-- EMAIL en lugar de username
        }),
        (_('Información Personal'), {
            'fields': ('first_name', 'last_name', 'username')  # username es secundario
        }),
        (_('Información Empresarial'), {
            'fields': ('empresa', 'rol', 'telefono', 'cargo', 'departamento')
        }),
        (_('Personalización'), {
            'fields': ('avatar', 'activo')
        }),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        (_('Fechas Importantes'), {
            'fields': ('last_login', 'date_joined', 'fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    # Reemplazar add_fieldsets para crear usuarios con EMAIL
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),  # <-- EMAIL primero
        }),
        (_('Información Personal'), {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'username')  # username opcional
        }),
        (_('Información Empresarial'), {
            'classes': ('wide',),
            'fields': ('empresa', 'rol', 'telefono', 'cargo', 'departamento')
        }),
    )
    
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']