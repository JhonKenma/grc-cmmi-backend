# apps/proveedores/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.core.permissions import EsAdminOSuperAdmin  # ← TU PERMISO EXISTENTE
from .models import Proveedor
from .serializers import (
    ProveedorSerializer,
    ProveedorCreateSerializer,
    ProveedorUpdateSerializer
)

class ProveedorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de proveedores
    Solo accesible por superadmin y administradores
    """
    permission_classes = [IsAuthenticated, EsAdminOSuperAdmin]  # ← USANDO TU PERMISO
    
    def get_queryset(self):
        user = self.request.user
        
        # Superadmin y Admin pueden ver todos
        if user.rol in ['superadmin', 'administrador']:
            return Proveedor.objects.all()
        
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
        """GET /api/proveedores/activos/"""
        proveedores = self.get_queryset().filter(activo=True)
        
        # ⭐ OPCIÓN 1: Usar el paginador (recomendado)
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # ⭐ OPCIÓN 2: Sin paginación (si prefieres)
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)  # ← Retorna array directo

    @action(detail=False, methods=['get'])
    def inactivos(self, request):
        """GET /api/proveedores/inactivos/"""
        proveedores = self.get_queryset().filter(activo=False)
        
        # ⭐ OPCIÓN 1: Usar el paginador (recomendado)
        page = self.paginate_queryset(proveedores)
        if page is not None:
            serializer = ProveedorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # ⭐ OPCIÓN 2: Sin paginación
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data)  # ← Retorna array directo