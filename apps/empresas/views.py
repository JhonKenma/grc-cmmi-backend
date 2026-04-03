# apps/empresas/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Empresa, PlanEmpresa 
from .serializers import EmpresaSerializer, EmpresaListSerializer, PlanEmpresaSerializer  
from apps.core.permissions import EsAdminOSuperAdmin, EsSuperAdmin
from apps.core.mixins import ResponseMixin
from drf_spectacular.utils import extend_schema

@extend_schema(tags=['2. Gestión de Empresas'])
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
        
    @action(detail=True, methods=['post'])
    def asignar_plan(self, request, pk=None):
        """
        POST /api/empresas/{id}/asignar_plan/
        Body:
        {
            "tipo": "demo",
            "max_usuarios": 3,
            "max_administradores": 1,
            "max_auditores": 1,
            "fecha_expiracion": "2026-05-30",  ← fecha ISO, el backend calcula el resto
            "sin_expiracion": false
        }
        """
        empresa = self.get_object()

        tipo             = request.data.get('tipo', 'demo')
        max_usuarios     = request.data.get('max_usuarios', 3)
        max_admins       = request.data.get('max_administradores', 1)
        max_auditores    = request.data.get('max_auditores', 1)
        sin_expiracion   = request.data.get('sin_expiracion', False)
        fecha_exp_str    = request.data.get('fecha_expiracion')  # "YYYY-MM-DD"

        plan, creado = PlanEmpresa.objects.get_or_create(empresa=empresa)
        plan.tipo                = tipo
        plan.max_usuarios        = max_usuarios
        plan.max_administradores = max_admins
        plan.max_auditores       = max_auditores

        if sin_expiracion:
            plan.fecha_expiracion = None
        elif fecha_exp_str:
            from datetime import datetime, timezone as dt_timezone
            try:
                fecha_naive = datetime.strptime(fecha_exp_str, '%Y-%m-%d')
                fecha_naive = fecha_naive.replace(hour=23, minute=59, second=59)
                plan.fecha_expiracion = fecha_naive.replace(tzinfo=dt_timezone.utc)
            except ValueError:
                return self.error_response(
                    message='Formato de fecha inválido. Use YYYY-MM-DD',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        else:
            return self.error_response(
                message='Debe proporcionar fecha_expiracion o sin_expiracion=true',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        plan.save()

        return self.success_response(
            data=PlanEmpresaSerializer(plan).data,
            message=f'Plan {"creado" if creado else "actualizado"} exitosamente'
        )