# apps/riesgos/models/__init__.py

from .categoria import CategoriaRiesgo
from .riesgo import Riesgo
from .tratamiento import PlanTratamiento
from .monitoreo import KRI, RegistroMonitoreo

__all__ = [
    'CategoriaRiesgo',
    'Riesgo',
    'PlanTratamiento',
    'KRI',
    'RegistroMonitoreo',
]