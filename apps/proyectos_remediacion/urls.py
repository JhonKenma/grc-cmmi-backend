# apps/proyectos_remediacion/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProyectoCierreBrechaViewSet, 
    ItemProyectoViewSet  # ⭐ 1. Asegúrate de importar el ViewSet de ítems
)

router = DefaultRouter()
router.register(r'proyectos-remediacion', ProyectoCierreBrechaViewSet, basename='proyectos-remediacion')

# ⭐ 2. Registra la ruta que el Frontend está buscando
router.register(r'items-proyecto', ItemProyectoViewSet, basename='items-proyecto')

urlpatterns = [
    path('', include(router.urls)),
]