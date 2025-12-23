# apps/asignaciones/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AsignacionViewSet

router = DefaultRouter()
router.register(r'', AsignacionViewSet, basename='asignacion')  # ⭐ VACÍO

urlpatterns = [
    path('', include(router.urls)),
]