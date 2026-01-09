# apps/respuestas/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from apps.respuestas.services import CalculoNivelService 

from apps.asignaciones.models import Asignacion
from apps.core.mixins import ResponseMixin
from .models import (
    TipoDocumento,
    Respuesta,
    HistorialRespuesta,
    Evidencia,
    CalculoNivel,
    Iniciativa
)
from .serializers import (
    TipoDocumentoSerializer,
    TipoDocumentoListSerializer,
    RespuestaListSerializer,
    RespuestaDetailSerializer,
    RespuestaCreateSerializer,
    RespuestaUpdateSerializer,
    RespuestaEnviarSerializer,
    RespuestaModificarAdminSerializer,
    EvidenciaSerializer,
    EvidenciaCreateSerializer,
    HistorialRespuestaSerializer,
    CalculoNivelSerializer,
    IniciativaListSerializer,
    IniciativaDetailSerializer,
    IniciativaCreateSerializer,
    VerificarCodigoDocumentoSerializer,
)


# ============================================
# VIEWSET: TIPOS DE DOCUMENTO
# ============================================

class TipoDocumentoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestionar tipos de documentos
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.rol == 'superadmin':
            return TipoDocumento.objects.all()
        else:
            return TipoDocumento.objects.filter(empresa=user.empresa)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TipoDocumentoListSerializer
        return TipoDocumentoSerializer
    
    def perform_create(self, serializer):
        """Crear tipo de documento para la empresa del usuario"""
        serializer.save(empresa=self.request.user.empresa)


# ============================================
# VIEWSET: RESPUESTAS
# ============================================

class RespuestaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestionar respuestas
    
    Endpoints:
    - GET /api/respuestas/ - Listar respuestas
    - GET /api/respuestas/{id}/ - Detalle de respuesta
    - POST /api/respuestas/ - Crear respuesta
    - PATCH /api/respuestas/{id}/ - Actualizar respuesta (solo borrador)
    - POST /api/respuestas/{id}/enviar/ - Enviar respuesta
    - POST /api/respuestas/{id}/modificar_admin/ - Admin modifica respuesta
    - GET /api/respuestas/{id}/historial/ - Historial de cambios
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Respuesta.objects.select_related(
            'asignacion',
            'pregunta',
            'respondido_por',
            'modificado_por'
        ).prefetch_related('evidencias')
        
        # Filtrar por asignación si se proporciona
        asignacion_id = self.request.query_params.get('asignacion')
        if asignacion_id:
            queryset = queryset.filter(asignacion_id=asignacion_id)
        
        # Permisos por rol
        if user.rol == 'superadmin':
            return queryset
        elif user.rol == 'administrador':
            # Ver respuestas de su empresa
            return queryset.filter(asignacion__empresa=user.empresa)
        else:
            # Ver solo sus propias respuestas
            return queryset.filter(respondido_por=user)
        
        return queryset.order_by('pregunta__orden')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RespuestaListSerializer
        elif self.action == 'retrieve':
            return RespuestaDetailSerializer
        elif self.action == 'create':
            return RespuestaCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return RespuestaUpdateSerializer
        elif self.action == 'enviar':
            return RespuestaEnviarSerializer
        elif self.action == 'modificar_admin':
            return RespuestaModificarAdminSerializer
        return RespuestaDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Crear nueva respuesta
        POST /api/respuestas/
        
        ⭐ SOBRESCRITO para devolver el objeto completo con todos los campos
        """
        # Validar datos de entrada
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Crear la respuesta
        respuesta = serializer.save(
            respondido_por=request.user  # ⭐ SOLO respondido_por, NO creado_por
        )
        
        # ⭐ IMPORTANTE: Devolver el objeto COMPLETO con RespuestaDetailSerializer
        output_serializer = RespuestaDetailSerializer(respuesta)
        
        return self.success_response(
            data=output_serializer.data,
            message='Respuesta creada exitosamente',
            status_code=status.HTTP_201_CREATED
        )
    
    def perform_update(self, serializer):
        """Actualizar respuesta (solo en borrador)"""
        instance = self.get_object()
        
        # Validar que sea el creador
        if instance.respondido_por != self.request.user:
            return self.error_response(
                message='Solo puedes editar tus propias respuestas',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        """
        Enviar respuesta individual (cambiar de borrador a enviado)
        POST /api/respuestas/{id}/enviar/
        
        Cuando se envía la ÚLTIMA respuesta (progreso = 100%):
        - Si requiere_revision → estado='pendiente_revision' (sin GAP)
        - Si NO requiere_revision → estado='completado' (CON GAP)
        """
        respuesta = self.get_object()
        
        # Validar que sea el creador
        if respuesta.respondido_por != request.user:
            return self.error_response(
                message='Solo puedes enviar tus propias respuestas',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            with transaction.atomic():
                # Marcar respuesta como enviada
                serializer = self.get_serializer(respuesta, data={})
                serializer.is_valid(raise_exception=True)
                respuesta_actualizada = serializer.save()
                
                # Obtener la asignación
                asignacion = respuesta_actualizada.asignacion
                
                # Actualizar progreso de la asignación
                asignacion.actualizar_progreso()
                
                mensaje = 'Respuesta enviada exitosamente'
                gap_info = None
                asignacion_completada = False
                
                # ⭐ VERIFICAR SI ES LA ÚLTIMA RESPUESTA (100% completado)
                if asignacion.porcentaje_avance >= 100:
                    print(f"🎯 Asignación {asignacion.id} alcanzó 100% de progreso")
                    asignacion_completada = True
                    
                    if asignacion.requiere_revision:
                        # ═══════════════════════════════════════════════
                        # CASO 1: REQUIERE REVISIÓN → NO CALCULAR GAP
                        # ═══════════════════════════════════════════════
                        asignacion.estado = 'pendiente_revision'
                        asignacion.fecha_envio_revision = timezone.now()
                        asignacion.save()
                        
                        mensaje = 'Respuesta enviada. ¡Has completado todas las preguntas! Tu evaluación será revisada por el administrador.'
                        
                        print(f"⏸️  Asignación enviada a revisión")
                        print(f"⏸️  GAP NO calculado (se calculará al aprobar)")
                    
                    else:
                        # ═══════════════════════════════════════════════
                        # CASO 2: NO REQUIERE REVISIÓN → CALCULAR GAP
                        # ═══════════════════════════════════════════════
                        asignacion.estado = 'completado'
                        asignacion.fecha_completado = timezone.now()
                        asignacion.save()
                        
                        print(f"✅ Asignación completada automáticamente")
                        print(f"🔧 Calculando GAP...")
                        
                        try:
                            # ⭐ CALCULAR GAP AUTOMÁTICAMENTE
                            calculo_gap = CalculoNivelService.calcular_gap_asignacion(asignacion)
                            
                            print(f"✅ GAP calculado exitosamente:")
                            print(f"   📊 Nivel Deseado: {calculo_gap.nivel_deseado}")
                            print(f"   📊 Nivel Actual: {calculo_gap.nivel_actual:.2f}")
                            print(f"   📊 GAP: {calculo_gap.gap:.2f}")
                            print(f"   📊 Clasificación: {calculo_gap.get_clasificacion_gap_display()}")
                            
                            gap_info = {
                                'nivel_deseado': float(calculo_gap.nivel_deseado),
                                'nivel_actual': float(calculo_gap.nivel_actual),
                                'gap': float(calculo_gap.gap),
                                'clasificacion': calculo_gap.get_clasificacion_gap_display(),
                                'clasificacion_gap': calculo_gap.clasificacion_gap,
                                'porcentaje_cumplimiento': float(calculo_gap.porcentaje_cumplimiento),
                            }
                            
                            mensaje = f'¡Felicidades! Has completado la evaluación. GAP calculado: {calculo_gap.gap:.1f} ({calculo_gap.get_clasificacion_gap_display()})'
                        
                        except Exception as e:
                            print(f"⚠️  Error al calcular GAP: {e}")
                            import traceback
                            traceback.print_exc()
                            
                            mensaje = '¡Felicidades! Has completado la evaluación (GAP se calculará después)'
                    
                    # Actualizar progreso de la evaluación
                    if asignacion.evaluacion_empresa:
                        asignacion.evaluacion_empresa.actualizar_progreso()
                
                else:
                    # Aún falta responder preguntas
                    preguntas_restantes = asignacion.total_preguntas - asignacion.preguntas_respondidas
                    mensaje = f'Respuesta enviada. Te faltan {preguntas_restantes} preguntas ({asignacion.porcentaje_avance:.0f}% completado)'
                
                # Respuesta
                from apps.asignaciones.serializers import AsignacionSerializer
                
                return self.success_response(
                    data={
                        'respuesta': RespuestaDetailSerializer(respuesta_actualizada).data,
                        'asignacion': AsignacionSerializer(asignacion).data,
                        'asignacion_completada': asignacion_completada,
                        'gap_calculado': gap_info,
                    },
                    message=mensaje,
                    status_code=status.HTTP_200_OK
                )
        
        except Exception as e:
            print(f"❌ Error al enviar respuesta: {e}")
            import traceback
            traceback.print_exc()
            return self.error_response(
                message='Error al enviar respuesta',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def modificar_admin(self, request, pk=None):
        """
        Administrador modifica respuesta del usuario
        POST /api/respuestas/{id}/modificar_admin/
        """
        respuesta = self.get_object()
        
        # Validar permisos
        if request.user.rol not in ['administrador', 'superadmin']:
            return self.error_response(
                message='Solo administradores pueden modificar respuestas',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(respuesta, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        respuesta_actualizada = serializer.save()
        
        return self.success_response(
            data=RespuestaDetailSerializer(respuesta_actualizada).data,
            message='Respuesta modificada exitosamente',
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def revision(self, request):
        """
        Obtener respuestas para revisión con evidencias incluidas
        GET /api/respuestas/revision/?asignacion={id}
        """
        asignacion_id = request.query_params.get('asignacion')
        
        if not asignacion_id:
            return self.error_response(
                message='Se requiere el parámetro asignacion',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que el usuario tenga permisos
        try:
            from apps.asignaciones.models import Asignacion
            asignacion = Asignacion.objects.get(id=asignacion_id)
        except Asignacion.DoesNotExist:
            return self.error_response(
                message='Asignación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validar permisos
        if request.user.rol == 'administrador':
            if asignacion.empresa != request.user.empresa:
                return self.error_response(
                    message='No tienes permisos para ver esta asignación',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        elif request.user.rol not in ['superadmin']:
            return self.error_response(
                message='No tienes permisos',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        queryset = Respuesta.objects.filter(
            asignacion_id=asignacion_id,
            activo=True
        ).select_related(
            'pregunta',
            'pregunta__dimension',
            'respondido_por'
        ).prefetch_related(
            'evidencias'
        ).order_by('pregunta__orden')
        
        serializer = RespuestaDetailSerializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })
# ============================================
# VIEWSET: EVIDENCIAS
# ============================================

class EvidenciaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestionar evidencias
    
    Endpoints:
    - GET /api/evidencias/ - Listar evidencias
    - GET /api/evidencias/{id}/ - Detalle de evidencia
    - POST /api/evidencias/ - Subir evidencia
    - DELETE /api/evidencias/{id}/ - Eliminar evidencia
    - POST /api/evidencias/verificar_codigo/ - ⭐ Verificar código duplicado
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Evidencia.objects.select_related(
            'respuesta',
            'respuesta__asignacion',
            'respuesta__pregunta',
            'subido_por'
        )
        
        # Filtrar por respuesta si se proporciona
        respuesta_id = self.request.query_params.get('respuesta')
        if respuesta_id:
            queryset = queryset.filter(respuesta_id=respuesta_id)
        
        # Permisos por rol
        if user.rol == 'superadmin':
            return queryset
        elif user.rol == 'administrador':
            return queryset.filter(respuesta__asignacion__empresa=user.empresa)
        else:
            return queryset.filter(respuesta__respondido_por=user)
        
        return queryset.order_by('-fecha_creacion')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EvidenciaCreateSerializer
        elif self.action == 'verificar_codigo':
            return VerificarCodigoDocumentoSerializer
        return EvidenciaSerializer
    
    # ⭐ NUEVO: Endpoint para verificar código duplicado
    @action(detail=False, methods=['post'])
    def verificar_codigo(self, request):
        """
        Verificar si un código de documento ya existe en la empresa
        POST /api/evidencias/verificar_codigo/
        
        Body:
        {
            "codigo_documento": "POL-SEG-001"
        }
        
        Response:
        {
            "existe": true,
            "evidencias_encontradas": [
                {
                    "id": "uuid",
                    "codigo_documento": "POL-SEG-001",
                    "tipo_documento_display": "Política",
                    "titulo_documento": "Política de Seguridad",
                    "pregunta_codigo": "D1-P001",
                    "pregunta_texto": "...",
                    "dimension_nombre": "Gestión de Procesos",
                    "subido_por": "Juan Pérez",
                    "fecha_creacion": "2024-12-18",
                    "puede_reutilizar": true
                }
            ],
            "total_encontradas": 2,
            "mensaje": "Se encontraron 2 documentos con este código"
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        codigo_documento = serializer.validated_data['codigo_documento']
        user = request.user
        
        # Buscar evidencias con el mismo código en la empresa
        evidencias_existentes = Evidencia.buscar_por_codigo(
            codigo_documento,
            user.empresa
        )
        
        if not evidencias_existentes.exists():
            return Response({
                'existe': False,
                'evidencias_encontradas': [],
                'total_encontradas': 0,
                'mensaje': 'No se encontraron documentos con este código'
            })
        
        # Serializar evidencias encontradas
        evidencias_data = []
        for evidencia in evidencias_existentes:
            evidencias_data.append({
                'id': str(evidencia.id),
                'codigo_documento': evidencia.codigo_documento,
                'tipo_documento': evidencia.tipo_documento_enum,
                'tipo_documento_display': evidencia.get_tipo_documento_enum_display(),
                'titulo_documento': evidencia.titulo_documento,
                'objetivo_documento': evidencia.objetivo_documento,
                'pregunta_codigo': evidencia.respuesta.pregunta.codigo,
                'pregunta_texto': evidencia.respuesta.pregunta.texto,
                'dimension_nombre': evidencia.respuesta.pregunta.dimension.nombre,
                'subido_por': evidencia.subido_por.nombre_completo if evidencia.subido_por else 'Desconocido',
                'fecha_creacion': evidencia.fecha_creacion.strftime('%Y-%m-%d'),
                'url_archivo': evidencia.url_archivo,
                'puede_reutilizar': True
            })
        
        return Response({
            'existe': True,
            'evidencias_encontradas': evidencias_data,
            'total_encontradas': len(evidencias_data),
            'mensaje': f'Se {"encontró" if len(evidencias_data) == 1 else "encontraron"} {len(evidencias_data)} documento{"" if len(evidencias_data) == 1 else "s"} con este código'
        })
    
    def perform_destroy(self, instance):
        """Eliminar evidencia (solo en borrador)"""
        respuesta = instance.respuesta
        
        if respuesta.estado != 'borrador':
            return self.error_response(
                message='Solo se pueden eliminar evidencias de respuestas en borrador',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if respuesta.respondido_por != self.request.user:
            return self.error_response(
                message='Solo puedes eliminar evidencias de tus propias respuestas',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Crear registro de auditoría
        HistorialRespuesta.objects.create(
            respuesta=respuesta,
            tipo_cambio='eliminado_evidencia',
            usuario=self.request.user,
            motivo=f'Evidencia eliminada: {instance.codigo_documento} - {instance.titulo_documento}',
            ip_address=self._get_client_ip(),
            user_agent=self._get_user_agent()
        )
        
        instance.delete()
    
    def _get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')
    
    def _get_user_agent(self):
        return self.request.META.get('HTTP_USER_AGENT', '')[:255]


# ============================================
# VIEWSET: HISTORIAL DE RESPUESTAS
# ============================================

class HistorialRespuestaViewSet(ResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver historial de cambios (solo lectura)
    
    Endpoints:
    - GET /api/historial-respuestas/ - Listar historial
    - GET /api/historial-respuestas/{id}/ - Detalle de cambio
    """
    permission_classes = [IsAuthenticated]
    serializer_class = HistorialRespuestaSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = HistorialRespuesta.objects.select_related(
            'respuesta',
            'usuario'
        )
        
        # Filtrar por respuesta si se proporciona
        respuesta_id = self.request.query_params.get('respuesta')
        if respuesta_id:
            queryset = queryset.filter(respuesta_id=respuesta_id)
        
        # Permisos por rol
        if user.rol == 'superadmin':
            return queryset
        elif user.rol == 'administrador':
            return queryset.filter(respuesta__asignacion__empresa=user.empresa)
        else:
            return queryset.filter(respuesta__respondido_por=user)
        
        return queryset.order_by('-timestamp')


# ============================================
# VIEWSET: CÁLCULO DE NIVEL
# ============================================

class CalculoNivelViewSet(ResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para cálculos de nivel de madurez (solo lectura)
    
    Endpoints:
    - GET /api/calculos-nivel/ - Listar cálculos
    - GET /api/calculos-nivel/{id}/ - Detalle de cálculo
    - GET /api/calculos-nivel/por_empresa/ - Cálculos por empresa
    - GET /api/calculos-nivel/por_dimension/ - Cálculos por dimensión
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CalculoNivelSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = CalculoNivel.objects.select_related(
            'asignacion',
            'dimension'
        )
        
        # Permisos por rol
        if user.rol == 'superadmin':
            return queryset
        elif user.rol == 'administrador':
            return queryset.filter(asignacion__empresa=user.empresa)
        else:
            return queryset.filter(asignacion__usuario_asignado=user)
        
        return queryset.order_by('-calculado_at')
    
    @action(detail=False, methods=['get'])
    def por_empresa(self, request):
        """
        Obtener cálculos agrupados por empresa
        GET /api/calculos-nivel/por_empresa/
        """
        user = request.user
        
        if user.rol not in ['superadmin', 'administrador']:
            return self.error_response(
                message='No tienes permisos para ver esta información',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        calculos = self.get_queryset()
        
        # Agrupar por empresa
        from django.db.models import Avg, Count
        resumen = calculos.values(
            'asignacion__empresa__nombre'
        ).annotate(
            total_calculos=Count('id'),
            nivel_promedio=Avg('nivel_actual'),
            gap_promedio=Avg('gap')
        )
        
        return Response(resumen)
    
    @action(detail=False, methods=['get'])
    def por_dimension(self, request):
        """
        Obtener cálculos agrupados por dimensión
        GET /api/calculos-nivel/por_dimension/
        """
        calculos = self.get_queryset()
        
        # Agrupar por dimensión
        from django.db.models import Avg, Count
        resumen = calculos.values(
            'dimension__nombre',
            'dimension__codigo'
        ).annotate(
            total_calculos=Count('id'),
            nivel_promedio=Avg('nivel_actual'),
            gap_promedio=Avg('gap'),
            cumplimiento_promedio=Avg('porcentaje_cumplimiento')
        )
        
        return Response(resumen)


# ============================================
# VIEWSET: INICIATIVAS
# ============================================

class IniciativaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestionar iniciativas de remediación
    
    Endpoints:
    - GET /api/iniciativas/ - Listar iniciativas
    - GET /api/iniciativas/{id}/ - Detalle de iniciativa
    - POST /api/iniciativas/ - Crear iniciativa
    - PATCH /api/iniciativas/{id}/ - Actualizar iniciativa
    - DELETE /api/iniciativas/{id}/ - Eliminar iniciativa
    - GET /api/iniciativas/mis_iniciativas/ - Iniciativas asignadas a mí
    - GET /api/iniciativas/por_vencer/ - Iniciativas próximas a vencer
    - POST /api/iniciativas/{id}/actualizar_progreso/ - Actualizar progreso
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Iniciativa.objects.select_related(
            'calculo_nivel',
            'dimension',
            'empresa',
            'responsable',
            'asignado_por'
        )
        
        # Permisos por rol
        if user.rol == 'superadmin':
            return queryset
        elif user.rol == 'administrador':
            return queryset.filter(empresa=user.empresa)
        else:
            return queryset.filter(responsable=user)
        
        # Filtros opcionales
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        prioridad = self.request.query_params.get('prioridad')
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
        
        return queryset.order_by('-prioridad', 'fecha_termino_estimada')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return IniciativaListSerializer
        elif self.action == 'create':
            return IniciativaCreateSerializer
        return IniciativaDetailSerializer
    
    @action(detail=False, methods=['get'])
    def mis_iniciativas(self, request):
        """
        Obtener iniciativas asignadas al usuario actual
        GET /api/iniciativas/mis_iniciativas/
        """
        iniciativas = Iniciativa.objects.filter(
            responsable=request.user,
            activo=True
        ).select_related(
            'dimension',
            'empresa',
            'asignado_por'
        ).order_by('-prioridad', 'fecha_termino_estimada')
        
        serializer = IniciativaListSerializer(iniciativas, many=True)
        
        return Response({
            'total': iniciativas.count(),
            'iniciativas': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def por_vencer(self, request):
        """
        Obtener iniciativas próximas a vencer (dentro de 7 días)
        GET /api/iniciativas/por_vencer/
        """
        from django.utils import timezone
        from datetime import timedelta
        
        fecha_limite = timezone.now().date() + timedelta(days=7)
        
        iniciativas = self.get_queryset().filter(
            estado__in=['planificada', 'en_progreso'],
            fecha_termino_estimada__lte=fecha_limite,
            fecha_termino_estimada__gte=timezone.now().date()
        ).order_by('fecha_termino_estimada')
        
        serializer = IniciativaListSerializer(iniciativas, many=True)
        
        return Response({
            'total': iniciativas.count(),
            'iniciativas': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def actualizar_progreso(self, request, pk=None):
        """
        Actualizar progreso de una iniciativa
        POST /api/iniciativas/{id}/actualizar_progreso/
        
        Body:
        {
            "porcentaje_avance": 50,
            "estado": "en_progreso"  # opcional
        }
        """
        iniciativa = self.get_object()
        
        # Validar que sea el responsable o administrador
        if request.user != iniciativa.responsable and request.user.rol not in ['administrador', 'superadmin']:
            return self.error_response(
                message='Solo el responsable o un administrador puede actualizar el progreso',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        porcentaje = request.data.get('porcentaje_avance')
        nuevo_estado = request.data.get('estado')
        
        if porcentaje is not None:
            try:
                porcentaje = float(porcentaje)
                if porcentaje < 0 or porcentaje > 100:
                    return self.error_response(
                        message='El porcentaje debe estar entre 0 y 100',
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                iniciativa.porcentaje_avance = porcentaje
            except ValueError:
                return self.error_response(
                    message='Porcentaje inválido',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        if nuevo_estado and nuevo_estado in dict(Iniciativa.ESTADOS).keys():
            iniciativa.estado = nuevo_estado
            
            # Si se completa, registrar fecha real
            if nuevo_estado == 'completada':
                from django.utils import timezone
                iniciativa.fecha_termino_real = timezone.now().date()
        
        iniciativa.save()
        
        serializer = IniciativaDetailSerializer(iniciativa)
        
        return self.success_response(
            data=serializer.data,
            message='Progreso actualizado exitosamente',
            status_code=status.HTTP_200_OK
        )