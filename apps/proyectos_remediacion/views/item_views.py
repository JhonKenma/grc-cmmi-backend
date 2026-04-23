# apps/proyectos_remediacion/views/item_views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from apps.proyectos_remediacion.models import ItemProyecto
from apps.proyectos_remediacion.serializers import (
    ItemProyectoListSerializer,
    ItemProyectoDetailSerializer,
    ItemProyectoCreateUpdateSerializer,
)
from apps.core.mixins import ResponseMixin


class ItemProyectoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestionar ítems directamente.

    ENDPOINTS:
    - GET    /api/items-proyecto/        → Listar ítems
    - GET    /api/items-proyecto/{id}/   → Detalle de ítem
    - POST   /api/items-proyecto/        → Crear ítem
    - PATCH  /api/items-proyecto/{id}/   → Actualizar ítem
    - DELETE /api/items-proyecto/{id}/   → Eliminar ítem
    """

    permission_classes   = [IsAuthenticated]
    http_method_names    = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.action == 'list':
            return ItemProyectoListSerializer
        elif self.action == 'retrieve':
            return ItemProyectoDetailSerializer
        return ItemProyectoCreateUpdateSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = ItemProyecto.objects.select_related(
            'proyecto',
            'proveedor',
            'responsable_ejecucion',
            'item_dependencia',
        ).filter(activo=True)

        # ─── Filtro por rol ───────────────────────────────────────────────────
        if user.rol == 'superadmin':
            pass
        elif user.rol == 'administrador':
            queryset = queryset.filter(proyecto__empresa=user.empresa) if user.empresa else queryset.none()
        else:
            queryset = queryset.filter(
                Q(proyecto__dueno_proyecto=user) |
                Q(responsable_ejecucion=user)
            )

        # ─── Filtros opcionales ───────────────────────────────────────────────
        proyecto_id = self.request.query_params.get('proyecto')
        if proyecto_id:
            queryset = queryset.filter(proyecto_id=proyecto_id)

        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)

        return queryset.order_by('proyecto', 'numero_item')