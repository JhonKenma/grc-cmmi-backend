# apps/proveedores/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProveedorViewSet,
    TipoProveedorViewSet,
    ClasificacionProveedorViewSet,
)

router = DefaultRouter()
router.register(r'proveedores', ProveedorViewSet, basename='proveedor')
router.register(r'tipos-proveedor', TipoProveedorViewSet, basename='tipo-proveedor')
router.register(r'clasificaciones-proveedor', ClasificacionProveedorViewSet, basename='clasificacion-proveedor')

urlpatterns = [
    path('', include(router.urls)),
]