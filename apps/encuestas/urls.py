# apps/encuestas/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EncuestaViewSet,
    DimensionViewSet,
    PreguntaViewSet,
    NivelReferenciaViewSet,  # ⭐ AGREGAR ESTE
    ConfigNivelDeseadoViewSet
)

router = DefaultRouter()

router.register(r'encuestas', EncuestaViewSet, basename='encuesta')
router.register(r'dimensiones', DimensionViewSet, basename='dimension')
router.register(r'preguntas', PreguntaViewSet, basename='pregunta')
router.register(r'niveles-referencia', NivelReferenciaViewSet, basename='nivel-referencia')  # ⭐ AGREGAR ESTE
router.register(r'config-niveles', ConfigNivelDeseadoViewSet, basename='config-nivel')

urlpatterns = [
    path('', include(router.urls)),
]