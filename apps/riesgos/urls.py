# apps/riesgos/urls.py

from rest_framework.routers import DefaultRouter
from .views import (
    CategoriaRiesgoViewSet,
    RiesgoViewSet,
    PlanTratamientoViewSet,
    KRIViewSet,
    RegistroMonitoreoViewSet,
)

router = DefaultRouter()
router.register(r'categorias',  CategoriaRiesgoViewSet,  basename='riesgo-categorias')
router.register(r'riesgos',     RiesgoViewSet,            basename='riesgos')
router.register(r'planes',      PlanTratamientoViewSet,   basename='riesgo-planes')
router.register(r'kris',        KRIViewSet,               basename='riesgo-kris')
router.register(r'monitoreo',   RegistroMonitoreoViewSet, basename='riesgo-monitoreo')

urlpatterns = router.urls