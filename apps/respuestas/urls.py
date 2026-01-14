# apps/respuestas/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TipoDocumentoViewSet,
    RespuestaViewSet,
    EvidenciaViewSet,
    HistorialRespuestaViewSet,
    CalculoNivelViewSet,
    #IniciativaViewSet,
)

# Crear el router
router = DefaultRouter()

# Registrar los ViewSets
router.register(r'tipos-documento', TipoDocumentoViewSet, basename='tipo-documento')
router.register(r'respuestas', RespuestaViewSet, basename='respuesta')
router.register(r'evidencias', EvidenciaViewSet, basename='evidencia')
router.register(r'historial-respuestas', HistorialRespuestaViewSet, basename='historial-respuesta')
router.register(r'calculos-nivel', CalculoNivelViewSet, basename='calculo-nivel')
#router.register(r'iniciativas', IniciativaViewSet, basename='iniciativa')

# URLs
urlpatterns = [
    path('', include(router.urls)),
]