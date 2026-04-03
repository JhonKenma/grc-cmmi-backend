# apps/evaluaciones/views.py
"""
Views para Sistema de Evaluaciones Inteligentes
Incluye endpoint para importar Excel (SOLO SUPERADMIN)
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.db.models import Count, Q
from django.conf import settings
from apps.core.permissions import EsSuperAdmin, EsAdminOSuperAdmin
import pandas as pd
import re

from .models import (
    EmpresaFramework,
    Framework,
    PreguntaEvaluacion,
    EvidenciaRequerida,
    RelacionFramework,
    Evaluacion,
    EvaluacionPregunta,  # ⭐ NUEVO
    RespuestaEvaluacion,
    NotaEvidencia,
    ComentarioEvaluacion
)
from .serializers import (
    EmpresaFrameworkListSerializer,
    EmpresaFrameworkSerializer,
    FrameworkSerializer,
    PreguntaEvaluacionListSerializer,
    PreguntaEvaluacionDetailSerializer,
    EvaluacionListSerializer,
    EvaluacionDetailSerializer,
    EvaluacionPreguntaSerializer,  # ⭐ NUEVO
    RespuestaEvaluacionSerializer,
    NotaEvidenciaSerializer,
    ComentarioEvaluacionSerializer
)
from .services import CopilotQuestionSelectorClient

class FrameworkViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Framework.objects.filter(activo=True)
    serializer_class = FrameworkSerializer
    
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[EsSuperAdmin],
        parser_classes=[MultiPartParser, FormParser],
        url_path='importar-excel'
    )
    def importar_excel(self, request):

        if 'file' not in request.FILES:
            return Response(
                {
                    'success': False,
                    'error': 'No se envió ningún archivo',
                    'message': 'Debes enviar un archivo Excel'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Validar extensión
        if not file.name.endswith('.xlsx'):
            return Response(
                {
                    'success': False,
                    'error': 'Formato inválido',
                    'message': 'Solo se permiten archivos .xlsx'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Importar
            importador = ImportadorExcel(request.user)
            resultado = importador.importar_archivo(file)
            
            return Response(resultado, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': 'Error en importación',
                    'message': str(e),
                    'tipo': type(e).__name__
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[EsSuperAdmin],
        url_path='estadisticas'
    )
    def estadisticas(self, request):
        """
        Estadísticas generales de frameworks
        
        GET /api/evaluaciones/frameworks/estadisticas/
        """
        
        frameworks = Framework.objects.all()
        estadisticas = []
        
        for fw in frameworks:
            preguntas_count = fw.preguntas.filter(activo=True).count()
            evidencias_count = EvidenciaRequerida.objects.filter(
                pregunta__framework=fw
            ).count()
            relaciones_count = RelacionFramework.objects.filter(
                pregunta_origen__framework=fw
            ).count()
            
            estadisticas.append({
                'framework': {
                    'id': fw.id,
                    'codigo': fw.codigo,
                    'nombre': fw.nombre,
                    'version': fw.version,
                    'activo': fw.activo
                },
                'preguntas': preguntas_count,
                'evidencias': evidencias_count,
                'relaciones_con_otros_frameworks': relaciones_count
            })
        
        return Response({
            'total_frameworks': frameworks.count(),
            'frameworks': estadisticas
        })


# ============================================================================
# PREGUNTA EVALUACION VIEWSET
# ============================================================================

class PreguntaEvaluacionViewSet(viewsets.ReadOnlyModelViewSet):
    
    queryset = PreguntaEvaluacion.objects.filter(activo=True)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PreguntaEvaluacionDetailSerializer
        return PreguntaEvaluacionListSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por framework
        framework = self.request.query_params.get('framework', None)
        if framework:
            queryset = queryset.filter(framework__codigo=framework)
        
        # Filtrar por nivel de madurez
        nivel = self.request.query_params.get('nivel_madurez', None)
        if nivel:
            queryset = queryset.filter(nivel_madurez=nivel)
        
        # Filtrar por sección
        seccion = self.request.query_params.get('seccion', None)
        if seccion:
            queryset = queryset.filter(seccion_general__icontains=seccion)
        
        return queryset.select_related('framework')
    
    @action(
        detail=False,
        methods=['get'],
        url_path='por-framework/(?P<codigo_framework>[^/.]+)'
    )
    def por_framework(self, request, codigo_framework=None):

        try:
            framework = Framework.objects.get(codigo=codigo_framework, activo=True)
        except Framework.DoesNotExist:
            return Response(
                {
                    'error': 'Framework no encontrado',
                    'codigo': codigo_framework,
                    'disponibles': list(Framework.objects.filter(activo=True).values_list('codigo', flat=True))
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener preguntas del framework
        queryset = PreguntaEvaluacion.objects.filter(
            framework=framework,
            activo=True
        ).select_related('framework').prefetch_related(
            'evidencias_requeridas',
            'relaciones_frameworks__framework_destino'
        )
        
        # Filtro opcional por correlativo
        correlativo = request.query_params.get('correlativo', None)
        if correlativo:
            queryset = queryset.filter(correlativo=correlativo)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PreguntaEvaluacionDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PreguntaEvaluacionDetailSerializer(queryset, many=True)
        return Response({
            'framework': {
                'codigo': framework.codigo,
                'nombre': framework.nombre,
                'version': framework.version,
                'total_preguntas': queryset.count()
            },
            'preguntas': serializer.data
        })


# ============================================================================
# ⭐ NUEVO: EMPRESA FRAMEWORK VIEWSET
# ============================================================================

class EmpresaFrameworkViewSet(viewsets.ModelViewSet):
    """
    Gestión de frameworks asignados a empresas.

    SuperAdmin:
      GET    /empresa-frameworks/                    → listar todas las asignaciones
      POST   /empresa-frameworks/                    → asignar framework a empresa
      GET    /empresa-frameworks/{id}/               → detalle de asignación
      PATCH  /empresa-frameworks/{id}/               → actualizar notas/activo
      DELETE /empresa-frameworks/{id}/               → quitar asignación
      GET    /empresa-frameworks/por-empresa/{id}/   → frameworks de una empresa
      POST   /empresa-frameworks/asignar-varios/     → asignar múltiples frameworks

    Admin (solo lectura de su propia empresa):
      GET    /empresa-frameworks/mis-frameworks/     → frameworks de mi empresa
    """

    permission_classes = [EsAdminOSuperAdmin]

    def get_queryset(self):
        user = self.request.user

        if user.rol == 'superadmin':
            # SuperAdmin ve todas las asignaciones
            return EmpresaFramework.objects.select_related(
                'empresa', 'framework', 'asignado_por'
            ).all()
        else:
            # Admin solo ve los frameworks de su empresa
            return EmpresaFramework.objects.select_related(
                'empresa', 'framework', 'asignado_por'
            ).filter(empresa=user.empresa, activo=True)

    def get_serializer_class(self):
        user = self.request.user
        # Admin usa serializer simplificado
        if user.rol != 'superadmin':
            return EmpresaFrameworkListSerializer
        return EmpresaFrameworkSerializer

    def perform_create(self, serializer):
        # Solo SuperAdmin puede crear, registra quién asignó
        serializer.save(asignado_por=self.request.user)

    def create(self, request, *args, **kwargs):
        # Solo SuperAdmin puede asignar frameworks
        if request.user.rol != 'superadmin':
            return Response(
                {'error': 'Solo el SuperAdmin puede asignar frameworks a empresas'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Solo SuperAdmin puede quitar frameworks
        if request.user.rol != 'superadmin':
            return Response(
                {'error': 'Solo el SuperAdmin puede quitar frameworks de empresas'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[EsSuperAdmin],
        url_path='por-empresa/(?P<empresa_id>[^/.]+)'
    )
    def por_empresa(self, request, empresa_id=None):
        """
        Lista los frameworks asignados a una empresa específica.
        Solo SuperAdmin.

        GET /api/evaluaciones/empresa-frameworks/por-empresa/{empresa_id}/
        """
        asignaciones = EmpresaFramework.objects.filter(
            empresa_id=empresa_id
        ).select_related('framework', 'asignado_por')

        serializer = EmpresaFrameworkSerializer(asignaciones, many=True)
        return Response({
            'empresa_id': empresa_id,
            'total': asignaciones.count(),
            'activos': asignaciones.filter(activo=True).count(),
            'frameworks': serializer.data
        })

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[EsSuperAdmin],
        url_path='asignar-varios'
    )
    def asignar_varios(self, request):
        """
        Asigna múltiples frameworks a una empresa en una sola llamada.
        Solo SuperAdmin.

        POST /api/evaluaciones/empresa-frameworks/asignar-varios/
        Body:
        {
            "empresa": 1,
            "frameworks": [1, 2, 3],
            "notas": "Opcional"
        }
        """
        empresa_id = request.data.get('empresa')
        framework_ids = request.data.get('frameworks', [])
        notas = request.data.get('notas', '')

        if not empresa_id:
            return Response(
                {'error': 'Debe enviar el campo empresa'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not framework_ids:
            return Response(
                {'error': 'Debe enviar al menos un framework'},
                status=status.HTTP_400_BAD_REQUEST
            )

        asignados = []
        ya_existian = []

        for fw_id in framework_ids:
            asignacion, created = EmpresaFramework.objects.get_or_create(
                empresa_id=empresa_id,
                framework_id=fw_id,
                defaults={
                    'asignado_por': request.user,
                    'notas': notas,
                    'activo': True,
                }
            )

            if created:
                asignados.append(fw_id)
            else:
                # Si existía pero estaba inactivo, reactivar
                if not asignacion.activo:
                    asignacion.activo = True
                    asignacion.save()
                    asignados.append(fw_id)
                else:
                    ya_existian.append(fw_id)

        return Response({
            'success': True,
            'asignados': asignados,
            'ya_existian': ya_existian,
            'total_asignados': len(asignados),
        }, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=['get'],
        url_path='mis-frameworks'
    )
    def mis_frameworks(self, request):
        """
        Lista los frameworks disponibles para el Admin de la empresa actual.

        GET /api/evaluaciones/empresa-frameworks/mis-frameworks/
        """
        user = request.user

        if user.rol == 'superadmin':
            return Response(
                {'error': 'Este endpoint es solo para administradores de empresa'},
                status=status.HTTP_403_FORBIDDEN
            )

        asignaciones = EmpresaFramework.objects.filter(
            empresa=user.empresa,
            activo=True
        ).select_related('framework')

        serializer = EmpresaFrameworkListSerializer(asignaciones, many=True)
        return Response({
            'empresa': user.empresa.nombre,
            'total_frameworks': asignaciones.count(),
            'frameworks': serializer.data
        })


# ============================================================================
# EVALUACION VIEWSET
# ============================================================================

class EvaluacionViewSet(viewsets.ModelViewSet):

    permission_classes = [EsAdminOSuperAdmin]

    def get_queryset(self):
        user = self.request.user

        if user.rol == 'superadmin':
            # SuperAdmin ve todas las evaluaciones de todas las empresas
            return Evaluacion.objects.select_related('empresa', 'creado_por').all()
        else:
            # Admin solo ve las evaluaciones de SU empresa
            return Evaluacion.objects.select_related(
                'empresa', 'creado_por'
            ).filter(empresa=user.empresa)

    def get_serializer_class(self):
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return EvaluacionDetailSerializer
        return EvaluacionListSerializer

    def perform_create(self, serializer):
        user = self.request.user

        if user.rol == 'superadmin':
            # SuperAdmin debe enviar empresa en el body
            serializer.save(creado_por=user)
        else:
            # Admin: la empresa se asigna automáticamente desde su perfil
            serializer.save(
                creado_por=user,
                empresa=user.empresa
            )

    def create(self, request, *args, **kwargs):
        user = request.user

        # Validar que Admin solo use frameworks de su empresa
        if user.rol != 'superadmin':
            frameworks_ids = request.data.get('frameworks', [])
            if frameworks_ids:
                # Verificar que todos los frameworks estén asignados a su empresa
                frameworks_asignados = EmpresaFramework.objects.filter(
                    empresa=user.empresa,
                    activo=True
                ).values_list('framework_id', flat=True)

                frameworks_no_asignados = [
                    fid for fid in frameworks_ids
                    if fid not in frameworks_asignados
                ]

                if frameworks_no_asignados:
                    return Response(
                        {
                            'error': 'Frameworks no disponibles para su empresa',
                            'frameworks_no_asignados': frameworks_no_asignados,
                            'message': 'Solo puede usar frameworks asignados a su empresa por el SuperAdmin'
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )

        return super().create(request, *args, **kwargs)

    @action(
        detail=True,
        methods=['post'],
        url_path='sugerir-preguntas-ia'
    )
    def sugerir_preguntas_ia(self, request, pk=None):
        """Sugiere preguntas priorizadas con IA segun el contexto de la evaluacion."""
        evaluacion = self.get_object()

        framework_codigo = request.data.get('framework_codigo')
        instruction = str(request.data.get('instruction', '')).strip()
        seccion = str(request.data.get('seccion', '')).strip()

        max_preguntas_raw = request.data.get('max_preguntas', 25)
        try:
            max_preguntas = int(max_preguntas_raw)
        except (TypeError, ValueError):
            return Response(
                {'error': 'max_preguntas debe ser un numero entero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        max_preguntas = max(1, min(max_preguntas, 100))

        nivel_madurez_raw = request.data.get('nivel_madurez')
        nivel_madurez = None
        if nivel_madurez_raw is not None and str(nivel_madurez_raw) != '':
            try:
                nivel_madurez = int(nivel_madurez_raw)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'nivel_madurez debe ser un numero entero'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        candidatas_qs = PreguntaEvaluacion.objects.filter(
            framework__in=evaluacion.frameworks.all(),
            activo=True,
        ).select_related('framework')

        if framework_codigo:
            candidatas_qs = candidatas_qs.filter(framework__codigo=framework_codigo)

        if nivel_madurez is not None:
            candidatas_qs = candidatas_qs.filter(nivel_madurez=nivel_madurez)

        if seccion:
            candidatas_qs = candidatas_qs.filter(seccion_general__icontains=seccion)

        candidatas_qs = candidatas_qs.order_by('framework__codigo', 'correlativo')[:300]
        candidatas = list(candidatas_qs)

        if not candidatas:
            return Response(
                {
                    'success': False,
                    'message': 'No hay preguntas candidatas con los filtros enviados',
                    'selected_question_ids': [],
                    'recommendations': [],
                    'preguntas_sugeridas': [],
                },
                status=status.HTTP_200_OK
            )

        payload = {
            'empresa_id': evaluacion.empresa_id,
            'framework': framework_codigo or 'MULTI-FRAMEWORK',
            'instruction': instruction,
            'max_questions': max_preguntas,
            'evaluation': {
                'evaluacion_id': evaluacion.id,
                'nombre': evaluacion.nombre,
                'descripcion': evaluacion.descripcion,
                'nivel_deseado': evaluacion.nivel_deseado,
                'frameworks': list(evaluacion.frameworks.values_list('codigo', flat=True)),
            },
            'candidates': [
                {
                    'question_id': pregunta.id,
                    'framework_codigo': pregunta.framework.codigo,
                    'codigo_control': pregunta.codigo_control,
                    'seccion_general': pregunta.seccion_general,
                    'nivel_madurez': pregunta.nivel_madurez,
                    'pregunta': pregunta.pregunta[:1200],
                }
                for pregunta in candidatas
            ],
        }

        auth_header = request.headers.get('Authorization')
        client = CopilotQuestionSelectorClient(
            base_url=settings.AI_MICROSERVICE_URL,
            timeout_seconds=settings.AI_MICROSERVICE_TIMEOUT,
        )

        try:
            ai_response = client.suggest_questions(
                authorization_header=auth_header,
                payload=payload,
            )
        except ValueError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except RuntimeError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        selected_raw = ai_response.get('selected_question_ids', [])
        if not isinstance(selected_raw, list):
            return Response(
                {'error': 'Respuesta invalida del microservicio de IA'},
                status=status.HTTP_502_BAD_GATEWAY
            )

        candidate_ids = {pregunta.id for pregunta in candidatas}
        selected_ids = [
            question_id
            for question_id in selected_raw
            if isinstance(question_id, int) and question_id in candidate_ids
        ]

        recomendaciones_raw = ai_response.get('recommendations', [])
        recomendaciones = []
        if isinstance(recomendaciones_raw, list):
            for item in recomendaciones_raw:
                if not isinstance(item, dict):
                    continue
                question_id = item.get('question_id')
                if isinstance(question_id, int) and question_id in candidate_ids:
                    recomendaciones.append(item)

        sugeridas_qs = PreguntaEvaluacion.objects.filter(id__in=selected_ids).select_related('framework')
        serializer = PreguntaEvaluacionListSerializer(sugeridas_qs, many=True)
        by_id = {item['id']: item for item in serializer.data}
        preguntas_ordenadas = [by_id[question_id] for question_id in selected_ids if question_id in by_id]

        return Response(
            {
                'success': True,
                'evaluacion_id': evaluacion.id,
                'framework': payload['framework'],
                'criterio': ai_response.get('criterio', ''),
                'total_candidatas': len(candidatas),
                'total_sugeridas': len(selected_ids),
                'selected_question_ids': selected_ids,
                'recommendations': recomendaciones,
                'preguntas_sugeridas': preguntas_ordenadas,
                'model': ai_response.get('model'),
            },
            status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='agregar-preguntas'
    )
    def agregar_preguntas(self, request, pk=None):

        evaluacion = self.get_object()

        if evaluacion.usar_todas_preguntas:
            return Response(
                {
                    'error': 'Esta evaluación usa todas las preguntas de los frameworks',
                    'message': 'No se pueden agregar preguntas individuales'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        preguntas_ids = request.data.get('preguntas_ids', [])

        if not preguntas_ids:
            return Response(
                {'error': 'Debe enviar al menos 1 pregunta'},
                status=status.HTTP_400_BAD_REQUEST
            )

        preguntas = PreguntaEvaluacion.objects.filter(
            id__in=preguntas_ids,
            framework__in=evaluacion.frameworks.all(),
            activo=True
        )

        if preguntas.count() != len(preguntas_ids):
            return Response(
                {
                    'error': 'Algunas preguntas no existen o no pertenecen a los frameworks seleccionados',
                    'enviadas': len(preguntas_ids),
                    'validas': preguntas.count()
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        agregadas = 0
        duplicadas = 0
        orden_actual = evaluacion.preguntas_seleccionadas.count()

        for pregunta in preguntas:
            if evaluacion.preguntas_seleccionadas.filter(pregunta=pregunta).exists():
                duplicadas += 1
                continue

            EvaluacionPregunta.objects.create(
                evaluacion=evaluacion,
                pregunta=pregunta,
                orden=orden_actual + agregadas + 1
            )
            agregadas += 1

        if evaluacion.estado == 'configurando' and agregadas > 0:
            evaluacion.estado = 'disponible'
            evaluacion.save()

        return Response({
            'success': True,
            'preguntas_agregadas': agregadas,
            'preguntas_duplicadas': duplicadas,
            'total_preguntas_evaluacion': evaluacion.total_preguntas,
            'estado': evaluacion.estado
        }, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['delete'],
        url_path='quitar-preguntas'
    )
    def quitar_preguntas(self, request, pk=None):

        evaluacion = self.get_object()

        if evaluacion.usar_todas_preguntas:
            return Response(
                {'error': 'No se pueden quitar preguntas de una evaluación que usa todas'},
                status=status.HTTP_400_BAD_REQUEST
            )

        preguntas_ids = request.data.get('preguntas_ids', [])

        if not preguntas_ids:
            return Response(
                {'error': 'Debe enviar al menos 1 pregunta'},
                status=status.HTTP_400_BAD_REQUEST
            )

        eliminadas = evaluacion.preguntas_seleccionadas.filter(
            pregunta_id__in=preguntas_ids
        ).delete()[0]

        for i, ep in enumerate(evaluacion.preguntas_seleccionadas.order_by('orden'), 1):
            if ep.orden != i:
                ep.orden = i
                ep.save()

        return Response({
            'success': True,
            'preguntas_eliminadas': eliminadas,
            'total_preguntas_evaluacion': evaluacion.total_preguntas
        })

    @action(
        detail=True,
        methods=['get'],
        url_path='preguntas-seleccionadas'
    )
    def preguntas_seleccionadas(self, request, pk=None):

        evaluacion = self.get_object()

        if evaluacion.usar_todas_preguntas:
            preguntas = evaluacion.get_preguntas_a_responder()
            serializer = PreguntaEvaluacionListSerializer(preguntas, many=True)
            return Response({
                'usar_todas_preguntas': True,
                'total': preguntas.count(),
                'preguntas': serializer.data
            })
        else:
            preguntas_eval = evaluacion.preguntas_seleccionadas.select_related(
                'pregunta__framework'
            ).order_by('orden')
            serializer = EvaluacionPreguntaSerializer(preguntas_eval, many=True)
            return Response({
                'usar_todas_preguntas': False,
                'total': preguntas_eval.count(),
                'preguntas': serializer.data
            })

    @action(
        detail=True,
        methods=['put'],
        url_path='reordenar-preguntas'
    )
    def reordenar_preguntas(self, request, pk=None):

        evaluacion = self.get_object()

        if evaluacion.usar_todas_preguntas:
            return Response(
                {'error': 'No se puede reordenar una evaluación que usa todas las preguntas'},
                status=status.HTTP_400_BAD_REQUEST
            )

        nuevo_orden = request.data.get('orden', [])

        if not nuevo_orden:
            return Response(
                {'error': 'Debe enviar el nuevo orden'},
                status=status.HTTP_400_BAD_REQUEST
            )

        for i, pregunta_id in enumerate(nuevo_orden, 1):
            evaluacion.preguntas_seleccionadas.filter(
                pregunta_id=pregunta_id
            ).update(orden=i)

        return Response({
            'success': True,
            'total_preguntas': len(nuevo_orden)
        })



# ============================================================================
# RESPUESTA EVALUACION VIEWSET
# ============================================================================

class RespuestaEvaluacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Respuestas de Evaluación
    """
    
    queryset = RespuestaEvaluacion.objects.all()
    serializer_class = RespuestaEvaluacionSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por evaluación
        evaluacion_id = self.request.query_params.get('evaluacion', None)
        if evaluacion_id:
            queryset = queryset.filter(evaluacion_id=evaluacion_id)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(respondido_por=self.request.user)


