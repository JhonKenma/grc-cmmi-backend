# apps/evaluaciones/urls.py
"""
URLs para Sistema de Evaluaciones Inteligentes
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmpresaFrameworkViewSet,
    FrameworkViewSet,
    PreguntaEvaluacionViewSet,
    EvaluacionViewSet,
    RespuestaEvaluacionViewSet
)

app_name = 'evaluaciones'

router = DefaultRouter()
router.register(r'frameworks', FrameworkViewSet, basename='framework')
router.register(r'preguntas', PreguntaEvaluacionViewSet, basename='pregunta')
router.register(r'evaluaciones', EvaluacionViewSet, basename='evaluacion')
router.register(r'respuestas', RespuestaEvaluacionViewSet, basename='respuesta')
router.register(r'empresa-frameworks', EmpresaFrameworkViewSet, basename='empresa-frameworks')

urlpatterns = [
    path('', include(router.urls)),
]