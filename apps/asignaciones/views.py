# apps/asignaciones/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q

from .models import Asignacion
from .serializers import (
    AsignacionSerializer,
    AsignacionListSerializer,
    AsignacionEvaluacionCompletaSerializer,
    AsignacionEvaluacionCompletaSerializer,
    AsignacionDimensionSerializer,
    ReasignarSerializer,
    ActualizarProgresoSerializer,
    RevisarAsignacionSerializer
)
from apps.encuestas.models import Encuesta, Dimension, EvaluacionEmpresa  
from apps.empresas.models import Empresa
from django.utils import timezone
from apps.usuarios.models import Usuario
from apps.core.permissions import EsSuperAdmin, EsAdminOSuperAdmin
from apps.core.mixins import ResponseMixin

# Importar servicio de notificaciones
from apps.notificaciones.services import NotificacionAsignacionService
from apps.respuestas.services import CalculoNivelService

class AsignacionViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de asignaciones
    
    FUNCIONALIDADES:
    1. SuperAdmin asigna evaluaciones completas a Administradores
    2. Administrador asigna dimensiones específicas a Usuarios de su empresa
    3. Notificaciones automáticas al asignar
    4. Tracking de progreso
    
    ENDPOINTS:
    - GET    /api/asignaciones/                     → Listar asignaciones
    - POST   /api/asignaciones/asignar_evaluacion/  → SuperAdmin asigna evaluación completa
    - POST   /api/asignaciones/asignar_dimension/   → Admin asigna dimensión
    - GET    /api/asignaciones/mis_asignaciones/    → Ver mis asignaciones
    - GET    /api/asignaciones/{id}/                → Detalle de asignación
    - POST   /api/asignaciones/{id}/reasignar/      → Reasignar a otro usuario
    - GET    /api/asignaciones/estadisticas/        → Estadísticas
    """
    queryset = Asignacion.objects.select_related(
        'encuesta', 'dimension', 'usuario_asignado', 'empresa', 'asignado_por'
    ).all()
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch']  # No DELETE
    
    def get_serializer_class(self):
        if self.action == 'list' or self.action == 'mis_asignaciones':
            return AsignacionListSerializer
        if self.action == 'asignar_evaluacion':
            return AsignacionEvaluacionCompletaSerializer
        if self.action == 'asignar_dimension':
            return AsignacionDimensionSerializer
        if self.action == 'reasignar':
            return ReasignarSerializer
        if self.action == 'actualizar_progreso':
            return ActualizarProgresoSerializer
        if self.action == 'revisar':
            return RevisarAsignacionSerializer
        return AsignacionSerializer
    
    def get_queryset(self):
        """Filtrar asignaciones según rol"""
        user = self.request.user
        queryset = Asignacion.objects.select_related(
            'evaluacion_empresa',
            'encuesta', 'dimension', 'usuario_asignado', 'empresa', 'asignado_por'
        ).filter(activo=True)
        
        # SuperAdmin ve TODAS
        if user.rol == 'superadmin':
            return queryset
        
        # Administrador ve asignaciones de su empresa
        if user.rol == 'administrador' and user.empresa:
            return queryset.filter(
                Q(evaluacion_empresa__administrador=user) |  
                Q(empresa=user.empresa, evaluacion_empresa__isnull=True)  # ⭐ Compatibilidad: Asignaciones antiguas
            )
        
        # Usuario/Auditor solo ve sus propias asignaciones
        return queryset.filter(usuario_asignado=user)
    
    def get_permissions(self):
        """Permisos específicos por acción"""
        if self.action == 'asignar_evaluacion':
            return [IsAuthenticated(), EsSuperAdmin()]
        if self.action in ['asignar_dimension', 'reasignar']:
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        return [IsAuthenticated()]
    
    # =========================================================================
    # ASIGNAR EVALUACIÓN COMPLETA (SuperAdmin → Administrador)
    # =========================================================================
    
    @action(detail=False, methods=['post'])
    def asignar_evaluacion(self, request):
        """
        SuperAdmin asigna evaluación completa a un Administrador
        POST /api/asignaciones/asignar_evaluacion/
        
        Body:
        {
            "encuesta_id": "uuid",
            "administrador_id": 123,
            "fecha_limite": "2024-12-31",
            "observaciones": "Prioridad alta"
        }
        
        PERMISOS: Solo SuperAdmin
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                encuesta = Encuesta.objects.get(id=serializer.validated_data['encuesta_id'])
                administrador = Usuario.objects.get(id=serializer.validated_data['administrador_id'])
                
                # Crear asignación de EVALUACIÓN COMPLETA (sin dimensión específica)
                asignacion = Asignacion.objects.create(
                    encuesta=encuesta,
                    dimension=None,  # NULL indica que es evaluación completa
                    usuario_asignado=administrador,
                    empresa=administrador.empresa,
                    asignado_por=request.user,
                    fecha_limite=serializer.validated_data['fecha_limite'],
                    observaciones=serializer.validated_data.get('observaciones', ''),
                    estado='pendiente',
                    total_preguntas=encuesta.total_preguntas,
                    preguntas_respondidas=0,
                    porcentaje_avance=0
                )
                
                # 🔔 ENVIAR NOTIFICACIÓN
                NotificacionAsignacionService.notificar_asignacion_evaluacion(asignacion)
                
            return self.error_response(
                message='Este endpoint está deprecado. Use /api/evaluaciones-empresa/asignar/ para asignar evaluaciones.',
                status_code=status.HTTP_410_GONE
            )
        
        except Exception as e:
            return self.error_response(
                message='Error al asignar evaluación',
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    # =========================================================================
    # ASIGNAR DIMENSIÓN (Administrador → Usuario de su empresa)
    # =========================================================================
    
    @action(detail=False, methods=['post'])
    def asignar_dimension(self, request):
        """
        Administrador asigna dimensiones a un Usuario
        POST /api/asignaciones/asignar_dimension/
        
        Body:
        {
            "evaluacion_empresa_id": "uuid",  // ⭐ NUEVO - REQUERIDO
            "dimension_ids": ["uuid1", "uuid2"],
            "usuario_id": 456,
            "fecha_limite": "2024-12-31",
            "observaciones": "Revisar urgente",
            "requiere_revision": true
        }
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                # ⭐ OBTENER EVALUACION EMPRESA
                evaluacion_empresa = EvaluacionEmpresa.objects.get(
                    id=serializer.validated_data['evaluacion_empresa_id']
                )
                
                # Validar permisos
                user = request.user
                if user.rol == 'administrador':
                    if evaluacion_empresa.administrador != user:
                        return self.error_response(
                            message='Solo puedes asignar dimensiones de tus evaluaciones',
                            status_code=status.HTTP_403_FORBIDDEN
                        )
                
                dimension_ids = serializer.validated_data['dimension_ids']
                usuario = Usuario.objects.get(id=serializer.validated_data['usuario_id'])
                fecha_limite = serializer.validated_data['fecha_limite']
                observaciones = serializer.validated_data.get('observaciones', '')
                requiere_revision = serializer.validated_data.get('requiere_revision', False)
                
                asignaciones_creadas = []
                
                for dimension_id in dimension_ids:
                    dimension = Dimension.objects.get(id=dimension_id)
                    
                    # ⭐ CREAR CON evaluacion_empresa
                    asignacion = Asignacion.objects.create(
                        evaluacion_empresa=evaluacion_empresa,  # ⭐ NUEVO
                        encuesta=evaluacion_empresa.encuesta,
                        dimension=dimension,
                        usuario_asignado=usuario,
                        empresa=usuario.empresa,
                        asignado_por=request.user,
                        fecha_limite=fecha_limite,
                        observaciones=observaciones,
                        requiere_revision=requiere_revision,
                        estado='pendiente',
                        total_preguntas=dimension.total_preguntas,
                        preguntas_respondidas=0,
                        porcentaje_avance=0
                    )
                    
                    asignaciones_creadas.append(asignacion)
                    NotificacionAsignacionService.notificar_asignacion_dimension(asignacion)
                
                # ⭐ ACTUALIZAR PROGRESO DE LA EVALUACIÓN
                evaluacion_empresa.actualizar_progreso()
                
                mensaje_extra = ' Estas asignaciones requerirán tu revisión.' if requiere_revision else ''
                
                return self.success_response(
                    data={
                        'asignaciones': [AsignacionSerializer(a).data for a in asignaciones_creadas],
                        'total_asignadas': len(asignaciones_creadas),
                        'evaluacion': {  # ⭐ NUEVO
                            'id': str(evaluacion_empresa.id),
                            'nombre': evaluacion_empresa.encuesta.nombre,
                            'porcentaje_avance': float(evaluacion_empresa.porcentaje_avance)
                        }
                    },
                    message=f'{len(asignaciones_creadas)} dimensión(es) asignada(s) exitosamente a {usuario.nombre_completo}.{mensaje_extra}',
                    status_code=status.HTTP_201_CREATED
                )
        
        except EvaluacionEmpresa.DoesNotExist:
            return self.error_response(
                message='Evaluación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.error_response(
                message='Error al asignar dimensiones',
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    # ⭐ NUEVO ENDPOINT: Obtener dimensiones disponibles para asignar
    @action(detail=False, methods=['get'])
    def dimensiones_disponibles(self, request):
        """
        Obtener dimensiones disponibles para asignar
        GET /api/asignaciones/dimensiones_disponibles/?evaluacion_empresa_id=xxx
        """
        evaluacion_empresa_id = request.query_params.get('evaluacion_empresa_id')
        
        if not evaluacion_empresa_id:
            return self.error_response(
                message='Debes proporcionar evaluacion_empresa_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            evaluacion_empresa = EvaluacionEmpresa.objects.get(id=evaluacion_empresa_id)
            
            # Validar permisos
            user = request.user
            if user.rol == 'administrador':
                if evaluacion_empresa.administrador != user:
                    return self.error_response(
                        message='No tienes acceso a esta evaluación',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            
            # Dimensiones de la encuesta
            dimensiones_encuesta = Dimension.objects.filter(
                encuesta=evaluacion_empresa.encuesta,
                activo=True
            ).order_by('orden')
            
            # ⭐ Dimensiones ya asignadas en ESTA evaluación específica
            dimensiones_asignadas = Asignacion.objects.filter(
                evaluacion_empresa=evaluacion_empresa,  # ⭐ CAMBIO CLAVE
                activo=True,
                dimension__isnull=False
            ).values_list('dimension_id', flat=True)
            
            # Dimensiones disponibles
            dimensiones_disponibles = dimensiones_encuesta.exclude(
                id__in=dimensiones_asignadas
            )
            
            from apps.encuestas.serializers import DimensionListSerializer
            
            return Response({
                'evaluacion': {  # ⭐ NUEVO
                    'id': str(evaluacion_empresa.id),
                    'nombre': evaluacion_empresa.encuesta.nombre,
                    'empresa': evaluacion_empresa.empresa.nombre,
                },
                'total_dimensiones': dimensiones_encuesta.count(),
                'dimensiones_asignadas': len(dimensiones_asignadas),
                'dimensiones_disponibles': dimensiones_disponibles.count(),
                'dimensiones': DimensionListSerializer(dimensiones_disponibles, many=True).data,
                'detalle_asignaciones': self._get_detalle_asignaciones(evaluacion_empresa)
            })
        
        except EvaluacionEmpresa.DoesNotExist:
            return self.error_response(
                message='Evaluación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

    def _get_detalle_asignaciones(self, evaluacion_empresa):  # ✅ MANTENER ESTA
        """Detalle de quién tiene asignada cada dimensión"""
        asignaciones = Asignacion.objects.filter(
            evaluacion_empresa=evaluacion_empresa,
            activo=True,
            dimension__isnull=False
        ).select_related('dimension', 'usuario_asignado')
        
        detalle = []
        for asignacion in asignaciones:
            detalle.append({
                'dimension_id': str(asignacion.dimension.id),
                'dimension_nombre': asignacion.dimension.nombre,
                'dimension_codigo': asignacion.dimension.codigo,
                'asignado_a': asignacion.usuario_asignado.nombre_completo,
                'usuario_id': asignacion.usuario_asignado.id,
                'estado': asignacion.estado,
                'porcentaje_avance': float(asignacion.porcentaje_avance)
            })
        
        return detalle

    # =========================================================================
    # MIS ASIGNACIONES
    # =========================================================================
    
    @action(detail=False, methods=['get'])
    def mis_asignaciones(self, request):
        """
        Ver mis propias asignaciones
        GET /api/asignaciones/mis_asignaciones/?estado=pendiente&tipo=dimension
        
        Query params:
        - estado: pendiente, en_progreso, completado, vencido
        - tipo: evaluacion_completa, dimension
        """
        user = request.user
        queryset = Asignacion.objects.filter(
            usuario_asignado=user,
            activo=True
        ).select_related('encuesta', 'dimension', 'empresa', 'asignado_por')
        
        # Filtros opcionales
        estado = request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        tipo = request.query_params.get('tipo')
        if tipo == 'evaluacion_completa':
            queryset = queryset.filter(dimension__isnull=True)
        elif tipo == 'dimension':
            queryset = queryset.filter(dimension__isnull=False)
        
        # Ordenar por fecha límite (más próximas primero)
        queryset = queryset.order_by('fecha_limite', '-fecha_asignacion')
        
        serializer = AsignacionListSerializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })
    
    # =========================================================================
    # REASIGNAR
    # =========================================================================
    
    @action(detail=True, methods=['post'])
    def reasignar(self, request, pk=None):
        """
        Reasignar asignación a otro usuario
        POST /api/asignaciones/{id}/reasignar/
        
        Body:
        {
            "nuevo_usuario_id": 789,
            "nueva_fecha_limite": "2024-12-31",
            "motivo": "Usuario no disponible"
        }
        """
        asignacion = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                nuevo_usuario = Usuario.objects.get(
                    id=serializer.validated_data['nuevo_usuario_id']
                )
                
                # Validar permisos
                user = request.user
                if user.rol == 'administrador':
                    if nuevo_usuario.empresa != user.empresa:
                        return self.error_response(
                            message='Solo puedes reasignar a usuarios de tu empresa',
                            status_code=status.HTTP_403_FORBIDDEN
                        )
                
                # Actualizar asignación
                asignacion.usuario_asignado = nuevo_usuario
                asignacion.empresa = nuevo_usuario.empresa
                
                if serializer.validated_data.get('nueva_fecha_limite'):
                    asignacion.fecha_limite = serializer.validated_data['nueva_fecha_limite']
                
                motivo = serializer.validated_data.get('motivo', '')
                asignacion.observaciones += f"\n[REASIGNADO] {motivo}"
                asignacion.save()
                
                # 🔔 NOTIFICAR al nuevo usuario
                if asignacion.dimension:
                    NotificacionAsignacionService.notificar_asignacion_dimension(asignacion)
                else:
                    NotificacionAsignacionService.notificar_asignacion_evaluacion(asignacion)
                
                return self.success_response(
                    data=AsignacionSerializer(asignacion).data,
                    message=f'Asignación reasignada a {nuevo_usuario.nombre_completo}'
                )
        
        except Exception as e:
            return self.error_response(
                message='Error al reasignar',
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    # =========================================================================
    # ESTADÍSTICAS
    # =========================================================================
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas de asignaciones
        GET /api/asignaciones/estadisticas/
        """
        user = request.user
        
        if user.rol == 'superadmin':
            queryset = Asignacion.objects.filter(activo=True)
        elif user.rol == 'administrador' and user.empresa:
            queryset = Asignacion.objects.filter(empresa=user.empresa, activo=True)
        else:
            queryset = Asignacion.objects.filter(usuario_asignado=user, activo=True)
        
        total = queryset.count()
        pendientes = queryset.filter(estado='pendiente').count()
        en_progreso = queryset.filter(estado='en_progreso').count()
        completadas = queryset.filter(estado='completado').count()
        vencidas = queryset.filter(estado='vencido').count()
        
        # Evaluaciones vs Dimensiones
        evaluaciones_completas = queryset.filter(dimension__isnull=True).count()
        dimensiones = queryset.filter(dimension__isnull=False).count()
        
        return Response({
            'total_asignaciones': total,
            'por_estado': {
                'pendientes': pendientes,
                'en_progreso': en_progreso,
                'completadas': completadas,
                'vencidas': vencidas
            },
            'por_tipo': {
                'evaluaciones_completas': evaluaciones_completas,
                'dimensiones_especificas': dimensiones
            },
            'porcentaje_completado': round((completadas / total * 100) if total > 0 else 0, 2)
        })
        
    # =========================================================================
    # ⭐ NUEVO ENDPOINT: REVISAR ASIGNACIÓN
    # =========================================================================
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def revisar(self, request, pk=None):
        """
        Aprobar o rechazar una asignación que requiere revisión
        POST /api/asignaciones/{id}/revisar/
        
        Body:
        {
            "accion": "aprobar" | "rechazar",
            "comentarios": "Observaciones del revisor"
        }
        
        PERMISOS: SuperAdmin o Administrador de la empresa
        """
        asignacion = self.get_object()
        
        # ⭐ DEBUG
        print(f"🔍 ANTES - Asignación ID: {asignacion.id}")
        print(f"   Estado actual: {asignacion.estado}")
        print(f"   Requiere revisión: {asignacion.requiere_revision}")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validar que la asignación requiera revisión
        if not asignacion.requiere_revision:
            return self.error_response(
                message='Esta asignación no requiere revisión',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if asignacion.estado != 'pendiente_revision':
            return self.error_response(
                message=f'La asignación debe estar en estado "Pendiente de Revisión". Estado actual: {asignacion.get_estado_display()}',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if request.user.rol == 'administrador':
            if asignacion.empresa != request.user.empresa:
                return self.error_response(
                    message='Solo puedes revisar asignaciones de tu empresa',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        try:
            with transaction.atomic():
                accion = serializer.validated_data['accion']
                comentarios = serializer.validated_data.get('comentarios', '')
                
                asignacion.revisado_por = request.user
                asignacion.fecha_revision = timezone.now()
                asignacion.comentarios_revision = comentarios
                
                if accion == 'aprobar':
                    asignacion.estado = 'completado'
                    asignacion.fecha_completado = timezone.now()
                    mensaje = f'Asignación aprobada exitosamente'
                    
                    # 🔔 Notificar al usuario que fue aprobada
                    NotificacionAsignacionService.notificar_revision_aprobada(asignacion)
                
                else:  # rechazar
                    asignacion.estado = 'rechazado'
                    asignacion.preguntas_respondidas = 0  # Resetear para que vuelva a responder
                    asignacion.porcentaje_avance = 0
                    mensaje = f'Asignación rechazada. El usuario deberá completarla nuevamente.'
                    
                    # 🔔 Notificar al usuario que fue rechazada
                    NotificacionAsignacionService.notificar_revision_rechazada(asignacion)
                
                asignacion.save()
                
                # ⭐ DEBUG
                print(f"✅ DESPUÉS - Asignación ID: {asignacion.id}")
                print(f"   Nuevo estado: {asignacion.estado}")
                print(f"   Acción: {accion}")
                
                # ⭐ VERIFICAR EN BASE DE DATOS
                asignacion.refresh_from_db()
                print(f"🔄 VERIFICACIÓN DB - Estado en DB: {asignacion.estado}")
                
                return self.success_response(
                    data=AsignacionSerializer(asignacion).data,
                    message=mensaje
                )
        
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return self.error_response(
                message='Error al procesar la revisión',
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
    # =========================================================================
    # ⭐ NUEVO ENDPOINT: LISTAR ASIGNACIONES PENDIENTES DE REVISIÓN
    # =========================================================================
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def pendientes_revision(self, request):
        """
        Listar asignaciones pendientes de revisión
        GET /api/asignaciones/pendientes_revision/
        
        PERMISOS: SuperAdmin o Administrador
        """
        user = request.user
        
        queryset = Asignacion.objects.filter(
            estado='pendiente_revision',
            requiere_revision=True,
            activo=True
        ).select_related(
            'encuesta', 'dimension', 'usuario_asignado', 'empresa', 'asignado_por'
        )
        
        # Filtrar por empresa si es administrador
        if user.rol == 'administrador':
            if not user.empresa:
                return self.error_response(
                    message='Tu usuario no tiene empresa asignada',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            queryset = queryset.filter(empresa=user.empresa)
        
        # Ordenar por fecha de envío (más antiguas primero)
        queryset = queryset.order_by('fecha_envio_revision')
        
        # ⭐ CAMBIO: Usar AsignacionListSerializer en lugar de AsignacionSerializer
        serializer = AsignacionListSerializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })
    
    # Actualizar endpoint de estadísticas
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas de asignaciones"""
        user = request.user
        
        if user.rol == 'superadmin':
            queryset = Asignacion.objects.filter(activo=True)
        elif user.rol == 'administrador' and user.empresa:
            queryset = Asignacion.objects.filter(empresa=user.empresa, activo=True)
        else:
            queryset = Asignacion.objects.filter(usuario_asignado=user, activo=True)
        
        total = queryset.count()
        pendientes = queryset.filter(estado='pendiente').count()
        en_progreso = queryset.filter(estado='en_progreso').count()
        completadas = queryset.filter(estado='completado').count()
        vencidas = queryset.filter(estado='vencido').count()
        pendientes_revision = queryset.filter(estado='pendiente_revision').count()  # ⭐ NUEVO
        rechazadas = queryset.filter(estado='rechazado').count()  # ⭐ NUEVO
        
        evaluaciones_completas = queryset.filter(dimension__isnull=True).count()
        dimensiones = queryset.filter(dimension__isnull=False).count()
        
        return Response({
            'total_asignaciones': total,
            'por_estado': {
                'pendientes': pendientes,
                'en_progreso': en_progreso,
                'completadas': completadas,
                'vencidas': vencidas,
                'pendientes_revision': pendientes_revision,  # ⭐ NUEVO
                'rechazadas': rechazadas  # ⭐ NUEVO
            },
            'por_tipo': {
                'evaluaciones_completas': evaluaciones_completas,
                'dimensiones_especificas': dimensiones
            },
            'porcentaje_completado': round((completadas / total * 100) if total > 0 else 0, 2)
        })