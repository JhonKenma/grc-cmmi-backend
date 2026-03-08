import os
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.utils import timezone
from apps.core.permissions import EsAuditor
from apps.core.services.storage_service import StorageService
from apps.respuestas.services import CalculoNivelService 
from apps.documentos.models import Documento  # <--- Importante para vincular documentos
from apps.asignaciones.models import Asignacion
from apps.core.mixins import ResponseMixin

# Modelos Locales
from .models import (
    TipoDocumento,
    Respuesta,
    HistorialRespuesta,
    Evidencia,
    CalculoNivel,
)

# Serializers
from .serializers import (
    AuditorCalificarSerializer,
    AuditorCerrarRevisionSerializer,
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
        """
        # Validar datos de entrada
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Crear la respuesta
        respuesta = serializer.save(
            respondido_por=request.user 
        )
        
        # Devolver el objeto COMPLETO con RespuestaDetailSerializer
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
        Enviar respuesta individual (borrador → enviado).

        Cuando TODAS las respuestas de la asignación están enviadas:
        - Asignación → 'completado' directamente (sin esperar al auditor)
        - GAP NO se calcula aquí → lo calcula el auditor al cerrar su revisión
        - Se notifica al Auditor de la empresa para revisión post-cierre
        """
        respuesta = self.get_object()

        if respuesta.respondido_por != request.user:
            return self.error_response(
                message='Solo puedes enviar tus propias respuestas',
                status_code=status.HTTP_403_FORBIDDEN
            )

        try:
            with transaction.atomic():
                serializer = self.get_serializer(respuesta, data={})
                serializer.is_valid(raise_exception=True)
                respuesta_actualizada = serializer.save()

                asignacion = respuesta_actualizada.asignacion
                asignacion.actualizar_progreso()

                mensaje             = 'Respuesta enviada exitosamente'
                asignacion_completa = False

                if asignacion.porcentaje_avance >= 100:
                    asignacion_completa = True

                    # ── Completada directamente, sin esperar al auditor ───────
                    asignacion.estado           = 'completado'
                    asignacion.fecha_completado = timezone.now()
                    asignacion.save()

                    # ⚠️ NO calcular GAP aquí
                    # El GAP se calcula cuando el auditor cierra su revisión

                    # Actualizar progreso de la evaluación empresa
                    if asignacion.evaluacion_empresa_id:
                        try:
                            asignacion.evaluacion_empresa.actualizar_progreso()
                        except Exception as e:
                            print(f'⚠️  Error al actualizar progreso de evaluación: {e}')

                    # Notificar al Auditor para revisión post-cierre
                    try:
                        from apps.notificaciones.services import NotificacionAsignacionService
                        NotificacionAsignacionService.notificar_pendiente_auditoria(
                            asignacion=asignacion,
                            enviado_por=request.user,
                        )
                        print(f'✅ Notificación enviada al auditor de {asignacion.empresa}')
                    except Exception as e:
                        print(f'⚠️  Error al notificar al auditor: {e}')

                    mensaje = (
                        '¡Has completado todas las preguntas! '
                        'Tu evaluación fue cerrada y el Auditor fue notificado para revisión.'
                    )

                else:
                    pendientes = asignacion.total_preguntas - asignacion.preguntas_respondidas
                    mensaje    = (
                        f'Respuesta enviada. Te faltan {pendientes} preguntas '
                        f'({asignacion.porcentaje_avance:.0f}% completado)'
                    )

                from apps.asignaciones.serializers import AsignacionSerializer
                return self.success_response(
                    data={
                        'respuesta':           RespuestaDetailSerializer(respuesta_actualizada).data,
                        'asignacion':          AsignacionSerializer(asignacion).data,
                        'asignacion_completa': asignacion_completa,
                    },
                    message=mensaje,
                    status_code=status.HTTP_200_OK
                )

        except Exception as e:
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
        try:
            from apps.asignaciones.models import Asignacion
            asignacion = Asignacion.objects.get(id=asignacion_id)
        except Asignacion.DoesNotExist:
            return self.error_response(
                message='Asignación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        # ── Validar permisos ──────────────────────────────────────────────────
        if request.user.rol == 'superadmin':
            pass  # Acceso total
        elif request.user.rol in ['administrador', 'auditor']:
            # Admin y Auditor: solo su empresa
            if asignacion.empresa != request.user.empresa:
                return self.error_response(
                    message='No tienes permisos para ver esta asignación',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        else:
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
            'respondido_por',
            'auditado_por',          # ⭐ Para mostrar quién calificó
        ).prefetch_related(
            'evidencias'
        ).order_by('pregunta__orden')

        serializer = RespuestaDetailSerializer(queryset, many=True)

        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })
            
