# apps/notificaciones/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificacionViewSet, PlantillaNotificacionViewSet

# ⭐ Router para ViewSets
router = DefaultRouter()
router.register(r'notificaciones', NotificacionViewSet, basename='notificacion')
router.register(r'plantillas-notificacion', PlantillaNotificacionViewSet, basename='plantilla-notificacion')

urlpatterns = [
    path('', include(router.urls)),
]