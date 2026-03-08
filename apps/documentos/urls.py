from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DocumentoViewSet, 
    ProcesoViewSet, 
    NormaViewSet, 
    TipoDocumentoViewSet 
)

router = DefaultRouter()

# Catálogos (Para Tipos de Documento ahora tendrás CRUD completo)
router.register(r'tipos', TipoDocumentoViewSet, basename='tipo-documento') 
router.register(r'procesos', ProcesoViewSet, basename='proceso')
router.register(r'normas', NormaViewSet, basename='norma')

# Endpoint principal
router.register(r'documentos', DocumentoViewSet, basename='documento')

urlpatterns = [
    path('', include(router.urls)),
]