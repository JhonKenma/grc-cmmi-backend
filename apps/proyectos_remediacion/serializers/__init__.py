# apps/proyectos_remediacion/serializers/__init__.py

from .item_serializers import (
    ItemProyectoListSerializer,
    ItemProyectoDetailSerializer,
    ItemProyectoCreateUpdateSerializer,
)

from .proyecto_serializers import (
    ProyectoCierreBrechaListSerializer,
    ProyectoCierreBrechaDetailSerializer,
    ProyectoCierreBrechaCreateSerializer,
    ProyectoCierreBrechaUpdateSerializer,
    ProyectoSimpleSerializer,
)

from .aprobacion_serializers import (
    AprobacionGAPListSerializer,
    AprobacionGAPDetailSerializer,
    SolicitarAprobacionSerializer,
    ResponderAprobacionSerializer,
)

__all__ = [
    # Items
    'ItemProyectoListSerializer',
    'ItemProyectoDetailSerializer',
    'ItemProyectoCreateUpdateSerializer',
    # Proyectos
    'ProyectoCierreBrechaListSerializer',
    'ProyectoCierreBrechaDetailSerializer',
    'ProyectoCierreBrechaCreateSerializer',
    'ProyectoCierreBrechaUpdateSerializer',
    'ProyectoSimpleSerializer',
    # Aprobaciones
    'AprobacionGAPListSerializer',
    'AprobacionGAPDetailSerializer',
    'SolicitarAprobacionSerializer',
    'ResponderAprobacionSerializer',
]