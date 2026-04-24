# apps/riesgos/views/__init__.py

from .riesgo import CategoriaRiesgoViewSet, RiesgoViewSet
from .tratamiento import (
    PlanTratamientoViewSet,
    KRIViewSet,
    RegistroMonitoreoViewSet,
)

__all__ = [
    'CategoriaRiesgoViewSet',
    'RiesgoViewSet',
    'PlanTratamientoViewSet',
    'KRIViewSet',
    'RegistroMonitoreoViewSet',
]