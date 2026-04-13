# apps/riesgos/views/tratamiento.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.core.mixins import ResponseMixin
from ..models import PlanTratamiento, KRI, RegistroMonitoreo
from ..serializers import (
    PlanTratamientoListSerializer,
    PlanTratamientoDetailSerializer,
    PlanTratamientoCreateSerializer,
    ActualizarAvancePlanSerializer,
    KRIListSerializer,
    KRICreateSerializer,
    RegistrarMedicionKRISerializer,
    RegistroMonitoreoSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# PLANES DE TRATAMIENTO
# ─────────────────────────────────────────────────────────────────────────────

class PlanTratamientoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    Endpoints:
      GET    /api/riesgos/planes/                       → Listar planes
      POST   /api/riesgos/planes/                       → Crear plan
      GET    /api/riesgos/planes/{id}/                  → Detalle
      PATCH  /api/riesgos/planes/{id}/actualizar_avance/ → Actualizar progreso
      POST   /api/riesgos/planes/{id}/aprobar/          → Admin aprueba el plan
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch']

    def get_serializer_class(self):
        if self.action == 'list':
            return PlanTratamientoListSerializer
        if self.action == 'create':
            return PlanTratamientoCreateSerializer
        if self.action == 'actualizar_avance':
            return ActualizarAvancePlanSerializer
        return PlanTratamientoDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = PlanTratamiento.objects.select_related(
            'riesgo', 'riesgo__empresa',
            'responsable_accion', 'aprobado_por'
        ).filter(activo=True)

        if user.rol == 'superadmin':
            pass
        elif user.rol in ['administrador', 'analista_riesgos', 'auditor']:
            qs = qs.filter(riesgo__empresa=user.empresa)
        else:
            # Dueño del riesgo o responsable del plan
            qs = qs.filter(
                responsable_accion=user
            ) | qs.filter(riesgo__dueno_riesgo=user)

        # Filtros
        riesgo_id = self.request.query_params.get('riesgo')
        if riesgo_id:
            qs = qs.filter(riesgo_id=riesgo_id)

        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)

        return qs.order_by('fecha_fin_plan')

    def create(self, request, *args, **kwargs):
        if request.user.rol not in ['administrador', 'analista_riesgos', 'superadmin']:
            return self.error_response(
                message='Solo administradores y analistas pueden crear planes.',
                status_code=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return self.success_response(
            data=PlanTratamientoDetailSerializer(plan).data,
            message='Plan de tratamiento creado exitosamente.',
            status_code=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['patch'], url_path='actualizar_avance')
    def actualizar_avance(self, request, pk=None):
        """
        PATCH /api/riesgos/planes/{id}/actualizar_avance/
        Actualiza el progreso del plan. Puede hacerlo el responsable o el admin.
        """
        plan = self.get_object()
        user = request.user

        es_responsable = plan.responsable_accion == user
        es_admin = user.rol in ['administrador', 'superadmin']

        if not es_responsable and not es_admin:
            return self.error_response(
                message='Solo el responsable o el administrador pueden actualizar el avance.',
                status_code=status.HTTP_403_FORBIDDEN
            )

        serializer = ActualizarAvancePlanSerializer(
            plan, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()

        return self.success_response(
            data=PlanTratamientoDetailSerializer(plan).data,
            message='Avance actualizado exitosamente.'
        )

    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        """El administrador aprueba el plan de tratamiento."""
        if request.user.rol not in ['administrador', 'superadmin']:
            return self.error_response(
                message='Solo administradores pueden aprobar planes.',
                status_code=status.HTTP_403_FORBIDDEN
            )

        plan = self.get_object()
        from django.utils import timezone
        plan.aprobado_por = request.user
        plan.fecha_aprobacion = timezone.now()
        plan.estado = 'en_curso'
        plan.save()

        return self.success_response(
            data=PlanTratamientoDetailSerializer(plan).data,
            message='Plan aprobado. Estado cambiado a En Curso.'
        )


# ─────────────────────────────────────────────────────────────────────────────
# KRIs
# ─────────────────────────────────────────────────────────────────────────────

class KRIViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    Endpoints:
      GET    /api/riesgos/kris/                      → Listar KRIs
      POST   /api/riesgos/kris/                      → Crear KRI
      GET    /api/riesgos/kris/{id}/                 → Detalle
      POST   /api/riesgos/kris/{id}/registrar_medicion/ → Nueva medición
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch']

    def get_serializer_class(self):
        if self.action == 'create':
            return KRICreateSerializer
        if self.action == 'registrar_medicion':
            return RegistrarMedicionKRISerializer
        return KRIListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = KRI.objects.select_related(
            'riesgo', 'riesgo__empresa', 'responsable_medicion'
        ).filter(activo=True)

        if user.rol == 'superadmin':
            pass
        elif user.rol in ['administrador', 'analista_riesgos', 'auditor']:
            qs = qs.filter(riesgo__empresa=user.empresa)
        else:
            qs = qs.filter(responsable_medicion=user)

        riesgo_id = self.request.query_params.get('riesgo')
        if riesgo_id:
            qs = qs.filter(riesgo_id=riesgo_id)

        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado_actual=estado)

        return qs

    def create(self, request, *args, **kwargs):
        if request.user.rol not in ['administrador', 'analista_riesgos', 'superadmin']:
            return self.error_response(
                message='Solo administradores y analistas pueden crear KRIs.',
                status_code=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        kri = serializer.save()
        return self.success_response(
            data=KRIListSerializer(kri).data,
            message='KRI creado exitosamente.',
            status_code=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], url_path='registrar_medicion')
    def registrar_medicion(self, request, pk=None):
        """
        POST /api/riesgos/kris/{id}/registrar_medicion/
        Registra una nueva medición y actualiza el estado del KRI.
        """
        kri = self.get_object()
        serializer = RegistrarMedicionKRISerializer(
            kri, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        kri, nuevo_estado = serializer.save()

        mensaje = f'Medición registrada. Estado KRI: {kri.get_estado_actual_display()}'
        if nuevo_estado in ['amarillo', 'rojo']:
            mensaje += ' ⚠️ Alerta activada.'

        return self.success_response(
            data=KRIListSerializer(kri).data,
            message=mensaje
        )


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRO DE MONITOREO
# ─────────────────────────────────────────────────────────────────────────────

class RegistroMonitoreoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    Endpoints:
      GET  /api/riesgos/monitoreo/           → Listar revisiones
      POST /api/riesgos/monitoreo/           → Registrar revisión
    """
    permission_classes = [IsAuthenticated]
    serializer_class = RegistroMonitoreoSerializer
    http_method_names = ['get', 'post']

    def get_queryset(self):
        user = self.request.user
        qs = RegistroMonitoreo.objects.select_related(
            'riesgo', 'riesgo__empresa', 'revisado_por'
        ).filter(activo=True)

        if user.rol == 'superadmin':
            pass
        elif user.rol in ['administrador', 'analista_riesgos', 'auditor']:
            qs = qs.filter(riesgo__empresa=user.empresa)
        else:
            qs = qs.filter(revisado_por=user)

        riesgo_id = self.request.query_params.get('riesgo')
        if riesgo_id:
            qs = qs.filter(riesgo_id=riesgo_id)

        return qs.order_by('-fecha_revision')

    def create(self, request, *args, **kwargs):
        if request.user.rol not in ['administrador', 'analista_riesgos', 'auditor', 'superadmin']:
            return self.error_response(
                message='No tienes permisos para registrar monitoreo.',
                status_code=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        registro = serializer.save()
        return self.success_response(
            data=RegistroMonitoreoSerializer(registro).data,
            message='Revisión de monitoreo registrada exitosamente.',
            status_code=status.HTTP_201_CREATED
        )