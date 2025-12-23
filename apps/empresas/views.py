# apps/empresas/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Empresa
from .serializers import EmpresaSerializer, EmpresaListSerializer
from apps.core.permissions import EsAdminOSuperAdmin, EsSuperAdmin
from apps.core.mixins import ResponseMixin

class EmpresaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de empresas
    
    PERMISOS:
    - SuperAdmin: CRUD completo de todas las empresas
    - Administrador: Solo puede ver su propia empresa (no crear/editar/eliminar)
    - Otros: Sin acceso
    """
    queryset = Empresa.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmpresaListSerializer
        return EmpresaSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # SuperAdmin ve todas las empresas
        if user.rol == 'superadmin':
            return Empresa.objects.all()
        
        # Administrador solo ve su empresa
        if user.rol == 'administrador' and user.empresa:
            return Empresa.objects.filter(id=user.empresa_id)
        
        # Otros roles no tienen acceso
        return Empresa.objects.none()
    
    def get_permissions(self):
        """Solo SuperAdmin puede crear/editar/eliminar empresas"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'cambiar_estado']:
            return [IsAuthenticated(), EsSuperAdmin()]
        
        # Ver empresas: SuperAdmin o Administrador
        if self.action in ['list', 'retrieve', 'mi_empresa', 'estadisticas']:
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        
        return [IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        """
        Crear empresa
        POST /api/empresas/
        Solo SuperAdmin
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return self.success_response(
            data=serializer.data,
            message='Empresa creada exitosamente',
            status_code=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """
        Actualizar empresa
        PUT/PATCH /api/empresas/{id}/
        Solo SuperAdmin
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return self.success_response(
            data=serializer.data,
            message='Empresa actualizada exitosamente'
        )
    
    def destroy(self, request, *args, **kwargs):
        """
        Eliminar empresa
        DELETE /api/empresas/{id}/
        Solo SuperAdmin
        """
        instance = self.get_object()
        
        # Verificar que no tenga usuarios activos
        if instance.usuarios.filter(activo=True).exists():
            return self.error_response(
                message='No se puede eliminar una empresa con usuarios activos',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_destroy(instance)
        return self.success_response(message='Empresa eliminada exitosamente')
    
    @action(detail=False, methods=['get'])
    def mi_empresa(self, request):
        """
        Obtener información de la empresa del usuario actual
        GET /api/empresas/mi_empresa/
        """
        if request.user.rol == 'superadmin':
            return self.error_response(
                message='Super administradores no tienen empresa asignada',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.user.empresa:
            return self.error_response(
                message='No tienes una empresa asignada',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(request.user.empresa)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """
        Activar/desactivar empresa
        POST /api/empresas/{id}/cambiar_estado/
        Solo SuperAdmin
        """
        empresa = self.get_object()
        empresa.activo = not empresa.activo
        empresa.save()
        
        return self.success_response(
            data={'activo': empresa.activo},
            message=f'Empresa {"activada" if empresa.activo else "desactivada"} correctamente'
        )
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas generales de empresas
        GET /api/empresas/estadisticas/
        Solo SuperAdmin
        """
        user = request.user
        
        if user.rol != 'superadmin':
            return self.error_response(
                message='Solo super administradores pueden ver estadísticas globales',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        total_empresas = Empresa.objects.count()
        empresas_activas = Empresa.objects.filter(activo=True).count()
        
        from apps.usuarios.models import Usuario
        total_usuarios = Usuario.objects.exclude(rol='superadmin').count()
        
        return Response({
            'total_empresas': total_empresas,
            'empresas_activas': empresas_activas,
            'empresas_inactivas': total_empresas - empresas_activas,
            'total_usuarios': total_usuarios,
        })