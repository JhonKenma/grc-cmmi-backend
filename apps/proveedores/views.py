# apps/proveedores/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.core.permissions import EsAdminOSuperAdmin
from .models import Proveedor
from .serializers import (
    ProveedorSerializer,
    ProveedorCreateSerializer,
    ProveedorUpdateSerializer
)

class ProveedorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de proveedores
    - Superadmin: Ve TODOS los proveedores (globales + de empresas)
    - Administrador: Solo ve proveedores de SU empresa
    """
    permission_classes = [IsAuthenticated, EsAdminOSuperAdmin]
    
    def get_queryset(self):
        """
        ⭐ CORREGIDO: Filtrar proveedores según el rol
        """
        user = self.request.user
        
        # Superadmin ve TODO (proveedores globales + de empresas)
        if user.rol == 'superadmin':
            return Proveedor.objects.all()
        
        # Administrador solo ve proveedores de SU empresa
        if user.rol == 'administrador':
            if not user.empresa:
                return Proveedor.objects.none()
            return Proveedor.objects.filter(empresa=user.empresa)
        
        # Otros roles no tienen acceso
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
    
    @action(detail=False, methods=['get'])
    def activos(self, request):
        """
        GET /api/proveedores/activos/
        ⭐ Retorna proveedores activos según el rol del usuario
        """
        proveedores = self.get_queryset().filter(activo=True)
        
        # Usar paginación (recomendado)
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Sin paginación
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def inactivos(self, request):
        """
        GET /api/proveedores/inactivos/
        ⭐ Retorna proveedores inactivos según el rol del usuario
        """
        proveedores = self.get_queryset().filter(activo=False)
        
        # Usar paginación (recomendado)
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Sin paginación
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)
    
    # ⭐ NUEVO: Endpoint para ver proveedores globales (solo superadmin)
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
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
        
        proveedores = Proveedor.objects.filter(empresa__isnull=True)
        
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)