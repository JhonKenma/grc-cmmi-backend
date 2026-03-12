# apps/asignaciones_iq/views.py
"""
Views para Asignación de Evaluaciones Inteligentes
Flujo: Usuario responde → Auditor califica → GAP calculado → Reporte → Remediar
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db.models import Avg, Count

from apps.core.permissions import EsAdminOSuperAdmin
from apps.core.services.storage_service import StorageService
from apps.respuestas.models import Evidencia

from .models import AsignacionEvaluacionIQ, RespuestaEvaluacionIQ, CalculoNivelIQ
from .serializers import (
    AsignacionIQListSerializer,
    AsignacionIQDetailSerializer,
    CrearAsignacionIQSerializer,
    RespuestaIQDetailSerializer,
    CrearRespuestaIQSerializer,
    EnviarRespuestaIQSerializer,
    CalificarRespuestaIQSerializer,
    PreguntaConRespuestaIQSerializer,
    CalculoNivelIQSerializer,
    EvidenciaIQSerializer,
)
from .services import NotificacionAsignacionIQService


# ─────────────────────────────────────────────────────────────────────────────
# ASIGNACIONES
# ─────────────────────────────────────────────────────────────────────────────

class AsignacionEvaluacionIQViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de asignaciones IQ."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AsignacionEvaluacionIQ.objects.select_related(
            'evaluacion', 'usuario_asignado', 'empresa',
            'asignado_por', 'auditado_por', 'revisado_por'
        )
        if user.rol == 'superadmin':
            return qs.all()
        elif user.rol == 'administrador':
            return qs.filter(empresa=user.empresa)
        elif user.rol == 'auditor':
            return qs.filter(empresa=user.empresa)
        else:
            return qs.filter(usuario_asignado=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return CrearAsignacionIQSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return AsignacionIQDetailSerializer
        return AsignacionIQListSerializer

    def create(self, request, *args, **kwargs):
        if request.user.rol not in ['administrador', 'superadmin']:
            return Response(
                {'error': 'Solo administradores pueden asignar evaluaciones'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        asignaciones = serializer.save()

        for asignacion in asignaciones:
            if asignacion.notificar_usuario:
                try:
                    NotificacionAsignacionIQService.notificar_asignacion(asignacion)
                except Exception as e:
                    print(f'⚠️  Error al notificar: {e}')

        output = AsignacionIQListSerializer(asignaciones, many=True)
        return Response(
            {'asignaciones': output.data, 'total_creadas': len(asignaciones)},
            status=status.HTTP_201_CREATED
        )

    # ── Mis asignaciones (usuario) ─────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='mis-asignaciones')
    def mis_asignaciones(self, request):
        qs = AsignacionEvaluacionIQ.objects.filter(
            usuario_asignado=request.user, activo=True
        )
        estado = request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)

        serializer = AsignacionIQListSerializer(qs, many=True)
        return Response({
            'asignaciones': serializer.data,
            'estadisticas': {
                'total':       qs.count(),
                'pendientes':  qs.filter(estado='pendiente').count(),
                'en_progreso': qs.filter(estado='en_progreso').count(),
                'completadas': qs.filter(estado='completada').count(),
                'auditadas':   qs.filter(estado='auditada').count(),
            }
        })

    # ── Iniciar (usuario) ──────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='iniciar')
    def iniciar(self, request, pk=None):
        asignacion = self.get_object()
        if asignacion.usuario_asignado != request.user:
            return Response(
                {'error': 'Solo puedes iniciar tus propias asignaciones'},
                status=status.HTTP_403_FORBIDDEN
            )
        if asignacion.estado != 'pendiente':
            return Response(
                {'error': f'La asignación ya está en estado: {asignacion.get_estado_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        asignacion.iniciar()
        return Response({
            'success': True,
            'message': 'Evaluación iniciada',
            'asignacion': AsignacionIQDetailSerializer(asignacion).data
        })

    # ── Cerrar revisión de auditoría (auditor) ─────────────────────────────────

    @action(detail=True, methods=['post'], url_path='cerrar-auditoria')
    def cerrar_auditoria(self, request, pk=None):
        """
        El auditor cierra la revisión.
        - Marca respuestas sin calificar como NO_CUMPLE
        - Calcula GAP por sección/framework
        - Cambia estado a 'auditada'
        """
        if request.user.rol not in ['auditor', 'administrador', 'superadmin']:
            return Response(
                {'error': 'Solo auditores pueden cerrar la revisión'},
                status=status.HTTP_403_FORBIDDEN
            )

        asignacion = self.get_object()

        if asignacion.estado != 'completada':
            return Response(
                {'error': 'Solo se puede auditar una asignación completada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        notas = request.data.get('notas_auditoria', '')
        asignacion.cerrar_revision_auditoria(request.user, notas)

        # Notificar al admin
        try:
            NotificacionAsignacionIQService.notificar_auditoria_completada(asignacion)
        except Exception as e:
            print(f'⚠️  Error al notificar: {e}')

        return Response({
            'success': True,
            'message': 'Auditoría cerrada. GAP calculado correctamente.',
            'asignacion': AsignacionIQDetailSerializer(asignacion).data,
            'calculos_gap': CalculoNivelIQSerializer(
                asignacion.calculos_nivel_iq.all(), many=True
            ).data
        })

    # ── Aprobar / Rechazar (admin) ─────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        if request.user.rol not in ['administrador', 'superadmin']:
            return Response({'error': 'Sin permisos'}, status=status.HTTP_403_FORBIDDEN)
        asignacion = self.get_object()
        if asignacion.estado != 'auditada':
            return Response(
                {'error': 'Solo se pueden aprobar asignaciones auditadas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        asignacion.aprobar(request.user, request.data.get('notas_revision', ''))
        return Response({
            'success': True,
            'asignacion': AsignacionIQDetailSerializer(asignacion).data
        })

    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar(self, request, pk=None):
        if request.user.rol not in ['administrador', 'superadmin']:
            return Response({'error': 'Sin permisos'}, status=status.HTTP_403_FORBIDDEN)
        asignacion = self.get_object()
        notas = request.data.get('notas_revision', '')
        if not notas:
            return Response(
                {'error': 'Debe proporcionar notas al rechazar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        asignacion.rechazar(request.user, notas)
        return Response({
            'success': True,
            'asignacion': AsignacionIQDetailSerializer(asignacion).data
        })

    # ── Estadísticas ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[EsAdminOSuperAdmin], url_path='estadisticas')
    def estadisticas(self, request):
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'por_estado': {
                'pendientes':  qs.filter(estado='pendiente').count(),
                'en_progreso': qs.filter(estado='en_progreso').count(),
                'completadas': qs.filter(estado='completada').count(),
                'auditadas':   qs.filter(estado='auditada').count(),
                'aprobadas':   qs.filter(estado='aprobada').count(),
                'rechazadas':  qs.filter(estado='rechazada').count(),
                'vencidas':    qs.filter(estado='vencida').count(),
            },
            'vencidas_sin_completar': sum(1 for a in qs if a.esta_vencida),
            'promedio_completado': qs.aggregate(
                Avg('porcentaje_completado')
            )['porcentaje_completado__avg'] or 0,
        })

    # ── GAP de una asignación ──────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='gap')
    def gap(self, request, pk=None):
        asignacion = self.get_object()
        calculos = CalculoNivelIQ.objects.filter(asignacion=asignacion)
        return Response({
            'asignacion_id': asignacion.id,
            'evaluacion': asignacion.evaluacion.nombre,
            'usuario': asignacion.usuario_asignado.get_full_name(),
            'estado': asignacion.estado,
            'calculos': CalculoNivelIQSerializer(calculos, many=True).data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# RESPUESTAS IQ
# ─────────────────────────────────────────────────────────────────────────────

class RespuestaEvaluacionIQViewSet(viewsets.ModelViewSet):
    """ViewSet para respuestas de evaluaciones IQ."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = RespuestaEvaluacionIQ.objects.select_related(
            'asignacion', 'pregunta', 'pregunta__framework',
            'respondido_por', 'auditado_por'
        ).prefetch_related('evidencias')

        if user.rol == 'superadmin':
            pass
        elif user.rol in ['administrador', 'auditor']:
            qs = qs.filter(asignacion__empresa=user.empresa)
        else:
            qs = qs.filter(asignacion__usuario_asignado=user)

        asignacion_id = self.request.query_params.get('asignacion')
        if asignacion_id:
            qs = qs.filter(asignacion_id=asignacion_id)

        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CrearRespuestaIQSerializer
        return RespuestaIQDetailSerializer

    def perform_create(self, serializer):
        serializer.save(respondido_por=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = RespuestaIQDetailSerializer(serializer.instance)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        if instance.respondido_por != request.user:
            return Response(
                {'error': 'Solo puedes editar tus propias respuestas'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CrearRespuestaIQSerializer(
            instance, data=request.data, partial=partial,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(modificado_por=request.user)
        return Response(RespuestaIQDetailSerializer(instance).data)

    # ── Preguntas con respuestas (para el formulario) ──────────────────────────

    @action(
        detail=False, methods=['get'],
        url_path='preguntas-asignacion/(?P<asignacion_id>[^/.]+)'
    )
    def preguntas_asignacion(self, request, asignacion_id=None):
        """GET /api/respuestas-iq/preguntas-asignacion/{asignacion_id}/"""
        try:
            asignacion = AsignacionEvaluacionIQ.objects.get(id=asignacion_id)
        except AsignacionEvaluacionIQ.DoesNotExist:
            return Response({'error': 'Asignación no encontrada'}, status=404)

        # Permisos
        if request.user.rol not in ['superadmin', 'administrador', 'auditor']:
            if asignacion.usuario_asignado != request.user:
                return Response({'error': 'Sin permisos'}, status=403)

        preguntas = asignacion.evaluacion.get_preguntas_a_responder()
        serializer = PreguntaConRespuestaIQSerializer(
            preguntas, many=True,
            context={'asignacion_id': asignacion_id, 'request': request}
        )

        return Response({
            'asignacion': {
                'id': asignacion.id,
                'evaluacion': asignacion.evaluacion.nombre,
                'estado': asignacion.estado,
                'total_preguntas': asignacion.total_preguntas,
                'preguntas_respondidas': asignacion.preguntas_respondidas,
                'porcentaje_completado': float(asignacion.porcentaje_completado),
            },
            'preguntas': serializer.data
        })

    # ── Enviar respuesta (usuario: borrador → enviado) ─────────────────────────

    @action(detail=True, methods=['post'], url_path='enviar')
    def enviar(self, request, pk=None):
        """
        POST /api/respuestas-iq/{id}/enviar/
        Cambia estado de borrador a enviado.
        Si todas las preguntas quedan enviadas → asignación pasa a 'completada'
        y se notifica al auditor.
        """
        respuesta = self.get_object()

        if respuesta.respondido_por != request.user:
            return Response(
                {'error': 'Solo puedes enviar tus propias respuestas'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = EnviarRespuestaIQSerializer(
            respuesta, data={}, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        respuesta_actualizada = serializer.save()

        # Verificar si la asignación quedó completa
        asignacion = respuesta_actualizada.asignacion
        asignacion_completa = asignacion.estado == 'completada'

        mensaje = (
            '¡Has completado todas las preguntas! El auditor fue notificado.'
            if asignacion_completa
            else f'Respuesta enviada. Faltan '
                 f'{asignacion.total_preguntas - asignacion.preguntas_respondidas} preguntas.'
        )

        return Response({
            'success': True,
            'message': mensaje,
            'respuesta': RespuestaIQDetailSerializer(respuesta_actualizada).data,
            'asignacion': AsignacionIQListSerializer(asignacion).data,
            'asignacion_completa': asignacion_completa,
        })

    # ── Calificar respuesta (auditor) ──────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='calificar')
    def calificar(self, request, pk=None):
        """
        POST /api/respuestas-iq/{id}/calificar/
        El auditor asigna SI_CUMPLE / CUMPLE_PARCIAL / NO_CUMPLE + nivel_madurez.
        """
        if request.user.rol not in ['auditor', 'administrador', 'superadmin']:
            return Response(
                {'error': 'Solo auditores pueden calificar respuestas'},
                status=status.HTTP_403_FORBIDDEN
            )

        respuesta = self.get_object()

        if respuesta.estado != 'enviado':
            return Response(
                {'error': 'Solo se pueden calificar respuestas enviadas'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CalificarRespuestaIQSerializer(
            respuesta, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        respuesta_calificada = serializer.save()

        return Response({
            'success': True,
            'message': 'Respuesta calificada correctamente',
            'respuesta': RespuestaIQDetailSerializer(respuesta_calificada).data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# EVIDENCIAS IQ
# ─────────────────────────────────────────────────────────────────────────────

class EvidenciaIQViewSet(viewsets.ModelViewSet):
    """Evidencias para respuestas de evaluaciones IQ."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = Evidencia.objects.filter(
            respuesta_iq__isnull=False, activo=True
        ).select_related('respuesta_iq', 'subido_por')

        if user.rol == 'superadmin':
            pass
        elif user.rol in ['administrador', 'auditor']:
            qs = qs.filter(respuesta_iq__asignacion__empresa=user.empresa)
        else:
            qs = qs.filter(respuesta_iq__respondido_por=user)

        respuesta_id = self.request.query_params.get('respuesta_iq')
        if respuesta_id:
            qs = qs.filter(respuesta_iq_id=respuesta_id)

        return qs

    def get_serializer_class(self):
        return EvidenciaIQSerializer

    def create(self, request, *args, **kwargs):
        """POST /api/evidencias-iq/  — sube un archivo para una respuesta IQ."""

        respuesta_iq_id = request.data.get('respuesta_iq_id')
        if not respuesta_iq_id:
            return Response(
                {'error': 'respuesta_iq_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            respuesta_iq = RespuestaEvaluacionIQ.objects.get(id=respuesta_iq_id)
        except RespuestaEvaluacionIQ.DoesNotExist:
            return Response({'error': 'Respuesta no encontrada'}, status=404)

        if respuesta_iq.respondido_por != request.user:
            return Response({'error': 'Sin permisos'}, status=403)

        if respuesta_iq.estado != 'borrador':
            return Response(
                {'error': 'Solo se pueden agregar evidencias a respuestas en borrador'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Evidencia.objects.filter(respuesta_iq=respuesta_iq, activo=True).count() >= 3:
            return Response({'error': 'Máximo 3 evidencias por respuesta'}, status=400)

        archivo = request.FILES.get('archivo')
        if not archivo:
            return Response({'error': 'El archivo es requerido'}, status=400)

        if not Evidencia.validar_extension(archivo.name):
            return Response({'error': 'Tipo de archivo no permitido'}, status=400)

        if not Evidencia.validar_tamanio(archivo.size):
            return Response({'error': 'El archivo no debe superar 10MB'}, status=400)

        # Sanitizar nombre del archivo (sin espacios, emojis ni caracteres especiales)
        import re
        import uuid as uuid_lib
        extension = archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else 'bin'
        nombre_seguro = f"{uuid_lib.uuid4().hex}.{extension}"

        # Subir a Supabase
        storage    = StorageService()
        empresa_id = respuesta_iq.asignacion.empresa_id
        ruta       = f"evidencias/iq/{empresa_id}/{respuesta_iq_id}/{nombre_seguro}"
        resultado  = storage.upload_file(archivo, ruta)

        if not resultado['success']:
            return Response(
                {'error': 'Error al subir archivo: ' + resultado.get('error', '')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        evidencia = Evidencia.objects.create(
            respuesta_iq=respuesta_iq,
            codigo_documento=request.data.get('codigo_documento', f'DOC-{respuesta_iq_id}'),
            tipo_documento_enum=request.data.get('tipo_documento_enum', 'otro'),
            titulo_documento=request.data.get('titulo_documento', archivo.name),
            objetivo_documento=request.data.get('objetivo_documento', 'Evidencia de cumplimiento'),
            nombre_archivo_original=archivo.name,
            archivo=resultado['path'],
            tamanio_bytes=archivo.size,
            subido_por=request.user
        )

        return Response(EvidenciaIQSerializer(evidencia).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        evidencia = self.get_object()
        if evidencia.respuesta_iq.respondido_por != request.user:
            return Response({'error': 'Sin permisos'}, status=403)
        evidencia.activo = False
        evidencia.save()
        return Response(status=status.HTTP_204_NO_CONTENT)