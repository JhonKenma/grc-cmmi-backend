# apps/asignaciones_iq/permissions.py
"""
Permisos personalizados para Asignaciones IQ
"""

from rest_framework import permissions


class PuedeAsignarEvaluaciones(permissions.BasePermission):
    """
    Solo Admin o SuperAdmin pueden asignar evaluaciones
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.rol in ['administrador', 'superadmin']
        )


class EsPropietarioOAdmin(permissions.BasePermission):
    """
    El usuario puede ver/editar su propia asignación,
    o ser Admin/SuperAdmin para ver/editar cualquiera
    """
    
    def has_object_permission(self, request, view, obj):
        # SuperAdmin puede todo
        if request.user.rol == 'superadmin':
            return True
        
        # Admin puede gestionar asignaciones de su empresa
        if request.user.rol == 'administrador':
            return obj.empresa == request.user.empresa
        
        # Usuario normal solo puede ver/editar las suyas
        return obj.usuario_asignado == request.user