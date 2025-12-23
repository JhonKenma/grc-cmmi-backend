# apps/usuarios/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers as drf_serializers
from django.contrib.auth import get_user_model
from .models import Usuario
from .serializers import (
    UsuarioSerializer,
    UsuarioListSerializer,
    UsuarioCreateSerializer,
    CambiarPasswordSerializer
)
from apps.core.permissions import EsAdminOSuperAdmin, EsAuditor, EsSuperAdmin
from apps.core.mixins import ResponseMixin

Usuario = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer personalizado para login con EMAIL"""
    username_field = Usuario.USERNAME_FIELD
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Verificar que el usuario esté activo
        if not self.user.activo:
            raise drf_serializers.ValidationError('Esta cuenta ha sido desactivada')
        
        # Información del usuario
        data['usuario'] = {
            'id': self.user.id,
            'email': self.user.email,
            'username': self.user.username,
            'nombre_completo': self.user.nombre_completo,
            'rol': self.user.rol,
            'empresa_id': self.user.empresa_id if self.user.empresa else None,
            'empresa_nombre': self.user.empresa.nombre if self.user.empresa else None,
            'avatar': self.user.avatar.url if self.user.avatar else None,
            'es_superadmin': self.user.es_superadmin,
        }
        
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    """Vista personalizada para login con EMAIL"""
    serializer_class = CustomTokenObtainPairSerializer

class UsuarioViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para CRUD de usuarios con control de acceso
    
    JERARQUÍA DE PERMISOS:
    - SuperAdmin: Acceso total a todos los usuarios de todas las empresas
    - Administrador: Acceso solo a usuarios de su empresa
    - Usuario: Solo puede ver su propio perfil
    - Auditor: Puede ver usuarios de su empresa (solo lectura)
    """
    queryset = Usuario.objects.select_related('empresa').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UsuarioListSerializer
        if self.action == 'create':
            return UsuarioCreateSerializer
        if self.action == 'cambiar_password':
            return CambiarPasswordSerializer
        return UsuarioSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # SuperAdmin ve TODOS los usuarios
        if user.rol == 'superadmin':
            return Usuario.objects.select_related('empresa').all()
        
        # Usuarios sin empresa no deberían llegar aquí
        if not user.empresa:
            return Usuario.objects.none()
        
        # Administrador y Auditor ven solo de su empresa
        if user.rol in ['administrador', 'auditor']:
            return Usuario.objects.filter(empresa=user.empresa).select_related('empresa')
        
        # Usuario normal solo se ve a sí mismo
        return Usuario.objects.filter(id=user.id).select_related('empresa')
    
    def get_permissions(self):
        """Permisos específicos por acción"""
        # Acciones de escritura: SuperAdmin o Administradores
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'cambiar_estado']:
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        
        # Listado y detalle: Admin, Auditor o SuperAdmin
        if self.action in ['list', 'retrieve', 'por_rol', 'estadisticas']:
            return [IsAuthenticated(), EsAuditor()]
        
        # Acciones personales: Cualquier usuario autenticado
        if self.action in ['me', 'cambiar_password']:
            return [IsAuthenticated()]
        
        return [IsAuthenticated()]
    
    def retrieve(self, request, *args, **kwargs):
        """Obtener detalle de un usuario"""
        instance = self.get_object()
        user = request.user
        
        # Usuario normal solo puede ver su propio perfil
        if user.rol == 'usuario' and instance.id != user.id:
            return self.error_response(
                message='No tienes permiso para ver este usuario',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Crear usuario"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Si admin no especifica empresa, asignar la suya
        if 'empresa' not in serializer.validated_data:
            if request.user.rol == 'administrador':
                serializer.validated_data['empresa'] = request.user.empresa
        
        self.perform_create(serializer)
        
        return self.success_response(
            data=UsuarioSerializer(serializer.instance, context={'request': request}).data,
            message='Usuario creado exitosamente',
            status_code=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Actualizar usuario"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Validar permisos adicionales
        user = request.user
        
        # Administrador no puede editar superadmins
        if user.rol == 'administrador' and instance.rol == 'superadmin':
            return self.error_response(
                message='No tienes permiso para editar super administradores',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return self.success_response(
            data=serializer.data,
            message='Usuario actualizado exitosamente'
        )
    
    def destroy(self, request, *args, **kwargs):
        """Eliminar usuario"""
        instance = self.get_object()
        user = request.user
        
        # No permitir eliminarse a sí mismo
        if instance.id == user.id:
            return self.error_response(
                message='No puedes eliminar tu propia cuenta',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Administrador no puede eliminar superadmins
        if user.rol == 'administrador' and instance.rol == 'superadmin':
            return self.error_response(
                message='No tienes permiso para eliminar super administradores',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        self.perform_destroy(instance)
        return self.success_response(message='Usuario eliminado exitosamente')
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Obtener información del usuario actual
        GET /api/auth/usuarios/me/
        """
        serializer = UsuarioSerializer(request.user, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """
        Activar/desactivar usuario
        POST /api/auth/usuarios/{id}/cambiar_estado/
        """
        usuario = self.get_object()
        user = request.user
        
        # No permitir desactivarse a sí mismo
        if usuario.id == user.id:
            return self.error_response(
                message='No puedes cambiar tu propio estado',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Administrador no puede cambiar estado de superadmins
        if user.rol == 'administrador' and usuario.rol == 'superadmin':
            return self.error_response(
                message='No tienes permiso para cambiar el estado de super administradores',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        usuario.activo = not usuario.activo
        usuario.save()
        
        return self.success_response(
            data={'activo': usuario.activo},
            message=f'Usuario {"activado" if usuario.activo else "desactivado"} correctamente'
        )
    
    @action(detail=False, methods=['post'])
    def cambiar_password(self, request):
        """
        Cambiar contraseña del usuario actual
        POST /api/auth/usuarios/cambiar_password/
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        request.user.set_password(serializer.validated_data['password_nuevo'])
        request.user.save()
        
        return self.success_response(message='Contraseña cambiada exitosamente')
    
    @action(detail=False, methods=['get'])
    def por_rol(self, request):
        """
        Listar usuarios filtrados por rol
        GET /api/auth/usuarios/por_rol/?rol=usuario
        """
        rol = request.query_params.get('rol')
        
        if not rol:
            return self.error_response(message='Parámetro "rol" es requerido')
        
        queryset = self.filter_queryset(self.get_queryset()).filter(rol=rol)
        serializer = UsuarioListSerializer(queryset, many=True)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas de usuarios
        GET /api/auth/usuarios/estadisticas/
        """
        user = request.user
        
        if user.rol == 'superadmin':
            # SuperAdmin ve estadísticas globales
            queryset = Usuario.objects.all()
        elif user.empresa:
            # Otros ven solo de su empresa
            queryset = Usuario.objects.filter(empresa=user.empresa)
        else:
            queryset = Usuario.objects.none()
        
        total = queryset.count()
        activos = queryset.filter(activo=True).count()
        por_rol = {}
        
        for rol_code, rol_name in Usuario.ROLES:
            por_rol[rol_code] = {
                'nombre': rol_name,
                'cantidad': queryset.filter(rol=rol_code).count()
            }
        
        return Response({
            'total_usuarios': total,
            'usuarios_activos': activos,
            'usuarios_inactivos': total - activos,
            'por_rol': por_rol
        })