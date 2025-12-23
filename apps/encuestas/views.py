# apps/encuestas/views.py - VERSIÓN SIMPLIFICADA SOLO EDICIÓN

from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.db import transaction

from apps.asignaciones.models import Asignacion

from .models import (
    Encuesta, Dimension, Pregunta, 
    NivelReferencia, ConfigNivelDeseado
)
from .serializers import (
    EncuestaAdminSerializer, EncuestaSerializer, EncuestaListSerializer,
    DimensionSerializer, DimensionListSerializer, DimensionConPreguntasSerializer,
    PreguntaSerializer, PreguntaListSerializer,
    NivelReferenciaSerializer,
    ConfigNivelDeseadoSerializer,
    CargaExcelSerializer
)
from .utils import CargadorExcel
from apps.core.permissions import (
    EsAdminOSuperAdmin, 
    EsSuperAdmin, 
    EsAuditor,
    EsAdminOSuperAdminOAuditor
)
from apps.core.mixins import ResponseMixin


# =============================================================================
# VIEWSET PARA ENCUESTAS
# =============================================================================

class EncuestaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de encuestas - SOLO LECTURA Y EDICIÓN
    
    ENDPOINTS DISPONIBLES:
    - GET    /api/encuestas/                    → Listar encuestas
    - GET    /api/encuestas/{id}/               → Detalle de encuesta
    - PATCH  /api/encuestas/{id}/               → Editar encuesta (SuperAdmin)
    - POST   /api/encuestas/cargar_excel/       → Cargar desde Excel (SuperAdmin)
    - GET    /api/encuestas/descargar_plantilla/ → Descargar plantilla Excel
    - POST   /api/encuestas/{id}/duplicar/      → Duplicar encuesta (SuperAdmin)
    - POST   /api/encuestas/{id}/toggle_estado/ → Activar/Desactivar (SuperAdmin)
    - GET    /api/encuestas/{id}/estadisticas/  → Estadísticas
    
    PERMISOS:
    - SuperAdmin: Puede editar, cargar, duplicar
    - Administrador/Auditor: Solo lectura de encuestas asignadas a su empresa
    - Usuario: Sin acceso
    """
    queryset = Encuesta.objects.prefetch_related('dimensiones__preguntas__niveles_referencia').all()
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'post']  # Solo GET, PATCH y POST (no PUT, no DELETE, no CREATE via POST /)
    
    def get_serializer_class(self):
        """
        Retornar serializer según el rol del usuario y la acción
        """
        user = self.request.user
        
        # Para carga de Excel
        if self.action == 'cargar_excel':
            return CargaExcelSerializer
        
        # Para listado
        if self.action == 'list':
            return EncuestaListSerializer
        
        # ⭐ AGREGAR ESTE BLOQUE
        # Para retrieve (detalle)
        if self.action == 'retrieve':
            # Administradores NO deben ver niveles ni recomendaciones
            if user.rol == 'administrador':
                return EncuestaAdminSerializer
            # SuperAdmin y Auditores SÍ ven niveles completos
            return EncuestaSerializer
        
        # Para otras acciones
        return EncuestaSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Encuesta.objects.prefetch_related('dimensiones__preguntas__niveles_referencia').all()
        
        # SuperAdmin ve TODAS las encuestas
        if user.rol == 'superadmin':
            return queryset
        
        # Administrador y Auditor: Solo encuestas asignadas a su empresa
        if user.rol in ['administrador', 'auditor']:
            if not user.empresa:
                return queryset.none()
            
            try:
                from apps.asignaciones.models import Asignacion
                encuestas_ids = Asignacion.objects.filter(
                    empresa=user.empresa
                ).values_list('encuesta_id', flat=True).distinct()
                return queryset.filter(id__in=encuestas_ids, activo=True)
            except ImportError:
                return queryset.filter(activo=True)
        
        # Usuario: SIN ACCESO
        return queryset.none()
    
    def get_permissions(self):
        # EDICIÓN: Solo SuperAdmin
        if self.action in ['update', 'partial_update', 'cargar_excel', 'duplicar', 'toggle_estado']:
            return [IsAuthenticated(), EsSuperAdmin()]
        
        # Lectura: SuperAdmin, Admin, Auditor
        if self.action in ['list', 'retrieve', 'estadisticas', 'descargar_plantilla']:
            return [IsAuthenticated(), EsAdminOSuperAdminOAuditor()]
        
        return [IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        """Bloquear creación manual - solo se permite vía cargar_excel"""
        return self.error_response(
            message='No se puede crear encuestas manualmente. Use el endpoint /cargar_excel/',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Bloquear eliminación - mantener historial"""
        return self.error_response(
            message='No se permite eliminar encuestas. Use toggle_estado para desactivar.',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def update(self, request, *args, **kwargs):
        """Actualizar encuesta - SOLO PATCH (parcial)"""
        if request.method == 'PUT':
            return self.error_response(
                message='Use PATCH para actualización parcial',
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return self.success_response(
            data=serializer.data,
            message='Encuesta actualizada exitosamente'
        )
    
    @action(detail=False, methods=['post'])
    def cargar_excel(self, request):
        """
        Cargar encuesta desde archivo Excel
        POST /api/encuestas/cargar_excel/
        
        PERMISO: Solo SuperAdmin
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            cargador = CargadorExcel(
                archivo_excel=serializer.validated_data['archivo'],
                nombre_encuesta=serializer.validated_data['nombre_encuesta'],
                version=serializer.validated_data.get('version', '1.0'),
                descripcion=serializer.validated_data.get('descripcion', '')
            )
            
            encuesta = cargador.procesar_y_guardar()
            
            return self.success_response(
                data=EncuestaSerializer(encuesta).data,
                message=f'Encuesta cargada exitosamente. {encuesta.total_preguntas} preguntas en {encuesta.total_dimensiones} dimensiones.',
                status_code=status.HTTP_201_CREATED
            )
        except Exception as e:
            return self.error_response(
                message='Error al procesar el archivo Excel',
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def descargar_plantilla(self, request):
        """
        Descargar plantilla Excel vacía
        GET /api/encuestas/descargar_plantilla/
        """
        try:
            archivo = CargadorExcel.generar_plantilla_excel()
            response = HttpResponse(
                archivo.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="plantilla_encuesta.xlsx"'
            return response
        except Exception as e:
            return self.error_response(
                message='Error al generar plantilla',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def duplicar(self, request, pk=None):
        """
        Duplicar encuesta completa
        POST /api/encuestas/{id}/duplicar/
        Body: {"nombre": "Nuevo Nombre", "version": "2.0"}
        
        PERMISO: Solo SuperAdmin
        """
        encuesta_original = self.get_object()
        nombre_nuevo = request.data.get('nombre')
        version_nueva = request.data.get('version', '1.0')
        
        if not nombre_nuevo:
            return self.error_response(
                message='Debes proporcionar un nombre para la nueva encuesta',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                nueva_encuesta = Encuesta.objects.create(
                    nombre=nombre_nuevo,
                    descripcion=encuesta_original.descripcion,
                    version=version_nueva,
                    es_plantilla=True,
                    activo=True
                )
                
                for dimension in encuesta_original.dimensiones.all():
                    nueva_dimension = Dimension.objects.create(
                        encuesta=nueva_encuesta,
                        codigo=dimension.codigo,
                        nombre=dimension.nombre,
                        descripcion=dimension.descripcion,
                        orden=dimension.orden,
                        activo=True
                    )
                    
                    for pregunta in dimension.preguntas.all():
                        nueva_pregunta = Pregunta.objects.create(
                            dimension=nueva_dimension,
                            codigo=pregunta.codigo,
                            titulo=pregunta.titulo,
                            texto=pregunta.texto,
                            peso=pregunta.peso,
                            obligatoria=pregunta.obligatoria,
                            orden=pregunta.orden,
                            activo=True
                        )
                        
                        for nivel in pregunta.niveles_referencia.all():
                            NivelReferencia.objects.create(
                                pregunta=nueva_pregunta,
                                numero=nivel.numero,
                                descripcion=nivel.descripcion,
                                recomendaciones=nivel.recomendaciones,
                                activo=True
                            )
            
            return self.success_response(
                data=EncuestaSerializer(nueva_encuesta).data,
                message='Encuesta duplicada exitosamente',
                status_code=status.HTTP_201_CREATED
            )
        except Exception as e:
            return self.error_response(
                message='Error al duplicar encuesta',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def toggle_estado(self, request, pk=None):
        """
        Activar/Desactivar encuesta
        POST /api/encuestas/{id}/toggle_estado/
        
        PERMISO: Solo SuperAdmin
        """
        encuesta = self.get_object()
        encuesta.activo = not encuesta.activo
        encuesta.save()
        
        mensaje = 'Encuesta activada' if encuesta.activo else 'Encuesta desactivada'
        return self.success_response(
            data=EncuestaSerializer(encuesta).data,
            message=f'{mensaje} exitosamente'
        )
    
    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        """
        Estadísticas de asignaciones de la encuesta
        GET /api/encuestas/{id}/estadisticas/
        """
        encuesta = self.get_object()
        user = request.user
        
        try:
            from apps.asignaciones.models import Asignacion
            
            if user.rol == 'superadmin':
                asignaciones = Asignacion.objects.filter(encuesta=encuesta)
            elif user.empresa:
                asignaciones = Asignacion.objects.filter(
                    encuesta=encuesta,
                    empresa=user.empresa
                )
            else:
                asignaciones = Asignacion.objects.none()
            
            stats = {
                'total_dimensiones': encuesta.total_dimensiones,
                'total_preguntas': encuesta.total_preguntas,
                'asignaciones': {
                    'total': asignaciones.count(),
                    'pendientes': asignaciones.filter(estado='pendiente').count(),
                    'en_progreso': asignaciones.filter(estado='en_progreso').count(),
                    'completadas': asignaciones.filter(estado='completado').count(),
                    'vencidas': asignaciones.filter(estado='vencido').count(),
                }
            }
        except ImportError:
            stats = {
                'total_dimensiones': encuesta.total_dimensiones,
                'total_preguntas': encuesta.total_preguntas,
                'asignaciones': {
                    'total': 0,
                    'pendientes': 0,
                    'en_progreso': 0,
                    'completadas': 0,
                    'vencidas': 0,
                }
            }
        
        return Response(stats)


# =============================================================================
# VIEWSET PARA DIMENSIONES
# =============================================================================

# apps/encuestas/views.py

class DimensionViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de dimensiones - SOLO LECTURA Y EDICIÓN
    
    ENDPOINTS:
    - GET    /api/dimensiones/                     → Listar dimensiones (?encuesta_id=xxx)
    - GET    /api/dimensiones/{id}/                → Detalle de dimensión
    - GET    /api/dimensiones/{id}/con_preguntas/  → Dimensión con preguntas ⭐ NUEVO
    - PATCH  /api/dimensiones/{id}/                → Editar dimensión (SuperAdmin)
    - POST   /api/dimensiones/{id}/toggle_estado/  → Activar/Desactivar (SuperAdmin)
    """
    queryset = Dimension.objects.select_related('encuesta').prefetch_related('preguntas').all()
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'post']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DimensionListSerializer
        elif self.action == 'con_preguntas':  # ⭐ NUEVO
            return DimensionConPreguntasSerializer
        return DimensionSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Dimension.objects.select_related('encuesta').prefetch_related('preguntas').all()
        
        # Filtrar por encuesta si se proporciona
        encuesta_id = self.request.query_params.get('encuesta_id')
        if encuesta_id:
            queryset = queryset.filter(encuesta_id=encuesta_id)
        
        if user.rol == 'superadmin':
            return queryset
        
        if user.rol in ['administrador', 'auditor']:
            if not user.empresa:
                return queryset.none()
            
            try:
                from apps.asignaciones.models import Asignacion
                encuestas_ids = Asignacion.objects.filter(
                    empresa=user.empresa
                ).values_list('encuesta_id', flat=True).distinct()
                return queryset.filter(encuesta_id__in=encuestas_ids)
            except ImportError:
                return queryset.filter(encuesta__activo=True)
        
        return queryset.none()
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'toggle_estado']:
            return [IsAuthenticated(), EsSuperAdmin()]

        if self.action == 'con_preguntas':
            return [IsAuthenticated()]  # 🔥 IMPORTANTE

        return [IsAuthenticated(), EsAdminOSuperAdminOAuditor()]

    
    def create(self, request, *args, **kwargs):
        """Bloquear creación manual"""
        return self.error_response(
            message='Las dimensiones se crean al cargar la encuesta desde Excel',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Bloquear eliminación"""
        return self.error_response(
            message='No se permite eliminar dimensiones. Use toggle_estado para desactivar.',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def update(self, request, *args, **kwargs):
        """Actualizar dimensión - SOLO PATCH"""
        if request.method == 'PUT':
            return self.error_response(
                message='Use PATCH para actualización parcial',
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return self.success_response(
            data=serializer.data,
            message='Dimensión actualizada exitosamente'
        )
    
    @action(detail=True, methods=['post'])
    def toggle_estado(self, request, pk=None):
        """Activar/Desactivar dimensión"""
        dimension = self.get_object()
        dimension.activo = not dimension.activo
        dimension.save()
        
        mensaje = 'Dimensión activada' if dimension.activo else 'Dimensión desactivada'
        return self.success_response(
            data=DimensionSerializer(dimension).data,
            message=f'{mensaje} exitosamente'
        )
    
    # ⭐ NUEVO MÉTODO
    @action(
    detail=True,
    methods=["get"],
    permission_classes=[IsAuthenticated]
    )
    def con_preguntas(self, request, pk=None):
        user = request.user

        dimension = get_object_or_404(
            Dimension.objects.select_related('encuesta')
            .prefetch_related('preguntas'),
            pk=pk
        )

        # Superadmin
        if user.rol == 'superadmin':
            serializer = DimensionConPreguntasSerializer(dimension)
            return Response(serializer.data)

        # Validar empresa
        if not user.empresa:
            return Response(
                {"detail": "Usuario sin empresa asignada"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validar asignación empresa ↔ encuesta
        tiene_acceso = Asignacion.objects.filter(
            empresa=user.empresa,
            encuesta=dimension.encuesta
        ).exists()

        if not tiene_acceso:
            return Response(
                {"detail": "No tiene acceso a esta dimensión"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = DimensionConPreguntasSerializer(dimension)
        return Response(serializer.data)


# =============================================================================
# VIEWSET PARA PREGUNTAS
# =============================================================================

class PreguntaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de preguntas - SOLO LECTURA Y EDICIÓN
    
    ENDPOINTS:
    - GET    /api/preguntas/                    → Listar preguntas (?dimension_id=xxx)
    - GET    /api/preguntas/{id}/               → Detalle de pregunta
    - PATCH  /api/preguntas/{id}/               → Editar pregunta (SuperAdmin)
    - POST   /api/preguntas/{id}/toggle_estado/ → Activar/Desactivar (SuperAdmin)
    """
    queryset = Pregunta.objects.select_related('dimension__encuesta').prefetch_related('niveles_referencia').all()
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'post']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PreguntaListSerializer
        return PreguntaSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Pregunta.objects.select_related('dimension__encuesta').prefetch_related('niveles_referencia').all()
        
        # Filtrar por dimensión si se proporciona
        dimension_id = self.request.query_params.get('dimension_id')
        if dimension_id:
            queryset = queryset.filter(dimension_id=dimension_id)
        
        if user.rol == 'superadmin':
            return queryset
        
        if user.rol in ['administrador', 'auditor']:
            if not user.empresa:
                return queryset.none()
            
            try:
                from apps.asignaciones.models import Asignacion
                encuestas_ids = Asignacion.objects.filter(
                    empresa=user.empresa
                ).values_list('encuesta_id', flat=True).distinct()
                return queryset.filter(dimension__encuesta_id__in=encuestas_ids)
            except ImportError:
                return queryset.filter(dimension__encuesta__activo=True)
        
        return queryset.none()
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'toggle_estado']:
            return [IsAuthenticated(), EsSuperAdmin()]
        return [IsAuthenticated(), EsAdminOSuperAdminOAuditor()]
    
    def create(self, request, *args, **kwargs):
        """Bloquear creación manual"""
        return self.error_response(
            message='Las preguntas se crean al cargar la encuesta desde Excel',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Bloquear eliminación"""
        return self.error_response(
            message='No se permite eliminar preguntas. Use toggle_estado para desactivar.',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def update(self, request, *args, **kwargs):
        """Actualizar pregunta - SOLO PATCH"""
        if request.method == 'PUT':
            return self.error_response(
                message='Use PATCH para actualización parcial',
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return self.success_response(
            data=serializer.data,
            message='Pregunta actualizada exitosamente'
        )
    
    @action(detail=True, methods=['post'])
    def toggle_estado(self, request, pk=None):
        """Activar/Desactivar pregunta"""
        pregunta = self.get_object()
        pregunta.activo = not pregunta.activo
        pregunta.save()
        
        mensaje = 'Pregunta activada' if pregunta.activo else 'Pregunta desactivada'
        return self.success_response(
            data=PreguntaSerializer(pregunta).data,
            message=f'{mensaje} exitosamente'
        )


# =============================================================================
# VIEWSET PARA NIVELES DE REFERENCIA
# =============================================================================

class NivelReferenciaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para niveles de referencia - SOLO LECTURA Y EDICIÓN
    
    ENDPOINTS:
    - GET    /api/niveles-referencia/           → Listar niveles (?pregunta_id=xxx)
    - GET    /api/niveles-referencia/{id}/      → Detalle de nivel
    - PATCH  /api/niveles-referencia/{id}/      → Editar nivel (SuperAdmin)
    - POST   /api/niveles-referencia/{id}/toggle_estado/ → Activar/Desactivar (SuperAdmin)
    """
    queryset = NivelReferencia.objects.select_related('pregunta__dimension__encuesta').all()
    serializer_class = NivelReferenciaSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'post']
    
    def get_queryset(self):
        user = self.request.user
        queryset = NivelReferencia.objects.select_related('pregunta__dimension__encuesta').all()
        
        # Filtrar por pregunta si se proporciona
        pregunta_id = self.request.query_params.get('pregunta_id')
        if pregunta_id:
            queryset = queryset.filter(pregunta_id=pregunta_id)
        
        if user.rol == 'superadmin':
            return queryset
        
        if user.rol in ['administrador', 'auditor']:
            if not user.empresa:
                return queryset.none()
            
            try:
                from apps.asignaciones.models import Asignacion
                encuestas_ids = Asignacion.objects.filter(
                    empresa=user.empresa
                ).values_list('encuesta_id', flat=True).distinct()
                return queryset.filter(pregunta__dimension__encuesta_id__in=encuestas_ids)
            except ImportError:
                return queryset.filter(pregunta__dimension__encuesta__activo=True)
        
        return queryset.none()
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'toggle_estado']:
            return [IsAuthenticated(), EsSuperAdmin()]
        return [IsAuthenticated(), EsAdminOSuperAdminOAuditor()]
    
    def create(self, request, *args, **kwargs):
        """Bloquear creación manual"""
        return self.error_response(
            message='Los niveles de referencia se crean al cargar la encuesta desde Excel',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Bloquear eliminación"""
        return self.error_response(
            message='No se permite eliminar niveles. Use toggle_estado para desactivar.',
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def update(self, request, *args, **kwargs):
        """Actualizar nivel - SOLO PATCH"""
        if request.method == 'PUT':
            return self.error_response(
                message='Use PATCH para actualización parcial',
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return self.success_response(
            data=serializer.data,
            message='Nivel de referencia actualizado exitosamente'
        )
    
    @action(detail=True, methods=['post'])
    def toggle_estado(self, request, pk=None):
        """Activar/Desactivar nivel"""
        nivel = self.get_object()
        nivel.activo = not nivel.activo
        nivel.save()
        
        mensaje = 'Nivel activado' if nivel.activo else 'Nivel desactivado'
        return self.success_response(
            data=NivelReferenciaSerializer(nivel).data,
            message=f'{mensaje} exitosamente'
        )


# =============================================================================
# VIEWSET PARA CONFIG NIVELES DESEADOS (Mantener el que ya tienes)
# =============================================================================

class ConfigNivelDeseadoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """ViewSet para configuración de niveles deseados - Ya implementado"""
    queryset = ConfigNivelDeseado.objects.select_related('dimension', 'empresa', 'configurado_por').all()
    serializer_class = ConfigNivelDeseadoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = ConfigNivelDeseado.objects.select_related('dimension', 'empresa', 'configurado_por').all()
        
        if user.rol == 'superadmin':
            return queryset
        
        if user.empresa:
            return queryset.filter(empresa=user.empresa)
        
        return queryset.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        return [IsAuthenticated(), EsAuditor()]
    
    @action(detail=False, methods=['get'])
    def por_dimension(self, request):
        """Obtener configuración por dimensión y empresa"""
        dimension_id = request.query_params.get('dimension_id')
        empresa_id = request.query_params.get('empresa_id')
        
        if not dimension_id or not empresa_id:
            return self.error_response(
                message='Parámetros dimension_id y empresa_id son requeridos',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        if user.rol != 'superadmin':
            if not user.empresa or str(user.empresa.id) != empresa_id:
                return self.error_response(
                    message='No tienes permiso para consultar esta empresa',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        try:
            config = ConfigNivelDeseado.objects.get(
                dimension_id=dimension_id,
                empresa_id=empresa_id
            )
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        except ConfigNivelDeseado.DoesNotExist:
            return Response({
                'mensaje': 'No existe configuración para esta dimensión y empresa',
                'nivel_deseado': None
            }, status=status.HTTP_200_OK)