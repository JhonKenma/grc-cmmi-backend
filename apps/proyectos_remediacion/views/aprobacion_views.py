# apps/proyectos_remediacion/views/aprobacion_views.py

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from datetime import date

from apps.proyectos_remediacion.models import AprobacionGAP
from apps.proyectos_remediacion.serializers import (
    AprobacionGAPListSerializer,
    AprobacionGAPDetailSerializer,
    SolicitarAprobacionSerializer,
    ResponderAprobacionSerializer,
)
from apps.notificaciones.models import Notificacion
from apps.core.permissions import EsAdminOSuperAdmin


class AprobacionMixin:
    """
    Mixin con todos los endpoints de aprobación de GAP.
    Se mezcla en ProyectoCierreBrechaViewSet.
    """

    # ── Solicitar aprobación ──────────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def solicitar_aprobacion(self, request, pk=None):
        """
        Solicita la aprobación para cerrar el GAP del proyecto.
        POST /api/proyectos-remediacion/{id}/solicitar_aprobacion/
        """
        proyecto = self.get_object()
        user     = request.user

        # ─── Validaciones ────────────────────────────────────────────────────
        estados_validos = ['en_ejecucion', 'planificado', 'pendiente', 'en_progreso']
        if proyecto.estado not in estados_validos:
            return self.error_response(
                message=f'El proyecto está en estado "{proyecto.estado}". No puede solicitar aprobación en este estado.',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if proyecto.modo_presupuesto == 'por_items':
            if proyecto.total_items == 0:
                return self.error_response(
                    message='No puedes solicitar aprobación de un proyecto sin ítems de planificación.',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            items_pendientes = proyecto.items.filter(activo=True).exclude(estado='completado').count()
            if items_pendientes > 0:
                return self.error_response(
                    message=f'Aún hay {items_pendientes} ítem(s) pendiente(s) de completar',
                    status_code=status.HTTP_400_BAD_REQUEST
                )

        aprobacion_pendiente = AprobacionGAP.objects.filter(
            proyecto=proyecto,
            estado='pendiente',
            activo=True
        ).first()

        if aprobacion_pendiente:
            return self.error_response(
                message='Ya existe una solicitud de aprobación pendiente para este proyecto',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # ─── Determinar validador ─────────────────────────────────────────────
        validador = proyecto.validador_interno

        if not validador and proyecto.calculo_nivel:
            try:
                asignacion = proyecto.calculo_nivel.asignacion
                if asignacion:
                    validador = asignacion.asignado_por or asignacion.evaluacion_empresa.administrador
            except Exception as e:
                print(f'⚠️ Error al buscar validador: {e}')

        if not validador:
            return self.error_response(
                message='No se pudo determinar el validador. Asígnale un validador interno manualmente.',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # ─── Crear aprobación ─────────────────────────────────────────────────
        serializer = SolicitarAprobacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                aprobacion = AprobacionGAP.objects.create(
                    proyecto=proyecto,
                    solicitado_por=user,
                    validador=validador,
                    comentarios_solicitud=serializer.validated_data.get('comentarios', ''),
                    documentos_adjuntos=serializer.validated_data.get('documentos_adjuntos', []),
                    items_completados=proyecto.items_completados if proyecto.modo_presupuesto == 'por_items' else 0,
                    items_totales=proyecto.total_items if proyecto.modo_presupuesto == 'por_items' else 0,
                    presupuesto_ejecutado=proyecto.presupuesto_total_ejecutado,
                    presupuesto_planificado=proyecto.presupuesto_total_planificado,
                    gap_original=proyecto.gap_original,
                )

                proyecto.estado = 'en_validacion'
                proyecto.save(update_fields=['estado'])

                # ⭐ Notificar al validador
                Notificacion.objects.create(
                    usuario=validador,
                    tipo='aprobacion',
                    titulo=f'📋 Solicitud de aprobación - {proyecto.codigo_proyecto}',
                    mensaje=(
                        f'{user.nombre_completo} solicita tu aprobación para cerrar el GAP '
                        f'del proyecto {proyecto.codigo_proyecto}.\n\n'
                        f'Comentarios: {serializer.validated_data.get("comentarios", "Sin comentarios")}'
                    ),
                    url_accion=f'/proyectos-remediacion/{proyecto.id}',
                    datos_adicionales={
                        'proyecto_id':   str(proyecto.id),
                        'aprobacion_id': str(aprobacion.id),
                    }
                )

        except Exception as e:
            return self.error_response(
                message=f'Error al crear la solicitud: {str(e)}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return self.success_response(
            data=AprobacionGAPDetailSerializer(aprobacion).data,
            message=f'Solicitud de aprobación enviada a {validador.nombre_completo}',
            status_code=status.HTTP_201_CREATED
        )

    # ── Aprobar cierre de GAP ─────────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def aprobar_cierre_gap(self, request, pk=None):
        """
        Aprueba el cierre del GAP de un proyecto.
        POST /api/proyectos-remediacion/{id}/aprobar_cierre_gap/
        """
        proyecto = self.get_object()
        user     = request.user

        aprobacion = AprobacionGAP.objects.filter(
            proyecto=proyecto,
            estado='pendiente',
            activo=True
        ).first()

        if not aprobacion:
            return self.error_response(
                message='No hay una solicitud de aprobación pendiente para este proyecto',
                status_code=status.HTTP_404_NOT_FOUND
            )

        if aprobacion.validador != user:
            return self.error_response(
                message='No tienes permisos para aprobar esta solicitud',
                status_code=status.HTTP_403_FORBIDDEN
            )

        serializer = ResponderAprobacionSerializer(data={
            'aprobado':      True,
            'observaciones': request.data.get('observaciones', ''),
        })
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                aprobacion.estado         = 'aprobado'
                aprobacion.fecha_revision = timezone.now()
                aprobacion.observaciones  = serializer.validated_data.get('observaciones', '')
                aprobacion.save()

                proyecto.estado       = 'cerrado'
                proyecto.fecha_fin_real = date.today()
                proyecto.save(update_fields=['estado', 'fecha_fin_real'])

                # ⭐ Marcar GAP como remediado
                if proyecto.calculo_nivel:
                    proyecto.calculo_nivel.remediado        = True
                    proyecto.calculo_nivel.fecha_remediacion = timezone.now()
                    proyecto.calculo_nivel.save(update_fields=['remediado', 'fecha_remediacion'])

                # Notificar al solicitante
                Notificacion.objects.create(
                    usuario=aprobacion.solicitado_por,
                    tipo='aprobacion',
                    titulo=f'✅ GAP aprobado - {proyecto.codigo_proyecto}',
                    mensaje=(
                        f'Tu solicitud de cierre de GAP para el proyecto '
                        f'{proyecto.codigo_proyecto} ha sido APROBADA.\n\n'
                        f'Validador: {user.nombre_completo}\n'
                        f'Observaciones: {aprobacion.observaciones or "Sin observaciones"}'
                    ),
                    url_accion=f'/proyectos-remediacion/{proyecto.id}',
                    datos_adicionales={
                        'proyecto_id':   str(proyecto.id),
                        'aprobacion_id': str(aprobacion.id),
                    }
                )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.error_response(
                message=f'Error al aprobar: {str(e)}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return self.success_response(
            data=AprobacionGAPDetailSerializer(aprobacion).data,
            message='GAP aprobado exitosamente'
        )

    # ── Rechazar cierre de GAP ────────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def rechazar_cierre_gap(self, request, pk=None):
        """
        Rechaza el cierre del GAP de un proyecto.
        POST /api/proyectos-remediacion/{id}/rechazar_cierre_gap/
        """
        proyecto = self.get_object()
        user     = request.user

        aprobacion = AprobacionGAP.objects.filter(
            proyecto=proyecto,
            estado='pendiente',
            activo=True
        ).first()

        if not aprobacion:
            return self.error_response(
                message='No hay una solicitud de aprobación pendiente para este proyecto',
                status_code=status.HTTP_404_NOT_FOUND
            )

        if aprobacion.validador != user:
            return self.error_response(
                message='No tienes permisos para rechazar esta solicitud',
                status_code=status.HTTP_403_FORBIDDEN
            )

        serializer = ResponderAprobacionSerializer(data={
            'aprobado':      False,
            'observaciones': request.data.get('observaciones', ''),
        })
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                aprobacion.estado         = 'rechazado'
                aprobacion.fecha_revision = timezone.now()
                aprobacion.observaciones  = serializer.validated_data['observaciones']
                aprobacion.save()

                proyecto.estado = 'en_ejecucion'
                proyecto.save(update_fields=['estado'])

                # Notificar al solicitante
                Notificacion.objects.create(
                    usuario=aprobacion.solicitado_por,
                    tipo='aprobacion',
                    titulo=f'❌ Solicitud rechazada - {proyecto.codigo_proyecto}',
                    mensaje=(
                        f'Tu solicitud de cierre de GAP para el proyecto '
                        f'{proyecto.codigo_proyecto} ha sido RECHAZADA.\n\n'
                        f'Validador: {user.nombre_completo}\n'
                        f'Observaciones: {aprobacion.observaciones or "Sin observaciones"}'
                    ),
                    url_accion=f'/proyectos-remediacion/{proyecto.id}',
                    datos_adicionales={
                        'proyecto_id':   str(proyecto.id),
                        'aprobacion_id': str(aprobacion.id),
                    }
                )

        except Exception as e:
            return self.error_response(
                message=f'Error al rechazar: {str(e)}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return self.success_response(
            data=AprobacionGAPDetailSerializer(aprobacion).data,
            message='Solicitud rechazada. Se ha notificado al responsable.'
        )

    # ── Aprobaciones pendientes ───────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def aprobaciones_pendientes(self, request):
        """
        Lista las aprobaciones pendientes del usuario actual.
        GET /api/proyectos-remediacion/aprobaciones_pendientes/
        """
        aprobaciones = AprobacionGAP.objects.filter(
            validador=request.user,
            estado='pendiente',
            activo=True
        ).select_related('proyecto', 'solicitado_por').order_by('-fecha_solicitud')

        return Response({
            'count':       aprobaciones.count(),
            'aprobaciones': AprobacionGAPListSerializer(aprobaciones, many=True).data,
        })