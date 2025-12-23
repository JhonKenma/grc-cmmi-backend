# apps/core/permissions.py
from rest_framework import permissions


class EsSuperAdmin(permissions.BasePermission):
    """
    Permiso para verificar que el usuario sea SuperAdmin
    Solo SuperAdmin puede realizar la acción
    """
    message = 'Solo los super administradores pueden realizar esta acción.'
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'superadmin'


class EsAdministrador(permissions.BasePermission):
    """
    Permiso para verificar que el usuario sea Administrador (de empresa)
    Solo Administradores pueden realizar la acción
    """
    message = 'Solo los administradores pueden realizar esta acción.'
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'administrador'


class EsAdminOSuperAdmin(permissions.BasePermission):
    """
    Permiso para administradores o superadmin
    Ambos roles pueden realizar la acción
    """
    message = 'Solo administradores o super administradores pueden realizar esta acción.'
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in ['administrador', 'superadmin']


class EsAuditor(permissions.BasePermission):
    """
    Permiso para auditores, administradores y superadmin
    IMPORTANTE: Permite lectura para Auditor, Admin y SuperAdmin
    (Excluye solo a Usuario común)
    """
    message = 'No tienes permisos para acceder a este recurso.'
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # SuperAdmin y Administrador: Acceso total
        if request.user.rol in ['superadmin', 'administrador']:
            return True
        
        # Auditor: Solo lectura (GET, HEAD, OPTIONS)
        if request.user.rol == 'auditor':
            return request.method in permissions.SAFE_METHODS
        
        # Usuario común: Sin acceso
        return False


class EsAdminOSuperAdminOAuditor(permissions.BasePermission):
    """
    Solo SuperAdmin, Administrador o Auditor
    (Excluye a Usuario común del catálogo de encuestas)
    Usado para vistas que Usuario común NO debe ver
    """
    message = 'Solo administradores, super administradores y auditores tienen acceso al catálogo de encuestas.'
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # SuperAdmin y Administrador: Acceso total
        if request.user.rol in ['superadmin', 'administrador']:
            return True
        
        # Auditor: Solo lectura
        if request.user.rol == 'auditor':
            return request.method in permissions.SAFE_METHODS
        
        # Usuario común: Sin acceso
        return False


class EsUsuario(permissions.BasePermission):
    """
    Permiso para usuarios normales y roles superiores
    IMPORTANTE: No restringe por método, solo verifica autenticación
    """
    message = 'Necesitas ser un usuario activo para realizar esta acción.'
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in [
            'usuario', 'administrador', 'superadmin', 'auditor'
        ]


class MismaEmpresa(permissions.BasePermission):
    """
    Verifica que el usuario pertenezca a la misma empresa que el objeto
    SuperAdmin tiene acceso a todo
    Permiso a nivel de OBJETO (has_object_permission)
    """
    message = 'No tienes permiso para acceder a recursos de otra empresa.'
    
    def has_object_permission(self, request, view, obj):
        # SuperAdmin puede acceder a todo
        if request.user.rol == 'superadmin':
            return True
        
        # Usuario sin empresa no tiene acceso
        if not request.user.empresa:
            return False
        
        # Verificar que el objeto tenga empresa (prioridad)
        if hasattr(obj, 'empresa') and obj.empresa:
            return obj.empresa == request.user.empresa
        
        # Si el objeto tiene empresa_id
        if hasattr(obj, 'empresa_id') and obj.empresa_id:
            return obj.empresa_id == request.user.empresa_id
        
        # Si no tiene empresa, permitir acceso (objetos globales como encuestas plantilla)
        return True


class EsPropietarioOAdmin(permissions.BasePermission):
    """
    El usuario es el propietario del objeto o es administrador/superadmin
    Permiso a nivel de OBJETO (has_object_permission)
    """
    message = 'Solo el propietario o un administrador puede realizar esta acción.'
    
    def has_object_permission(self, request, view, obj):
        # SuperAdmin puede todo
        if request.user.rol == 'superadmin':
            return True
        
        # Administrador de la misma empresa puede todo
        if request.user.rol == 'administrador':
            if hasattr(obj, 'empresa') and obj.empresa:
                return obj.empresa == request.user.empresa
            if hasattr(obj, 'empresa_id') and obj.empresa_id:
                return obj.empresa_id == request.user.empresa_id
        
        # El usuario es el propietario del objeto
        if hasattr(obj, 'usuario') and obj.usuario:
            return obj.usuario == request.user
        
        if hasattr(obj, 'usuario_asignado') and obj.usuario_asignado:
            return obj.usuario_asignado == request.user
        
        if hasattr(obj, 'creado_por') and obj.creado_por:
            return obj.creado_por == request.user
        
        # Por defecto, denegar
        return False


class SoloLectura(permissions.BasePermission):
    """
    Permiso de solo lectura (GET, HEAD, OPTIONS)
    Útil para endpoints que todos pueden ver pero nadie editar
    """
    message = 'Este recurso es de solo lectura.'
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS