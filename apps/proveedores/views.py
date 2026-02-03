# apps/proveedores/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.core.permissions import EsAdminOSuperAdmin
from .models import Proveedor, TipoProveedor, ClasificacionProveedor
from .serializers import (
    ProveedorSerializer,
    ProveedorCreateSerializer,
    ProveedorUpdateSerializer,
    TipoProveedorSerializer,
    ClasificacionProveedorSerializer,
)


# ============================================================
# VIEWSETS PARA CATÁLOGOS
# ============================================================

class TipoProveedorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para tipos de proveedor
    GET /api/tipos-proveedor/ - Listar todos los tipos activos
    GET /api/tipos-proveedor/{id}/ - Ver detalle de un tipo
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TipoProveedorSerializer
    queryset = TipoProveedor.objects.filter(activo=True)


class ClasificacionProveedorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para clasificaciones de proveedor
    GET /api/clasificaciones-proveedor/ - Listar todas las clasificaciones activas
    GET /api/clasificaciones-proveedor/{id}/ - Ver detalle de una clasificación
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ClasificacionProveedorSerializer
    queryset = ClasificacionProveedor.objects.filter(activo=True)


# ============================================================
# VIEWSET PARA PROVEEDORES
# ============================================================

class ProveedorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de proveedores
    - Superadmin: Ve TODOS los proveedores (globales + de empresas)
    - Administrador: Solo ve proveedores de SU empresa
    """
    permission_classes = [IsAuthenticated, EsAdminOSuperAdmin]
    
    def get_queryset(self):
        """Filtrar proveedores según el rol"""
        user = self.request.user
        
        if user.rol == 'superadmin':
            return Proveedor.objects.all().select_related(
                'empresa',
                'tipo_proveedor',
                'clasificacion',
                'creado_por'
            )
        
        if user.rol == 'administrador':
            if not user.empresa:
                return Proveedor.objects.none()
            return Proveedor.objects.filter(empresa=user.empresa).select_related(
                'empresa',
                'tipo_proveedor',
                'clasificacion',
                'creado_por'
            )
        
        return Proveedor.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProveedorCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProveedorUpdateSerializer
        return ProveedorSerializer
    
    def create(self, request, *args, **kwargs):
        """POST /api/proveedores/"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proveedor = serializer.save()
        
        response_serializer = ProveedorSerializer(proveedor)
        
        return Response({
            'success': True,
            'message': 'Proveedor creado exitosamente (desactivado por defecto)',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    # ============================================================
    # ACCIONES DE ESTADO
    # ============================================================
    
    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        """POST /api/proveedores/{id}/activar/"""
        proveedor = self.get_object()
        proveedor.activar()
        
        serializer = ProveedorSerializer(proveedor)
        
        return Response({
            'success': True,
            'message': f'Proveedor "{proveedor.razon_social}" activado',
            'data': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        """POST /api/proveedores/{id}/desactivar/"""
        proveedor = self.get_object()
        proveedor.desactivar()
        
        serializer = ProveedorSerializer(proveedor)
        
        return Response({
            'success': True,
            'message': f'Proveedor "{proveedor.razon_social}" desactivado',
            'data': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def suspender(self, request, pk=None):
        """POST /api/proveedores/{id}/suspender/"""
        proveedor = self.get_object()
        proveedor.suspender()
        
        serializer = ProveedorSerializer(proveedor)
        
        return Response({
            'success': True,
            'message': f'Proveedor "{proveedor.razon_social}" suspendido',
            'data': serializer.data
        })
    
    # ============================================================
    # FILTROS Y LISTADOS
    # ============================================================
    
    @action(detail=False, methods=['get'])
    def activos(self, request):
        """GET /api/proveedores/activos/"""
        proveedores = self.get_queryset().filter(activo=True)
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def inactivos(self, request):
        """GET /api/proveedores/inactivos/"""
        proveedores = self.get_queryset().filter(activo=False)
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def globales(self, request):
        """
        GET /api/proveedores/globales/
        Solo superadmin puede ver proveedores globales
        """
        if request.user.rol != 'superadmin':
            return Response({
                'success': False,
                'message': 'Solo superadmin puede ver proveedores globales'
            }, status=status.HTTP_403_FORBIDDEN)
        
        proveedores = Proveedor.objects.filter(empresa__isnull=True).select_related(
            'tipo_proveedor',
            'clasificacion',
            'creado_por'
        )
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def por_tipo(self, request):
        """
        GET /api/proveedores/por-tipo/?tipo_id={uuid}
        Filtrar proveedores por tipo
        """
        tipo_id = request.query_params.get('tipo_id')
        
        if not tipo_id:
            return Response({
                'success': False,
                'message': 'Debes proporcionar tipo_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        proveedores = self.get_queryset().filter(tipo_proveedor_id=tipo_id)
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def por_clasificacion(self, request):
        """
        GET /api/proveedores/por-clasificacion/?clasificacion_id={uuid}
        Filtrar proveedores por clasificación
        """
        clasificacion_id = request.query_params.get('clasificacion_id')
        
        if not clasificacion_id:
            return Response({
                'success': False,
                'message': 'Debes proporcionar clasificacion_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        proveedores = self.get_queryset().filter(clasificacion_id=clasificacion_id)
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def estrategicos(self, request):
        """
        GET /api/proveedores/estrategicos/
        Listar proveedores estratégicos
        """
        proveedores = self.get_queryset().filter(proveedor_estrategico=True)
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def por_nivel_riesgo(self, request):
        """
        GET /api/proveedores/por-nivel-riesgo/?nivel={alto|medio|bajo}
        Filtrar proveedores por nivel de riesgo
        """
        nivel = request.query_params.get('nivel')
        
        if nivel not in ['alto', 'medio', 'bajo']:
            return Response({
                'success': False,
                'message': 'El nivel debe ser: alto, medio o bajo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        proveedores = self.get_queryset().filter(nivel_riesgo=nivel)
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)