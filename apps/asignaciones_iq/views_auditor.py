# apps/asignaciones_iq/views_auditor.py
"""
ViewSet exclusivo para el Auditor en el módulo de Evaluaciones Inteligentes (IQ).

Endpoints:
  GET  /api/auditor-iq/mis_revisiones/                     → Asignaciones IQ completadas
  POST /api/auditor-iq/calificar/{respuesta_id}/           → Calificar una respuesta IQ
  POST /api/auditor-iq/cerrar_revision/{asignacion_id}/    → Cerrar revisión + calcular GAP
  GET  /api/auditor-iq/historial/                          → Asignaciones ya auditadas

Integración: agrega en apps/asignaciones_iq/urls.py:
    from .views_auditor import AuditorIQViewSet
    router.register(r'auditor-iq', AuditorIQViewSet, basename='auditor-iq')
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from apps.core.permissions import EsAuditor
from apps.core.mixins import ResponseMixin

from .models import AsignacionEvaluacionIQ, RespuestaEvaluacionIQ
from .serializers import (
    AsignacionIQListSerializer,
    AsignacionIQDetailSerializer,
    RespuestaIQDetailSerializer,
    CalificarRespuestaIQSerializer,
)


class AuditorIQViewSet(ResponseMixin, viewsets.GenericViewSet):
    """
    ViewSet exclusivo para el Auditor en el módulo IQ.
    Flujo: asignación 'completada' → auditor califica pregunta por pregunta
           → cierra revisión → GAP calculado → asignación 'auditada'
    """
    permission_classes = [IsAuthenticated, EsAuditor]

    # ── mis_revisiones ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def mis_revisiones(self, request):
        """
        Lista asignaciones IQ completadas de la empresa del auditor.
        Incluye pendientes (completada) y ya auditadas.

        Query params:
            evaluacion_id  (int, opcional)
        """
        user = request.user

        qs = AsignacionEvaluacionIQ.objects.filter(
            empresa=user.empresa,
            estado__in=['completada', 'auditada', 'aprobada'],
            activo=True,
        ).select_related(
            'evaluacion', 'usuario_asignado', 'empresa',
            'asignado_por', 'auditado_por',
        ).order_by('-fecha_completado')

        evaluacion_id = request.query_params.get('evaluacion_id')
        if evaluacion_id:
            qs = qs.filter(evaluacion_id=evaluacion_id)

        serializer = AsignacionIQListSerializer(qs, many=True)

        # Enriquecer con datos de progreso de calificación
        data = serializer.data
        for item, asig in zip(data, qs):
            total    = RespuestaEvaluacionIQ.objects.filter(asignacion=asig).count()
            calificadas = RespuestaEvaluacionIQ.objects.filter(
                asignacion=asig, estado='auditado'
            ).count()
            no_aplica = RespuestaEvaluacionIQ.objects.filter(
                asignacion=asig, respuesta='NO_APLICA'
            ).count()
            item['total_respuestas']     = total
            item['respuestas_calificadas'] = calificadas + no_aplica
            item['progreso_revision']    = (
                round((calificadas + no_aplica) / total * 100, 1) if total > 0 else 0
            )

        return Response({'count': len(data), 'results': data})

    # ── detalle ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            url_path='detalle/(?P<asignacion_id>[^/.]+)')
    def detalle(self, request, asignacion_id=None):
        """
        GET /api/auditor-iq/detalle/{asignacion_id}/
        Devuelve la asignación + todas sus respuestas con evidencias.
        """
        try:
            asignacion = AsignacionEvaluacionIQ.objects.select_related(
                'evaluacion', 'usuario_asignado', 'empresa', 'auditado_por'
            ).get(id=asignacion_id, empresa=request.user.empresa)
        except AsignacionEvaluacionIQ.DoesNotExist:
            return self.error_response(
                message='Asignación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        respuestas = RespuestaEvaluacionIQ.objects.filter(
            asignacion=asignacion
        ).select_related(
            'pregunta', 'pregunta__framework',
            'respondido_por', 'auditado_por',
        ).prefetch_related('evidencias').order_by('pregunta__correlativo')

        return self.success_response(data={
            'asignacion': AsignacionIQDetailSerializer(asignacion).data,
            'respuestas': RespuestaIQDetailSerializer(respuestas, many=True).data,
        })

    # ── calificar ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            url_path='calificar/(?P<respuesta_id>[^/.]+)')
    def calificar(self, request, respuesta_id=None):
        """
        POST /api/auditor-iq/calificar/{respuesta_id}/

        Body:
        {
            "calificacion_auditor": "SI_CUMPLE" | "CUMPLE_PARCIAL" | "NO_CUMPLE",
            "nivel_madurez": 3.0,
            "comentarios_auditor": "...",        (opcional)
            "recomendaciones_auditor": "..."     (opcional)
        }
        """
        try:
            respuesta = RespuestaEvaluacionIQ.objects.select_related(
                'asignacion__empresa', 'asignacion__usuario_asignado'
            ).get(id=respuesta_id)
        except RespuestaEvaluacionIQ.DoesNotExist:
            return self.error_response(
                message='Respuesta no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        # Validar empresa
        if respuesta.asignacion.empresa != request.user.empresa:
            return self.error_response(
                message='No puedes calificar respuestas de otra empresa',
                status_code=status.HTTP_403_FORBIDDEN
            )

        # No calificar NO_APLICA
        if respuesta.respuesta == 'NO_APLICA':
            return self.error_response(
                message='Las respuestas "No Aplica" no requieren calificación',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # La asignación debe estar en 'completada' o 'auditada' (para re-calificar)
        if respuesta.asignacion.estado not in ['completada', 'auditada']:
            return self.error_response(
                message=f'La asignación debe estar completada para auditar. '
                        f'Estado actual: {respuesta.asignacion.get_estado_display()}',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = CalificarRespuestaIQSerializer(
            respuesta, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        respuesta_calificada = serializer.save()

        return self.success_response(
            data=RespuestaIQDetailSerializer(respuesta_calificada).data,
            message='Respuesta calificada exitosamente'
        )

    # ── cerrar_revision ───────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            url_path='cerrar_revision/(?P<asignacion_id>[^/.]+)')
    def cerrar_revision(self, request, asignacion_id=None):
        """
        POST /api/auditor-iq/cerrar_revision/{asignacion_id}/

        Al cerrar:
        1. Respuestas sin calificar → NO_CUMPLE automático
        2. Calcula GAP por sección/framework (crea CalculoNivelIQ)
        3. Estado asignación → 'auditada'
        4. Notifica al administrador

        Body (opcional):
        {
            "notas_auditoria": "Comentarios generales..."
        }
        """
        try:
            asignacion = AsignacionEvaluacionIQ.objects.select_related(
                'empresa', 'evaluacion', 'usuario_asignado'
            ).get(id=asignacion_id, empresa=request.user.empresa)
        except AsignacionEvaluacionIQ.DoesNotExist:
            return self.error_response(
                message='Asignación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        if asignacion.estado != 'completada':
            return self.error_response(
                message=f'Solo se pueden auditar asignaciones completadas. '
                        f'Estado actual: {asignacion.get_estado_display()}',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        notas = request.data.get('notas_auditoria', '')

        try:
            # Esto marca sin calificar como NO_CUMPLE + calcula GAP + cambia estado
            asignacion.cerrar_revision_auditoria(
                auditor=request.user,
                notas=notas
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.error_response(
                message='Error al cerrar la revisión',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Construir resumen del GAP para el frontend
        from .models import CalculoNivelIQ
        from django.db.models import Avg

        calculos = CalculoNivelIQ.objects.filter(asignacion=asignacion)
        stats    = calculos.aggregate(
            gap_avg=Avg('gap'),
            nivel_actual_avg=Avg('nivel_actual'),
            nivel_deseado_avg=Avg('nivel_deseado'),
            cumplimiento_avg=Avg('porcentaje_cumplimiento'),
        )

        # Contar respuestas que se marcaron automáticamente
        pendientes_auto_nc = RespuestaEvaluacionIQ.objects.filter(
            asignacion=asignacion,
            estado='auditado',
            comentarios_auditor__startswith='Sin calificación del auditor'
        ).count()

        gap_promedio = float(stats['gap_avg'] or 0)
        if gap_promedio >= 3:
            clasificacion = 'Crítico'
        elif gap_promedio >= 2:
            clasificacion = 'Alto'
        elif gap_promedio >= 1:
            clasificacion = 'Medio'
        elif gap_promedio > 0:
            clasificacion = 'Bajo'
        else:
            clasificacion = 'Cumplido'

        gap_info = {
            'nivel_deseado':           float(stats['nivel_deseado_avg'] or 0),
            'nivel_actual':            float(stats['nivel_actual_avg'] or 0),
            'gap':                     gap_promedio,
            'clasificacion':           clasificacion,
            'porcentaje_cumplimiento': float(stats['cumplimiento_avg'] or 0),
            'total_secciones':         calculos.count(),
            'brechas_criticas':        calculos.filter(clasificacion_gap='critico').count(),
            'brechas_altas':           calculos.filter(clasificacion_gap='alto').count(),
        }

        return self.success_response(
            data={
                'asignacion_id':      asignacion.id,
                'estado':             asignacion.estado,
                'gap_info':           gap_info,
                'pendientes_auto_nc': pendientes_auto_nc,
            },
            message='Revisión cerrada. GAP calculado exitosamente.'
        )

    # ── historial ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def historial(self, request):
        """
        GET /api/auditor-iq/historial/
        Asignaciones IQ ya auditadas por este auditor o de su empresa.
        """
        user = request.user

        qs = AsignacionEvaluacionIQ.objects.filter(
            empresa=user.empresa,
            estado__in=['auditada', 'aprobada'],
            activo=True,
        ).select_related(
            'evaluacion', 'usuario_asignado', 'auditado_por'
        ).order_by('-fecha_auditada')

        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')

        if fecha_desde:
            qs = qs.filter(fecha_auditada__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_auditada__date__lte=fecha_hasta)

        serializer = AsignacionIQListSerializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})

    # ── listado respuestas para revisión ─────────────────────────────────────

    @action(detail=False, methods=['get'],
            url_path='respuestas/(?P<asignacion_id>[^/.]+)')
    def respuestas_asignacion(self, request, asignacion_id=None):
        """
        GET /api/auditor-iq/respuestas/{asignacion_id}/
        Devuelve todas las respuestas de la asignación con evidencias.
        Equivalente a GET /api/respuestas/revision/?asignacion= del módulo de encuestas.
        """
        try:
            asignacion = AsignacionEvaluacionIQ.objects.get(
                id=asignacion_id, empresa=request.user.empresa
            )
        except AsignacionEvaluacionIQ.DoesNotExist:
            return self.error_response(
                message='Asignación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        respuestas = RespuestaEvaluacionIQ.objects.filter(
            asignacion=asignacion
        ).select_related(
            'pregunta', 'pregunta__framework',
            'respondido_por', 'auditado_por',
        ).prefetch_related('evidencias').order_by('pregunta__correlativo')

        # Shape compatible con TablaRespuestasRevision (mismo que encuestas)
        data = []
        for r in respuestas:
            data.append({
                'id':                      r.id,
                'asignacion':              r.asignacion_id,
                'pregunta':                r.pregunta_id,
                'pregunta_codigo':         r.pregunta.codigo_control,
                'pregunta_texto':          r.pregunta.pregunta,
                # Respuesta del usuario (null = Sí con evidencias, 'NO_CUMPLE', 'NO_APLICA')
                'respuesta':               r.respuesta,
                'justificacion':           r.justificacion,
                'comentarios_adicionales': r.comentarios_adicionales,
                # Calificación del auditor
                'calificacion_auditor':    r.calificacion_auditor,
                'calificacion_display':    r.get_calificacion_auditor_display() if r.calificacion_auditor else '',
                'comentarios_auditor':     r.comentarios_auditor,
                'recomendaciones_auditor': r.recomendaciones_auditor,
                'fecha_auditoria':         r.fecha_auditoria,
                'auditado_por':            r.auditado_por_id,
                'auditado_por_nombre':     r.auditado_por.get_full_name() if r.auditado_por else '',
                'nivel_madurez':           float(r.nivel_madurez),
                # Estado
                'estado':                  r.estado,
                'estado_display':          r.get_estado_display(),
                # Auditoría
                'respondido_por':          r.respondido_por_id,
                'respondido_por_nombre':   r.respondido_por.get_full_name() if r.respondido_por else '',
                'respondido_at':           r.respondido_at,
                'version':                 r.version,
                # Evidencias (mismo shape que EvidenciaSerializer)
                'evidencias': [
                    {
                        'id':                      ev.id,
                        'respuesta':               ev.respuesta_iq_id,
                        'codigo_documento':        ev.codigo_documento,
                        'tipo_documento_enum':     ev.tipo_documento_enum,
                        'tipo_documento_display':  ev.get_tipo_documento_enum_display(),
                        'titulo_documento':        ev.titulo_documento,
                        'objetivo_documento':      ev.objetivo_documento,
                        'nombre_archivo_original': ev.nombre_archivo_original,
                        'url_archivo':             ev.url_archivo,
                        'tamanio_mb':              ev.tamanio_mb,
                        'fecha_creacion':          ev.fecha_creacion,
                        'activo':                  ev.activo,
                    }
                    for ev in r.evidencias.filter(activo=True)
                ],
            })

        return Response({'count': len(data), 'results': data})