class AuditorViewSet(ResponseMixin, viewsets.GenericViewSet):
    """
    ViewSet exclusivo para el rol Auditor.

    Endpoints:
        GET  /api/auditor/mis_revisiones/              → Asignaciones pendientes de auditar
        POST /api/auditor/calificar/{respuesta_id}/    → Calificar una respuesta
        POST /api/auditor/cerrar_revision/{asig_id}/   → Cerrar revisión (GAP automático)
        GET  /api/auditor/historial/                   → Evaluaciones ya auditadas (con filtro de fecha)
        GET  /api/auditor/notificaciones/              → Notificaciones del auditor
    """
    permission_classes = [IsAuthenticated, EsAuditor]

    # ── mis_revisiones ────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def mis_revisiones(self, request):
        """
        Lista asignaciones completadas de la empresa del auditor.
        Incluye tanto las pendientes de revisar (completado) como las ya auditadas.
        """
        user = request.user

        qs = Asignacion.objects.filter(
            empresa=user.empresa,
            # ⭐ CORREGIDO: 'completado' en lugar de 'pendiente_auditoria'
            # El estado pasa a 'completado' cuando el usuario envía la última respuesta
            estado__in=['completado', 'pendiente_auditoria', 'auditado'],
            activo=True
        ).select_related(
            'dimension', 'usuario_asignado', 'encuesta', 'evaluacion_empresa'
        ).order_by('-fecha_completado')  # ⭐ Más recientes primero

        evaluacion_id = request.query_params.get('evaluacion_empresa_id')
        if evaluacion_id:
            qs = qs.filter(evaluacion_empresa_id=evaluacion_id)

        from apps.asignaciones.serializers import AsignacionSerializer
        return Response({
            'count':   qs.count(),
            'results': AsignacionSerializer(qs, many=True).data
        })

    # ── calificar ─────────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='calificar/(?P<respuesta_id>[^/.]+)')
    def calificar(self, request, respuesta_id=None):
        """
        El auditor califica una respuesta individual.

        Body:
        {
            "calificacion_auditor": "SI_CUMPLE" | "CUMPLE_PARCIAL" | "NO_CUMPLE",
            "comentarios_auditor": "...",
            "recomendaciones_auditor": "...",
            "nivel_madurez": 3.0
        }
        """
        try:
            respuesta = Respuesta.objects.select_related(
                'asignacion__empresa', 'asignacion__usuario_asignado'
            ).get(id=respuesta_id)
        except Respuesta.DoesNotExist:
            return self.error_response(
                message='Respuesta no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        # No calificar NO_APLICA
        if respuesta.respuesta == 'NO_APLICA':
            return self.error_response(
                message='Las respuestas marcadas como "No Aplica" no requieren calificación',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = AuditorCalificarSerializer(
            respuesta, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        respuesta_actualizada = serializer.save()

        return self.success_response(
            data=RespuestaDetailSerializer(respuesta_actualizada).data,
            message='Respuesta calificada exitosamente'
        )

    # ── cerrar_revision ───────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='cerrar_revision/(?P<asignacion_id>[^/.]+)')
    def cerrar_revision(self, request, asignacion_id=None):
        """
        Cierra la revisión de una asignación completa.
        - Las respuestas sin calificar pasan a NO_CUMPLE automáticamente.
        - GAP se calcula automáticamente.
        - Se notifica al administrador y usuario.

        Body (opcional):
        {
            "comentario_cierre": "Revisión completada. ..."
        }
        """
        try:
            asignacion = Asignacion.objects.select_related(
                'empresa', 'evaluacion_empresa', 'usuario_asignado'
            ).get(id=asignacion_id)
        except Asignacion.DoesNotExist:
            return self.error_response(
                message='Asignación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = AuditorCerrarRevisionSerializer(
            data=request.data,
            context={'request': request, 'asignacion': asignacion}
        )
        serializer.is_valid(raise_exception=True)
        resultado = serializer.save()

        return self.success_response(
            data=resultado,
            message='Revisión cerrada exitosamente. GAP calculado.'
        )

    # ── historial ─────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def historial(self, request):
        """
        Evaluaciones (asignaciones) ya auditadas por este auditor o de su empresa.

        Query params:
            fecha_desde  (YYYY-MM-DD)
            fecha_hasta  (YYYY-MM-DD)
            evaluacion_empresa_id
        """
        user = request.user

        qs = Asignacion.objects.filter(
            empresa=user.empresa,
            estado='completado',
            activo=True
        ).select_related(
            'dimension', 'usuario_asignado', 'encuesta', 'evaluacion_empresa'
        ).order_by('-fecha_completado')

        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        evaluacion_id = request.query_params.get('evaluacion_empresa_id')

        if fecha_desde:
            qs = qs.filter(fecha_completado__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_completado__date__lte=fecha_hasta)
        if evaluacion_id:
            qs = qs.filter(evaluacion_empresa_id=evaluacion_id)

        from apps.asignaciones.serializers import AsignacionSerializer
        return Response({
            'count':   qs.count(),
            'results': AsignacionSerializer(qs, many=True).data
        })

    # ── notificaciones ────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def notificaciones(self, request):
        """
        Notificaciones del auditor: evaluaciones cerradas/completadas
        de su empresa ordenadas por fecha.

        Query params:
            solo_no_leidas (bool)
            fecha_desde    (YYYY-MM-DD)
        """
        user = request.user

        try:
            from apps.notificaciones.models import Notificacion
            qs = Notificacion.objects.filter(
                usuario=user,
                activo=True
            ).order_by('-fecha_creacion')

            solo_no_leidas = request.query_params.get('solo_no_leidas', 'false').lower() == 'true'
            fecha_desde    = request.query_params.get('fecha_desde')

            if solo_no_leidas:
                qs = qs.filter(leida=False)
            if fecha_desde:
                qs = qs.filter(fecha_creacion__date__gte=fecha_desde)

            from apps.notificaciones.serializers import NotificacionSerializer
            return Response({
                'count':        qs.count(),
                'no_leidas':    qs.filter(leida=False).count(),
                'results':      NotificacionSerializer(qs, many=True).data
            })

        except Exception as e:
            return self.error_response(
                message='Error al obtener notificaciones',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )        
        
# ============================================
# VIEWSET: EVIDENCIAS
# ============================================

class EvidenciaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestionar evidencias con Supabase Storage
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser] 
    
    def get_queryset(self):
        user = self.request.user
        queryset = Evidencia.objects.select_related(
            'respuesta',
            'respuesta__asignacion',
            'respuesta__pregunta',
            'subido_por',
            'documento_oficial'
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
    
    # ⭐ CREAR: Subir a Supabase o Vincular Documento
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Subir evidencia o vincular documento maestro
        """
        # ===== 1. OBTENER Y VALIDAR DATOS =====
        respuesta_id = request.data.get('respuesta_id')
        archivo = request.FILES.get('archivo')
        documento_id = request.data.get('documento_id') # <--- NUEVO: ID del documento existente
        
        # Metadatos
        codigo_documento = request.data.get('codigo_documento', 'SIN-CODIGO')
        tipo_documento_enum = request.data.get('tipo_documento_enum', 'otro')
        titulo_documento = request.data.get('titulo_documento', 'Documento sin título')
        objetivo_documento = request.data.get('objetivo_documento', 'Sin objetivo especificado')
        
        if not respuesta_id:
            return self.error_response(message='respuesta_id es requerido', status_code=status.HTTP_400_BAD_REQUEST)
        
        # --- LÓGICA PRINCIPAL: Archivo Físico vs Documento Vinculado ---
        if not archivo and not documento_id:
            return self.error_response(
                message='Debe subir un archivo o seleccionar un documento existente',
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        # --- VARIABLES INICIALES ---
        path_supabase = None
        tamanio_bytes = 0
        nombre_original = ''
        doc_oficial_obj = None

        # CASO A: VINCULAR DOCUMENTO EXISTENTE
        if documento_id:
            try:
                doc_oficial_obj = Documento.objects.get(id=documento_id)
                
                # ⭐ NUEVO: Validación solicitada por el jefe (Solo VIGENTES)
                if doc_oficial_obj.estado != 'vigente':
                    return self.error_response(
                        message=f'No se puede vincular. El documento debe estar VIGENTE (Actual: {doc_oficial_obj.get_estado_display()}).',
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

                # Si el usuario no mandó datos específicos, heredamos del documento oficial
                if codigo_documento == 'SIN-CODIGO': 
                    codigo_documento = doc_oficial_obj.codigo
                if titulo_documento == 'Documento sin título': 
                    titulo_documento = doc_oficial_obj.titulo
                
                # Asignamos nombre original para referencia
                nombre_base = os.path.basename(str(doc_oficial_obj.archivo_pdf)) if doc_oficial_obj.archivo_pdf else f"{doc_oficial_obj.codigo}.pdf"
                nombre_original = f"VINCULADO: {nombre_base}"
                
            except Documento.DoesNotExist:
                 return self.error_response(message='El documento seleccionado no existe', status_code=404)

        # CASO B: SUBIR ARCHIVO NUEVO
        if archivo:
            # Validaciones de archivo
            if not Evidencia.validar_extension(archivo.name):
                return self.error_response(
                    message=f'Extensión no permitida. Válidas: {", ".join(Evidencia.EXTENSIONES_PERMITIDAS)}',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            if not Evidencia.validar_tamanio(archivo.size):
                return self.error_response(
                    message='El archivo no puede superar los 10MB',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # ===== 3. VALIDAR QUE LA RESPUESTA EXISTE =====
        try:
            respuesta = Respuesta.objects.select_related(
                'asignacion__empresa',
                'asignacion__usuario_asignado'
            ).get(id=respuesta_id)
        except Respuesta.DoesNotExist:
            return self.error_response(message='Respuesta no encontrada', status_code=status.HTTP_404_NOT_FOUND)
        
        # ===== 4. VALIDAR PERMISOS =====
        if respuesta.respondido_por != request.user:
            return self.error_response(message='No tienes permiso', status_code=status.HTTP_403_FORBIDDEN)
        
        if respuesta.estado != 'borrador':
            return self.error_response(message='Solo se pueden agregar evidencias en borrador', status_code=status.HTTP_400_BAD_REQUEST)
        
        if respuesta.evidencias.filter(activo=True).count() >= 3:
            return self.error_response(message='Máximo 3 evidencias por respuesta', status_code=status.HTTP_400_BAD_REQUEST)
        
        # ===== 5. SUBIR A SUPABASE (Solo si hay archivo físico) =====
        if archivo:
            storage = StorageService()
            folder = (
                f"evidencias/"
                f"empresa_{respuesta.asignacion.empresa.id}/"
                f"usuario_{respuesta.asignacion.usuario_asignado.id}/"
                f"respuesta_{respuesta_id}"
            )
            
            upload_result = storage.upload_file(file=archivo, folder=folder)
            
            if not upload_result['success']:
                return self.error_response(
                    message=f"Error en Supabase: {upload_result.get('error')}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            path_supabase = upload_result.get('path')
            tamanio_bytes = archivo.size
            nombre_original = archivo.name

        # ===== 6. CREAR REGISTRO EN BASE DE DATOS =====
        try:
            # Instanciamos primero para poder validar con full_clean()
            evidencia = Evidencia(
                respuesta=respuesta,
                archivo=path_supabase if path_supabase else 'VINCULADO_MAESTRO', 
                documento_oficial=doc_oficial_obj, 
                nombre_archivo_original=nombre_original,
                tamanio_bytes=tamanio_bytes,
                codigo_documento=codigo_documento,
                tipo_documento_enum=tipo_documento_enum,
                titulo_documento=titulo_documento,
                objetivo_documento=objetivo_documento,
                subido_por=request.user
            )
            # Forzamos la validación del modelo (esto verifica que no pase de 3 evidencias o le falten PDFs)
            evidencia.full_clean() 
            evidencia.save()
            
            # ===== 7. REGISTRAR EN HISTORIAL =====
            HistorialRespuesta.objects.create(
                respuesta=respuesta,
                tipo_cambio='agregado_evidencia',
                usuario=request.user,
                motivo=f'Evidencia agregada: {codigo_documento} - {titulo_documento}',
                ip_address=self._get_client_ip(),
                user_agent=self._get_user_agent()
            )
            
            # ===== 8. RETORNAR RESPUESTA =====
            serializer = EvidenciaSerializer(evidencia)
            return self.success_response(
                data=serializer.data,
                message='Evidencia agregada exitosamente',
                status_code=status.HTTP_201_CREATED
            )
            
        except ValidationError as e:
            # ⭐ AQUÍ ESTÁ LA SOLUCIÓN AL ERROR: Ahora devolvemos el mensaje exacto al frontend
            errores = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return self.error_response(
                message='Error de validación al vincular el documento',
                errors=errores,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return self.error_response(
                message='Error interno al procesar la evidencia',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def verificar_codigo(self, request):
        """
        Verificar si un código de documento ya existe
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        codigo_documento = serializer.validated_data['codigo_documento']
        user = request.user
        
        evidencias_existentes = Evidencia.buscar_por_codigo(
            codigo_documento,
            user.empresa
        )
        
        if not evidencias_existentes.exists():
            return Response({
                'existe': False,
                'evidencias_encontradas': [],
                'mensaje': 'No se encontraron documentos con este código'
            })
        
        evidencias_data = []
        for evidencia in evidencias_existentes:
            evidencias_data.append({
                'id': str(evidencia.id),
                'codigo_documento': evidencia.codigo_documento,
                'titulo_documento': evidencia.titulo_documento,
                'tipo_documento_display': evidencia.get_tipo_documento_enum_display(),
                'subido_por': evidencia.subido_por.nombre_completo if evidencia.subido_por else 'Desconocido',
                'fecha_creacion': evidencia.fecha_creacion.strftime('%Y-%m-%d'),
            })
        
        return Response({
            'existe': True,
            'evidencias_encontradas': evidencias_data,
            'mensaje': f'Se encontraron {len(evidencias_data)} documentos con este código'
        })
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Eliminar evidencia
        """
        instance = self.get_object()
        respuesta = instance.respuesta
        
        if respuesta.estado != 'borrador':
            return self.error_response(
                message='Solo se pueden eliminar evidencias de respuestas en borrador',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if respuesta.respondido_por != request.user:
            return self.error_response(
                message='Solo puedes eliminar evidencias de tus propias respuestas',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Eliminar de Supabase (solo si tiene archivo físico y NO es un documento vinculado)
        if instance.archivo and not instance.documento_oficial and instance.archivo != 'VINCULADO_MAESTRO':
            storage = StorageService()
            delete_result = storage.delete_file(instance.archivo)
            if not delete_result['success']:
                print(f"⚠️ Advertencia: No se pudo eliminar archivo de Supabase")
        
        HistorialRespuesta.objects.create(
            respuesta=respuesta,
            tipo_cambio='eliminado_evidencia',
            usuario=request.user,
            motivo=f'Evidencia eliminada: {instance.codigo_documento}',
            ip_address=self._get_client_ip(),
            user_agent=self._get_user_agent()
        )
        
        instance.delete()
        
        return self.success_response(
            message='Evidencia eliminada exitosamente',
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    # ===== MÉTODOS AUXILIARES ESTANDARIZADOS =====
    def _get_client_ip(self, request=None):
        if not request:
            request = self.request
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _get_user_agent(self, request=None):
        if not request:
            request = self.request
        return request.META.get('HTTP_USER_AGENT', '')[:255]


# ============================================
# VIEWSET: HISTORIAL DE RESPUESTAS
# ============================================

class HistorialRespuestaViewSet(ResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver historial de cambios
    """
    permission_classes = [IsAuthenticated]
    serializer_class = HistorialRespuestaSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = HistorialRespuesta.objects.select_related(
            'respuesta',
            'usuario'
        )
        
        respuesta_id = self.request.query_params.get('respuesta')
        if respuesta_id:
            queryset = queryset.filter(respuesta_id=respuesta_id)
        
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
    ViewSet para cálculos de nivel de madurez
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CalculoNivelSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = CalculoNivel.objects.select_related(
            'asignacion',
            'dimension'
        )
        
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
        """
        user = request.user
        
        if user.rol not in ['superadmin', 'administrador']:
            return self.error_response(
                message='No tienes permisos para ver esta información',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        calculos = self.get_queryset()
        
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
        """
        calculos = self.get_queryset()
        
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