# ============================================================================
# IMPORTADOR DE EXCEL
# ============================================================================

class ImportadorExcel:
    """
    Clase auxiliar para importar Excel
    Omite automáticamente hojas que contengan "NIST"
    """
    
    def __init__(self, usuario):
        self.usuario = usuario
    
    def importar_archivo(self, file):
        """Importa el archivo Excel completo"""
        
        # Cargar Excel
        xl_file = pd.ExcelFile(file)
        
        # Filtrar hojas (omitir NIST)
        hojas_disponibles = xl_file.sheet_names
        hojas_omitidas = [h for h in hojas_disponibles if 'NIST' in h.upper()]
        hojas_a_procesar = [h for h in hojas_disponibles if 'NIST' not in h.upper()]
        
        if not hojas_a_procesar:
            raise ValueError('No hay hojas para procesar (todas son NIST)')
        
        # Procesar cada hoja
        resultados = []
        
        with transaction.atomic():
            for sheet_name in hojas_a_procesar:
                resultado = self.importar_hoja(file, sheet_name)
                resultados.append(resultado)
        
        # Estadísticas totales
        estadisticas = {
            'total_frameworks': len(resultados),
            'total_preguntas': sum(r['preguntas'] for r in resultados),
            'total_evidencias': sum(r['evidencias'] for r in resultados),
            'total_relaciones': sum(r['relaciones'] for r in resultados),
            'hojas_procesadas': [r['nombre'] for r in resultados],
            'hojas_omitidas': hojas_omitidas
        }
        
        return {
            'success': True,
            'message': f'Importación completada: {len(resultados)} framework(s)',
            'frameworks_importados': resultados,
            'estadisticas': estadisticas,
            'importado_por': {
                'id': self.usuario.id,
                'email': self.usuario.email,
                'nombre': self.usuario.get_full_name()
            }
        }
    
    def importar_hoja(self, file, sheet_name):
        """Importa una hoja específica"""
        
        # Cargar datos
        df = pd.read_excel(file, sheet_name=sheet_name)
        
        # Detectar framework
        framework_info = self.detectar_framework(sheet_name)
        
        # Crear/Actualizar framework
        framework, created = Framework.objects.update_or_create(
            codigo=framework_info['codigo'],
            defaults={
                'nombre': framework_info['nombre'],
                'descripcion': framework_info['descripcion'],
                'version': framework_info.get('version', '')
            }
        )
        
        # ⭐ CORRECCIÓN: Filtrar mejor las filas de preguntas
        # Solo procesar filas donde Correlativo sea un número válido
        preguntas_df = df[
            df['Correlativo'].notna() &  # No sea NaN
            (df['Correlativo'] != 'Correlativo')  # No sea el encabezado
        ].copy()
        
        # ⭐ CORRECCIÓN: Convertir a numérico y filtrar inválidos
        preguntas_df['Correlativo'] = pd.to_numeric(
            preguntas_df['Correlativo'], 
            errors='coerce'
        )
        preguntas_df = preguntas_df[preguntas_df['Correlativo'].notna()]
        
        contador_preguntas = 0
        contador_evidencias = 0
        contador_relaciones = 0
        
        for idx, row in preguntas_df.iterrows():
            try:
                # Crear pregunta
                pregunta = self.crear_pregunta(row, framework)
                contador_preguntas += 1
                
                # Crear evidencias
                evidencias = self.crear_evidencias(df, idx, pregunta)
                contador_evidencias += evidencias
                
                # Crear relaciones
                relaciones = self.crear_relaciones(
                    pregunta,
                    row.get('Frameworks y Controles Referenciales')
                )
                contador_relaciones += relaciones
            except Exception as e:
                print(f"⚠️ Error en fila {idx}: {str(e)}")
                continue
        
        return {
            'codigo': framework.codigo,
            'nombre': framework.nombre,
            'version': framework.version,
            'creado': created,
            'preguntas': contador_preguntas,
            'evidencias': contador_evidencias,
            'relaciones': contador_relaciones
        }
    
    def detectar_framework(self, sheet_name):
        """Detecta información del framework"""
        
        mapeo = {
            'ISO 27001': {
                'codigo': 'ISO27001',
                'nombre': 'ISO 27001 - SGSI',
                'descripcion': 'Sistema de Gestión de Seguridad de la Información',
                'version': '2022'
            },
            'ISO 42001': {
                'codigo': 'ISO42001',
                'nombre': 'ISO 42001 - IA',
                'descripcion': 'Sistema de Gestión de IA',
                'version': '2023'
            },
            'ISO 27701': {
                'codigo': 'ISO27701',
                'nombre': 'ISO 27701 - Privacidad',
                'descripcion': 'Gestión de Privacidad',
                'version': '2019'
            },
            'ISO 31000': {
                'codigo': 'ISO31000',
                'nombre': 'ISO 31000 - Riesgos',
                'descripcion': 'Gestión de Riesgos',
                'version': '2018'
            },
            'DMM': {
                'codigo': 'DMM',
                'nombre': 'DMM',
                'descripcion': 'Data Management Maturity',
                'version': ''
            },
            'DAMA DMBOK': {
                'codigo': 'DAMADMBOK',
                'nombre': 'DAMA-DMBOK',
                'descripcion': 'Data Management Body of Knowledge',
                'version': '2'
            },
            'Gartner AI Maturity Model': {
                'codigo': 'GARTNERAI',
                'nombre': 'Gartner AI Maturity',
                'descripcion': 'Modelo de Madurez de IA',
                'version': ''
            }
        }
        
        if sheet_name in mapeo:
            return mapeo[sheet_name]
        
        codigo = sheet_name.replace(' ', '').replace('-', '').upper()[:50]
        return {
            'codigo': codigo,
            'nombre': sheet_name,
            'descripcion': f'Framework {sheet_name}',
            'version': ''
        }
    
    def crear_pregunta(self, row, framework):
        """Crea o actualiza pregunta"""
        
        # Validar Correlativo
        correlativo = row.get('Correlativo')
        try:
            correlativo_int = int(float(correlativo))
        except (ValueError, TypeError):
            raise ValueError(f"Correlativo inválido: {correlativo}")
        
        nivel_madurez = row.get('Nivel de Madurez de la Pregunta')
        if pd.isna(nivel_madurez) or isinstance(nivel_madurez, str):
            nivel_madurez = 3
        else:
            try:
                nivel_madurez = int(float(nivel_madurez))
            except (ValueError, TypeError):
                nivel_madurez = 3
        
        def limpiar(valor):
            return str(valor).strip() if pd.notna(valor) else ''
        
        # Limpiar pregunta
        pregunta_texto = limpiar(row.get('Pregunta de evaluación bien exhaustiva'))
        
        # ⭐ NUEVO: Guardar framework_base_nombre
        framework_base_nombre = limpiar(row.get('Framework Base'))
        
        pregunta, created = PreguntaEvaluacion.objects.update_or_create(
            framework=framework,
            correlativo=correlativo_int,
            defaults={
                'framework_base_nombre': framework_base_nombre,  # ⭐ NUEVO CAMPO
                'codigo_control': limpiar(row.get('Código Control / Referencia')),
                'seccion_general': limpiar(row.get('Sección General o Tema del Control')),
                'nombre_control': limpiar(row.get('Nombre del Control')),
                'tags': limpiar(row.get('Etiquetas Contextuales Unificadas (Tags)')),
                'frameworks_referenciales': limpiar(row.get('Frameworks y Controles Referenciales')),
                'objetivo_evaluacion': limpiar(row.get('Objetivo de Evaluación Basado en Etiquetas')),
                'pregunta': pregunta_texto,
                'nivel_madurez': nivel_madurez,
            }
        )
        
        return pregunta
    
    def crear_evidencias(self, df, idx_pregunta, pregunta):

        import re
        
        contador = 0
        
        # PASO 1: Obtener evidencia de la fila principal (columna J)
        try:
            evidencia_principal = df.iloc[idx_pregunta]['Mínimo 5 Evidencias Tipo Aceptadas para Evaluación']
            
            if pd.notna(evidencia_principal):
                evidencia_str = str(evidencia_principal).strip()
                
                # ⭐ DETECTAR: ¿Tiene formato "1. ... 2. ... 3. ..."?
                if self._tiene_evidencias_numeradas(evidencia_str):
                    # PARSEAR y SEPARAR en 5 evidencias
                    evidencias_separadas = self._separar_evidencias_numeradas(evidencia_str)
                    
                    for i, evidencia_texto in enumerate(evidencias_separadas, 1):
                        if evidencia_texto and i <= 5:
                            EvidenciaRequerida.objects.update_or_create(
                                pregunta=pregunta,
                                orden=i,
                                defaults={
                                    'descripcion': evidencia_texto.strip()
                                }
                            )
                            contador += 1
                    
                    # Si parseó correctamente, terminar aquí
                    if contador > 0:
                        return contador
        except (IndexError, KeyError):
            pass
        
        # PASO 2: Si no encontró en fila principal, buscar en siguientes 5 filas
        for i in range(1, 6):
            try:
                evidencia_row = df.iloc[idx_pregunta + i]
                evidencia_texto = evidencia_row.get('Mínimo 5 Evidencias Tipo Aceptadas para Evaluación')
                
                if pd.notna(evidencia_texto):
                    evidencia_str = str(evidencia_texto).strip()
                    
                    # Verificar si esta fila también tiene formato numerado
                    if self._tiene_evidencias_numeradas(evidencia_str):
                        # Esta fila tiene múltiples evidencias, parsear
                        sub_evidencias = self._separar_evidencias_numeradas(evidencia_str)
                        for j, sub_ev in enumerate(sub_evidencias, 1):
                            if sub_ev and j <= 5:
                                EvidenciaRequerida.objects.update_or_create(
                                    pregunta=pregunta,
                                    orden=j,
                                    defaults={
                                        'descripcion': sub_ev.strip()
                                    }
                                )
                                contador += 1
                        # Si encontró evidencias, terminar
                        if contador > 0:
                            return contador
                    else:
                        # Esta fila tiene UNA evidencia simple
                        # Limpiar número inicial si existe (ej: "1. Documento" → "Documento")
                        evidencia_limpia = re.sub(r'^\d+\.\s*', '', evidencia_str)
                        
                        EvidenciaRequerida.objects.update_or_create(
                            pregunta=pregunta,
                            orden=i,
                            defaults={
                                'descripcion': evidencia_limpia.strip()
                            }
                        )
                        contador += 1
            except (IndexError, KeyError):
                break
        
        return contador
    
    def _tiene_evidencias_numeradas(self, texto):

        import re
        # Buscar números del 1 al 5 seguidos de punto
        patron = r'(?:^|\s)([1-5])\.\s+'
        matches = re.findall(patron, texto)
        # Si encuentra al menos 2 números diferentes, es formato numerado
        numeros_unicos = set(matches)
        return len(numeros_unicos) >= 2
    
    def _separar_evidencias_numeradas(self, texto):

        import re
        
        # Método 1: Buscar patrón "N. contenido" donde N es 1-5
        # Captura el número y todo el contenido hasta el siguiente número o final
        patron = r'([1-5])\.\s*([^1-5]+?)(?=\s*[1-5]\.\s*|$)'
        matches = re.findall(patron, texto, re.DOTALL)
        
        if matches and len(matches) >= 2:
            # Ordenar por número
            matches_ordenados = sorted(matches, key=lambda x: int(x[0]))
            evidencias = []
            for numero, contenido in matches_ordenados:
                # Limpiar: remover puntos finales, espacios, saltos de línea
                contenido_limpio = contenido.strip().rstrip('.').strip()
                # Remover saltos de línea internos
                contenido_limpio = ' '.join(contenido_limpio.split())
                evidencias.append(contenido_limpio)
            
            # Asegurar máximo 5 evidencias
            return evidencias[:5]
        
        # Método 2: Si el método 1 falla, intentar split simple
        partes = re.split(r'\s*([1-5])\.\s+', texto)
        
        evidencias = []
        i = 1
        while i < len(partes) - 1:
            if partes[i].isdigit() and int(partes[i]) <= 5:
                contenido = partes[i + 1].strip().rstrip('.').strip()
                contenido = ' '.join(contenido.split())  # Normalizar espacios
                evidencias.append(contenido)
                i += 2
            else:
                i += 1
        
        # Si no pudo parsear, retornar el texto completo como única evidencia
        if not evidencias:
            evidencias = [texto.strip()]
        
        return evidencias[:5]
    
    def crear_relaciones(self, pregunta, frameworks_ref_text):
        """Crea relaciones entre frameworks (omite NIST)"""
        
        if pd.isna(frameworks_ref_text) or not frameworks_ref_text:
            return 0
        
        contador = 0
        referencias = frameworks_ref_text.split(',')
        
        for ref in referencias:
            ref = ref.strip()
            if not ref:
                continue
            
            # OMITIR NIST
            if 'NIST' in ref.upper() or 'CSF' in ref.upper():
                continue
            
            # Parsear referencia
            info = self.parsear_referencia(ref)
            if not info:
                continue
            
            # Obtener framework destino
            framework_destino = self.obtener_framework_destino(info['framework_nombre'])
            if not framework_destino:
                continue
            
            # Crear relación
            _, created = RelacionFramework.objects.get_or_create(
                pregunta_origen=pregunta,
                referencia_textual=ref,
                defaults={
                    'framework_destino': framework_destino,
                    'codigo_control_referenciado': info['codigo_control'],
                    'porcentaje_cobertura': 100
                }
            )
            
            if created:
                contador += 1
        
        return contador
    
    def parsear_referencia(self, texto):
        """Parsea una referencia individual"""
        
        partes = texto.split(':')
        
        if len(partes) >= 2:
            if len(partes) == 2:
                return {
                    'framework_nombre': partes[0].strip(),
                    'codigo_control': partes[1].strip()
                }
            elif len(partes) >= 3:
                framework = ':'.join(partes[:-1]).strip()
                codigo = partes[-1].strip()
                return {
                    'framework_nombre': framework,
                    'codigo_control': codigo
                }
        
        return None
    
    def obtener_framework_destino(self, nombre_framework):
        """Obtiene framework destino"""
        
        mapeo = {
            'ISO 27001': 'ISO27001',
            'ISO 27001:2022': 'ISO27001',
            'ISO 42001': 'ISO42001',
            'ISO 27701': 'ISO27701',
            'ISO 27701:2022': 'ISO27701',
            'ISO 31000': 'ISO31000',
            'COBIT 2019': 'COBIT2019',
            'COBIT': 'COBIT2019',
            'TOGAF': 'TOGAF',
            'DAMA DMBOK': 'DAMADMBOK',
            'DAMA': 'DAMADMBOK',
            'DMM': 'DMM',
        }
        
        for nombre_busqueda, codigo in mapeo.items():
            if nombre_busqueda in nombre_framework:
                return Framework.objects.filter(codigo=codigo).first()
        
        return None