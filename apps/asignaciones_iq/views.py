# apps/asignaciones_iq/views.py
"""
Views para Asignación de Evaluaciones Inteligentes
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db.models import Q, Count, Avg
from apps.core.permissions import EsAdminOSuperAdmin
from apps.core.services.storage_service import StorageService
from apps.respuestas.models import Evidencia
from .models import AsignacionEvaluacionIQ, ProgresoAsignacion, RespuestaEvaluacionIQ
from .serializers import (
    AsignacionEvaluacionListSerializer,
    AsignacionEvaluacionDetailSerializer,
    CrearAsignacionSerializer,
    ActualizarEstadoAsignacionSerializer,
    CrearRespuestaSerializer,
    PreguntaConRespuestaSerializer,
    ProgresoAsignacionSerializer,
    RespuestaEvaluacionIQSerializer,
)
from .services import NotificacionAsignacionIQService


class AsignacionEvaluacionViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de asignaciones de evaluaciones"""
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.rol == 'superadmin':
            return AsignacionEvaluacionIQ.objects.select_related(
                'evaluacion', 'usuario_asignado', 'empresa', 'asignado_por', 'revisado_por'
            ).all()
        elif user.rol == 'administrador':
            return AsignacionEvaluacionIQ.objects.select_related(
                'evaluacion', 'usuario_asignado', 'empresa', 'asignado_por', 'revisado_por'
            ).filter(empresa=user.empresa)
        else:
            return AsignacionEvaluacionIQ.objects.select_related(
                'evaluacion', 'usuario_asignado', 'empresa', 'asignado_por', 'revisado_por'
            ).filter(usuario_asignado=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CrearAsignacionSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return AsignacionEvaluacionDetailSerializer
        return AsignacionEvaluacionListSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear asignación y propagar respuestas previas"""
        if request.user.rol not in ['administrador', 'superadmin']:
            return Response(
                {'error': 'Solo administradores pueden asignar evaluaciones'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        asignaciones = serializer.save()
        
        resultados_propagacion = []
        for asignacion in asignaciones:
            if asignacion.notificar_usuario:
                NotificacionAsignacionIQService.notificar_asignacion(asignacion)
            
            if asignacion.evaluacion.usar_respuestas_compartidas:
                cantidad = asignacion.propagar_respuestas_previas()
                if cantidad > 0:
                    resultados_propagacion.append({
                        'usuario': asignacion.usuario_asignado.nombre_completo,
                        'respuestas_importadas': cantidad
                    })
        
        output_serializer = AsignacionEvaluacionListSerializer(asignaciones, many=True)
        
        response_data = {
            'asignaciones': output_serializer.data,
            'total_creadas': len(asignaciones),
        }
        
        if resultados_propagacion:
            response_data['respuestas_importadas'] = resultados_propagacion
            response_data['mensaje'] = 'Se importaron respuestas de evaluaciones anteriores'
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'], url_path='mis-asignaciones')
    def mis_asignaciones(self, request):
        """GET /api/asignaciones-iq/mis-asignaciones/"""
        asignaciones = self.get_queryset().filter(usuario_asignado=request.user, activo=True)
        
        estado = request.query_params.get('estado')
        if estado:
            asignaciones = asignaciones.filter(estado=estado)
        
        serializer = AsignacionEvaluacionListSerializer(asignaciones, many=True)
        
        stats = {
            'total': asignaciones.count(),
            'pendientes': asignaciones.filter(estado='pendiente').count(),
            'en_progreso': asignaciones.filter(estado='en_progreso').count(),
            'completadas': asignaciones.filter(estado='completada').count(),
            'vencidas': sum(1 for a in asignaciones if a.esta_vencida),
        }
        
        return Response({
            'asignaciones': serializer.data,
            'estadisticas': stats
        })
    
    @action(detail=True, methods=['post'], url_path='iniciar')
    def iniciar(self, request, pk=None):
        """POST /api/asignaciones-iq/{id}/iniciar/"""
        asignacion = self.get_object()
        
        if asignacion.usuario_asignado != request.user:
            return Response(
                {'error': 'Solo puedes iniciar tus propias asignaciones'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if asignacion.estado != 'pendiente':
            return Response(
                {'error': f'La asignación ya está {asignacion.get_estado_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        asignacion.iniciar()
        
        serializer = AsignacionEvaluacionDetailSerializer(asignacion)
        return Response({
            'success': True,
            'message': 'Asignación iniciada correctamente',
            'asignacion': serializer.data
        })
    
    @action(detail=True, methods=['post'], url_path='completar')
    def completar(self, request, pk=None):
        """POST /api/asignaciones-iq/{id}/completar/"""
        asignacion = self.get_object()
        
        if asignacion.usuario_asignado != request.user:
            return Response(
                {'error': 'Solo puedes completar tus propias asignaciones'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if asignacion.estado != 'en_progreso':
            return Response(
                {'error': 'La asignación debe estar en progreso'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        asignacion.actualizar_progreso()
        
        if asignacion.preguntas_respondidas < asignacion.total_preguntas:
            return Response(
                {
                    'error': 'Aún no has completado todas las preguntas',
                    'preguntas_respondidas': asignacion.preguntas_respondidas,
                    'total_preguntas': asignacion.total_preguntas,
                    'preguntas_faltantes': asignacion.total_preguntas - asignacion.preguntas_respondidas
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        asignacion.completar()
        
        try:
            NotificacionAsignacionIQService.notificar_completada(asignacion)
        except Exception as e:
            print(f"Error al enviar notificación: {str(e)}")
        
        serializer = AsignacionEvaluacionDetailSerializer(asignacion)
        return Response({
            'success': True,
            'message': 'Asignación completada correctamente',
            'asignacion': serializer.data
        })
    
    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        """POST /api/asignaciones-iq/{id}/aprobar/"""
        if request.user.rol not in ['administrador', 'superadmin']:
            return Response(
                {'error': 'Solo administradores pueden aprobar'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        asignacion = self.get_object()
        
        if asignacion.estado != 'completada':
            return Response(
                {'error': 'Solo se pueden aprobar asignaciones completadas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notas = request.data.get('notas_revision', '')
        asignacion.aprobar(request.user, notas)
        
        try:
            NotificacionAsignacionIQService.notificar_aprobada(asignacion)
        except Exception as e:
            print(f"Error al enviar notificación: {str(e)}")
        
        serializer = AsignacionEvaluacionDetailSerializer(asignacion)
        return Response({
            'success': True,
            'message': 'Asignación aprobada correctamente',
            'asignacion': serializer.data
        })
    
    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar(self, request, pk=None):
        """POST /api/asignaciones-iq/{id}/rechazar/"""
        if request.user.rol not in ['administrador', 'superadmin']:
            return Response(
                {'error': 'Solo administradores pueden rechazar'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        asignacion = self.get_object()
        
        if asignacion.estado != 'completada':
            return Response(
                {'error': 'Solo se pueden rechazar asignaciones completadas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notas = request.data.get('notas_revision', '')
        if not notas:
            return Response(
                {'error': 'Debe proporcionar notas al rechazar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        asignacion.rechazar(request.user, notas)
        
        try:
            NotificacionAsignacionIQService.notificar_rechazada(asignacion)
        except Exception as e:
            print(f"Error al enviar notificación: {str(e)}")
        
        serializer = AsignacionEvaluacionDetailSerializer(asignacion)
        return Response({
            'success': True,
            'message': 'Asignación rechazada',
            'asignacion': serializer.data
        })
    
    @action(detail=True, methods=['get'], url_path='progreso')
    def progreso(self, request, pk=None):
        """GET /api/asignaciones-iq/{id}/progreso/"""
        asignacion = self.get_object()
        asignacion.actualizar_progreso()
        
        progreso_detallado = ProgresoAsignacion.objects.filter(
            asignacion=asignacion
        ).select_related('pregunta')
        
        return Response({
            'asignacion_id': asignacion.id,
            'total_preguntas': asignacion.total_preguntas,
            'preguntas_respondidas': asignacion.preguntas_respondidas,
            'porcentaje_completado': float(asignacion.porcentaje_completado),
            'estado': asignacion.estado,
            'progreso_detallado': ProgresoAsignacionSerializer(
                progreso_detallado, many=True
            ).data if progreso_detallado.exists() else None
        })
    
    @action(detail=False, methods=['get'], permission_classes=[EsAdminOSuperAdmin], url_path='estadisticas')
    def estadisticas(self, request):
        """GET /api/asignaciones-iq/estadisticas/"""
        queryset = self.get_queryset()
        
        return Response({
            'total': queryset.count(),
            'por_estado': {
                'pendientes': queryset.filter(estado='pendiente').count(),
                'en_progreso': queryset.filter(estado='en_progreso').count(),
                'completadas': queryset.filter(estado='completada').count(),
                'aprobadas': queryset.filter(estado='aprobada').count(),
                'rechazadas': queryset.filter(estado='rechazada').count(),
                'vencidas': queryset.filter(estado='vencida').count(),
            },
            'vencidas_sin_completar': sum(1 for a in queryset if a.esta_vencida),
            'promedio_completado': queryset.aggregate(
                Avg('porcentaje_completado')
            )['porcentaje_completado__avg'] or 0,
        })
    
    @action(detail=False, methods=['get'], permission_classes=[EsAdminOSuperAdmin], url_path='por-evaluacion/(?P<evaluacion_id>[^/.]+)')
    def por_evaluacion(self, request, evaluacion_id=None):
        """GET /api/asignaciones-iq/por-evaluacion/{evaluacion_id}/"""
        asignaciones = self.get_queryset().filter(evaluacion_id=evaluacion_id)
        serializer = AsignacionEvaluacionListSerializer(asignaciones, many=True)
        
        return Response({
            'evaluacion_id': evaluacion_id,
            'total': asignaciones.count(),
            'asignaciones': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[EsAdminOSuperAdmin], url_path='por-usuario/(?P<usuario_id>[^/.]+)')
    def por_usuario(self, request, usuario_id=None):
        """GET /api/asignaciones-iq/por-usuario/{usuario_id}/"""
        asignaciones = self.get_queryset().filter(usuario_asignado_id=usuario_id)
        serializer = AsignacionEvaluacionListSerializer(asignaciones, many=True)
        
        return Response({
            'usuario_id': usuario_id,
            'total': asignaciones.count(),
            'asignaciones': serializer.data
        })
    
    @action(detail=True, methods=['get'], url_path='estadisticas-propagacion')
    def estadisticas_propagacion(self, request, pk=None):
        """GET /api/asignaciones-iq/{id}/estadisticas-propagacion/"""
        asignacion = self.get_object()
        
        total = RespuestaEvaluacionIQ.objects.filter(asignacion=asignacion).count()
        originales = RespuestaEvaluacionIQ.objects.filter(
            asignacion=asignacion, es_respuesta_original=True
        ).count()
        propagadas = total - originales
        
        propagadas_previas = RespuestaEvaluacionIQ.objects.filter(
            asignacion=asignacion,
            es_respuesta_original=False,
            propagada_desde__asignacion__evaluacion__isnull=False
        ).exclude(
            propagada_desde__asignacion__evaluacion=asignacion.evaluacion
        ).count()
        
        return Response({
            'asignacion_id': asignacion.id,
            'evaluacion': asignacion.evaluacion.nombre,
            'usuario': asignacion.usuario_asignado.nombre_completo,
            'total_preguntas': asignacion.total_preguntas,
            'estadisticas': {
                'total_respuestas': total,
                'respuestas_originales': originales,
                'respuestas_propagadas': propagadas,
                'desglose_propagadas': {
                    'de_evaluaciones_anteriores': propagadas_previas,
                    'dentro_de_esta_evaluacion': propagadas - propagadas_previas
                }
            },
            'porcentaje_completado': float(asignacion.porcentaje_completado),
        })


class RespuestaEvaluacionIQViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de respuestas"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = RespuestaEvaluacionIQSerializer
    
    def get_queryset(self):
        qs = RespuestaEvaluacionIQ.objects.select_related(
            'asignacion', 'pregunta', 'pregunta__framework', 'respondido_por'
        ).prefetch_related('evidencias')
        
        user = self.request.user
        if user.rol == 'superadmin':
            pass
        elif user.rol == 'administrador':
            qs = qs.filter(asignacion__asignado_por__empresa=user.empresa)
        else:
            qs = qs.filter(asignacion__usuario_asignado=user)
        
        asignacion_id = self.request.query_params.get('asignacion')
        if asignacion_id:
            qs = qs.filter(asignacion_id=asignacion_id)
        
        return qs
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CrearRespuestaSerializer
        return RespuestaEvaluacionIQSerializer
    
    def perform_create(self, serializer):
        serializer.save(respondido_por=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Crear respuesta - ASEGURAR QUE RETORNE ID"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # ⭐ IMPORTANTE: Usar el serializer completo para la respuesta
        instance = serializer.instance
        response_serializer = RespuestaEvaluacionIQSerializer(instance)
        
        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    @action(detail=False, methods=['get'], url_path='preguntas-asignacion/(?P<asignacion_id>[^/.]+)')
    def preguntas_asignacion(self, request, asignacion_id=None):
        """GET /api/respuestas-iq/preguntas-asignacion/{asignacion_id}/"""
        try:
            asignacion = AsignacionEvaluacionIQ.objects.get(id=asignacion_id)
        except AsignacionEvaluacionIQ.DoesNotExist:
            return Response(
                {'error': 'Asignación no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.user.rol not in ['superadmin', 'administrador']:
            if asignacion.usuario_asignado != request.user:
                return Response(
                    {'error': 'No tienes permiso'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        preguntas = asignacion.evaluacion.get_preguntas_a_responder()
        
        serializer = PreguntaConRespuestaSerializer(
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
        
class EvidenciaIQViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de evidencias de evaluaciones IQ.
    Usa el modelo Evidencia existente pero para RespuestaEvaluacionIQ.
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        user = self.request.user
        qs = Evidencia.objects.filter(
            respuesta_iq__isnull=False,  # Solo evidencias IQ
            activo=True
        ).select_related('respuesta_iq', 'subido_por')
        
        # Filtrar por permisos
        if user.rol == 'superadmin':
            pass
        elif user.rol == 'administrador':
            qs = qs.filter(respuesta_iq__asignacion__empresa=user.empresa)
        else:
            qs = qs.filter(respuesta_iq__respondido_por=user)
        
        # Filtrar por respuesta_iq si se proporciona
        respuesta_iq_id = self.request.query_params.get('respuesta_iq')
        if respuesta_iq_id:
            qs = qs.filter(respuesta_iq_id=respuesta_iq_id)
        
        return qs
    
    def get_serializer_class(self):
        from apps.asignaciones_iq.serializers import EvidenciaSerializer
        return EvidenciaSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear evidencia para respuesta IQ"""
        respuesta_iq_id = request.data.get('respuesta_iq_id')
        
        if not respuesta_iq_id:
            return Response(
                {'error': 'respuesta_iq_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que la respuesta existe y pertenece al usuario
        try:
            respuesta_iq = RespuestaEvaluacionIQ.objects.get(id=respuesta_iq_id)
        except RespuestaEvaluacionIQ.DoesNotExist:
            return Response(
                {'error': 'Respuesta no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if respuesta_iq.respondido_por != request.user:
            return Response(
                {'error': 'No tienes permiso para añadir evidencias a esta respuesta'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar máximo 3 evidencias
        evidencias_count = Evidencia.objects.filter(
            respuesta_iq=respuesta_iq,
            activo=True
        ).count()
        
        if evidencias_count >= 3:
            return Response(
                {'error': 'Máximo 3 evidencias por respuesta'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener archivo
        archivo = request.FILES.get('archivo')
        if not archivo:
            return Response(
                {'error': 'El archivo es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar extensión
        if not Evidencia.validar_extension(archivo.name):
            return Response(
                {'error': 'Tipo de archivo no permitido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamaño
        if not Evidencia.validar_tamanio(archivo.size):
            return Response(
                {'error': 'El archivo no debe superar 10MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Subir a Supabase
        storage = StorageService()
        empresa_id = respuesta_iq.asignacion.empresa_id
        ruta_archivo = f"evidencias/iq/{empresa_id}/{respuesta_iq_id}/{archivo.name}"
        
        resultado = storage.upload_file(archivo, ruta_archivo)
        
        if not resultado['success']:
            return Response(
                {'error': 'Error al subir el archivo: ' + resultado.get('error', '')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Crear evidencia
        evidencia = Evidencia.objects.create(
            respuesta_iq=respuesta_iq,
            codigo_documento=request.data.get('codigo_documento', 'DOC-' + str(respuesta_iq_id)),
            tipo_documento_enum=request.data.get('tipo_documento_enum', 'otro'),
            titulo_documento=request.data.get('titulo_documento', archivo.name),
            objetivo_documento=request.data.get('objetivo_documento', 'Evidencia de cumplimiento'),
            nombre_archivo_original=archivo.name,
            archivo=resultado['path'],
            tamanio_bytes=archivo.size,
            subido_por=request.user
        )
        
        from apps.asignaciones_iq.serializers import EvidenciaSerializer
        serializer = EvidenciaSerializer(evidencia)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, *args, **kwargs):
        """Eliminar evidencia (soft delete)"""
        evidencia = self.get_object()
        
        # Verificar permisos
        if evidencia.respuesta_iq.respondido_por != request.user:
            return Response(
                {'error': 'No tienes permiso para eliminar esta evidencia'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        evidencia.activo = False
        evidencia.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)