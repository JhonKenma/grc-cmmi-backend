# apps/riesgos/views/riesgo.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q

from apps.core.mixins import ResponseMixin
from ..models import Riesgo, CategoriaRiesgo
from ..serializers import (
    CategoriaRiesgoSerializer,
    CategoriaRiesgoListSerializer,
    RiesgoListSerializer,
    RiesgoDetailSerializer,
    RiesgoCreateSerializer,
    RiesgoUpdateSerializer,
    AprobarRiesgoSerializer,
)
from ..services import CalculoRiesgoService


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORÍAS
# ─────────────────────────────────────────────────────────────────────────────

class CategoriaRiesgoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    CRUD de categorías de riesgo.
    GET  /api/riesgos/categorias/         → Listar (globales + las de la empresa)
    POST /api/riesgos/categorias/         → Crear (admin: para su empresa)
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return CategoriaRiesgoListSerializer
        return CategoriaRiesgoSerializer

    def get_queryset(self):
        user = self.request.user
        # Mostrar categorías globales + las de la empresa del usuario
        if user.rol == 'superadmin':
            return CategoriaRiesgo.objects.filter(activo=True)
        return CategoriaRiesgo.objects.filter(
            Q(empresa=user.empresa) | Q(empresa__isnull=True),
            activo=True
        ).order_by('orden', 'nombre')

    def create(self, request, *args, **kwargs):
        if request.user.rol not in ['administrador', 'superadmin']:
            return self.error_response(
                message='Solo administradores pueden crear categorías.',
                status_code=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        categoria = serializer.save()
        return self.success_response(
            data=CategoriaRiesgoSerializer(categoria).data,
            message='Categoría creada exitosamente.',
            status_code=status.HTTP_201_CREATED
        )


# ─────────────────────────────────────────────────────────────────────────────
# RIESGOS
# ─────────────────────────────────────────────────────────────────────────────

class RiesgoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet principal de Riesgos.

    Endpoints:
      GET    /api/riesgos/                         → Listar
      POST   /api/riesgos/                         → Crear
      GET    /api/riesgos/{id}/                    → Detalle
      PATCH  /api/riesgos/{id}/                    → Actualizar
      POST   /api/riesgos/{id}/enviar_revision/    → Analista envía a Admin
      POST   /api/riesgos/{id}/aprobar/            → Admin aprueba
      POST   /api/riesgos/{id}/rechazar/           → Admin rechaza
      POST   /api/riesgos/{id}/cerrar/             → Cerrar riesgo
      GET    /api/riesgos/dashboard/               → Estadísticas generales
      GET    /api/riesgos/mapa_calor/              → Datos para el mapa de calor
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.action == 'list':
            return RiesgoListSerializer
        if self.action == 'create':
            return RiesgoCreateSerializer
        if self.action in ['update', 'partial_update']:
            return RiesgoUpdateSerializer
        if self.action == 'aprobar':
            return AprobarRiesgoSerializer
        return RiesgoDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Riesgo.objects.select_related(
            'categoria', 'empresa',
            'identificado_por', 'dueno_riesgo', 'aprobado_por'
        ).filter(activo=True)

        if user.rol == 'superadmin':
            pass
        elif user.rol in ['administrador', 'analista_riesgos', 'auditor']:
            qs = qs.filter(empresa=user.empresa)
        else:
            # Usuario normal: solo ve riesgos donde es dueño
            qs = qs.filter(dueno_riesgo=user)

        # Filtros opcionales via query params
        clasificacion = self.request.query_params.get('clasificacion')
        if clasificacion:
            qs = qs.filter(clasificacion=clasificacion)

        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)

        categoria = self.request.query_params.get('categoria')
        if categoria:
            qs = qs.filter(categoria_id=categoria)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(codigo__icontains=search) |
                Q(nombre__icontains=search) |
                Q(descripcion__icontains=search)
            )

        return qs.order_by('-nivel_riesgo', '-fecha_identificacion')

    def create(self, request, *args, **kwargs):
        if request.user.rol not in ['administrador', 'analista_riesgos', 'superadmin']:
            return self.error_response(
                message='Solo administradores y analistas pueden crear riesgos.',
                status_code=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        riesgo = serializer.save()
        return self.success_response(
            data=RiesgoDetailSerializer(riesgo).data,
            message='Riesgo creado exitosamente.',
            status_code=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        riesgo = self.get_object()

        # No editar riesgos cerrados o mitigados
        if riesgo.estado in ['cerrado', 'mitigado', 'aceptado']:
            return self.error_response(
                message=f'No se puede editar un riesgo en estado: {riesgo.get_estado_display()}',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(
            riesgo, data=request.data, partial=partial,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        riesgo = serializer.save()
        return self.success_response(
            data=RiesgoDetailSerializer(riesgo).data,
            message='Riesgo actualizado exitosamente.'
        )

    # ── Flujo de aprobación ────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='enviar_revision')
    def enviar_revision(self, request, pk=None):
        """El analista envía el riesgo al administrador para aprobación."""
        riesgo = self.get_object()

        if riesgo.estado != 'borrador':
            return self.error_response(
                message='Solo se pueden enviar a revisión riesgos en borrador.',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        riesgo.estado = 'en_revision'
        riesgo.save()

        return self.success_response(
            data=RiesgoDetailSerializer(riesgo).data,
            message='Riesgo enviado a revisión del administrador.'
        )

    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        """El administrador aprueba el riesgo."""
        if request.user.rol not in ['administrador', 'superadmin']:
            return self.error_response(
                message='Solo administradores pueden aprobar riesgos.',
                status_code=status.HTTP_403_FORBIDDEN
            )

        riesgo = self.get_object()
        serializer = AprobarRiesgoSerializer(
            riesgo, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        riesgo = serializer.save()

        return self.success_response(
            data=RiesgoDetailSerializer(riesgo).data,
            message='Riesgo aprobado exitosamente.'
        )

    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar(self, request, pk=None):
        """El administrador rechaza el riesgo y lo devuelve a borrador."""
        if request.user.rol not in ['administrador', 'superadmin']:
            return self.error_response(
                message='Solo administradores pueden rechazar riesgos.',
                status_code=status.HTTP_403_FORBIDDEN
            )

        riesgo = self.get_object()
        if riesgo.estado != 'en_revision':
            return self.error_response(
                message='Solo se pueden rechazar riesgos en revisión.',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        motivo = request.data.get('motivo', '')
        if not motivo:
            return self.error_response(
                message='Debes indicar el motivo del rechazo.',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        riesgo.estado = 'borrador'
        riesgo.notas += f'\n[Rechazado por {request.user.get_full_name()}] {motivo}'
        riesgo.save()

        return self.success_response(
            data=RiesgoDetailSerializer(riesgo).data,
            message='Riesgo rechazado. Volvió a borrador.'
        )

    @action(detail=True, methods=['post'], url_path='cerrar')
    def cerrar(self, request, pk=None):
        """Cierra un riesgo (ya no aplica o fue superado)."""
        if request.user.rol not in ['administrador', 'superadmin']:
            return self.error_response(
                message='Solo administradores pueden cerrar riesgos.',
                status_code=status.HTTP_403_FORBIDDEN
            )

        riesgo = self.get_object()
        motivo = request.data.get('motivo', '')
        riesgo.estado = 'cerrado'
        if motivo:
            riesgo.notas += f'\n[Cerrado] {motivo}'
        riesgo.save()

        return self.success_response(
            data=RiesgoDetailSerializer(riesgo).data,
            message='Riesgo cerrado exitosamente.'
        )

    # ── Dashboard ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """
        GET /api/riesgos/dashboard/
        Estadísticas generales de riesgos de la empresa.
        """
        qs = self.get_queryset()
        resumen = CalculoRiesgoService.calcular_resumen_empresa(qs)

        # Riesgos críticos que necesitan atención
        criticos_sin_plan = qs.filter(
            clasificacion='critico',
            estado='aprobado'
        ).values('id', 'codigo', 'nombre', 'nivel_riesgo', 'ale')[:5]

        # KRIs en alerta
        from ..models import KRI
        kris_alerta = KRI.objects.filter(
            riesgo__empresa=request.user.empresa,
            estado_actual__in=['amarillo', 'rojo'],
            activo=True
        ).select_related('riesgo').values(
            'id', 'codigo', 'nombre', 'estado_actual',
            'valor_actual', 'umbral_rojo', 'riesgo__nombre'
        )[:5]

        return self.success_response(data={
            'resumen': resumen,
            'criticos_sin_plan': list(criticos_sin_plan),
            'kris_en_alerta': list(kris_alerta),
        })

    @action(detail=False, methods=['get'], url_path='mapa_calor')
    def mapa_calor(self, request):
        """
        GET /api/riesgos/mapa_calor/
        Datos para renderizar el mapa de calor 5x5 en el frontend.
        """
        qs = self.get_queryset().filter(estado__in=['aprobado', 'en_tratamiento'])

        # Agrupar riesgos por celda de la matriz
        celdas = {}
        for riesgo in qs:
            clave = f"{riesgo.probabilidad}_{riesgo.impacto}"
            if clave not in celdas:
                celdas[clave] = []
            celdas[clave].append({
                'id': str(riesgo.id),
                'codigo': riesgo.codigo,
                'nombre': riesgo.nombre,
                'clasificacion': riesgo.clasificacion,
            })

        return self.success_response(data={
            'matriz': CalculoRiesgoService.get_matriz_completa(),
            'riesgos_por_celda': celdas,
        })