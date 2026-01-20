# apps/proyectos_remediacion/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProyectoCierreBrechaViewSet

router = DefaultRouter()
router.register(r'proyectos-remediacion', ProyectoCierreBrechaViewSet, basename='proyectos-remediacion')

urlpatterns = [
    path('', include(router.urls)),
]