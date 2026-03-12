# apps/asignaciones_iq/urls.py
"""
URLs para Asignaciones de Evaluaciones Inteligentes
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AsignacionEvaluacionIQViewSet, RespuestaEvaluacionIQViewSet, EvidenciaIQViewSet

router = DefaultRouter()
router.register(r'asignaciones-iq', AsignacionEvaluacionIQViewSet, basename='asignacion-evaluacion-iq')
router.register(r'respuestas-iq', RespuestaEvaluacionIQViewSet, basename='respuesta-evaluacion-iq')
router.register(r'evidencias-iq', EvidenciaIQViewSet, basename='evidencia-iq')

urlpatterns = [
    path('', include(router.urls)),
]