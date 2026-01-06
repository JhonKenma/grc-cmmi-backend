# apps/reportes/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReporteViewSet

router = DefaultRouter()
router.register(r'reportes', ReporteViewSet, basename='reporte')

urlpatterns = [
    path('', include(router.urls)),
]