# apps/proyectos_remediacion/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone

from .models import ProyectoCierreBrecha
from .serializers import (
    ProyectoCierreBrechaListSerializer,
    ProyectoCierreBrechaDetailSerializer,
    ProyectoCierreBrechaCreateSerializer,
    ProyectoCierreBrechaUpdateSerializer,
)
from apps.core.permissions import EsSuperAdmin, EsAdminOSuperAdmin
from apps.core.mixins import ResponseMixin
from apps.respuestas.models import CalculoNivel


class ProyectoCierreBrechaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de Proyectos de Cierre de Brecha
    
    FUNCIONALIDADES:
    1. CRUD completo de proyectos
    2. Filtros por estado, prioridad, empresa
    3. Búsqueda por código o nombre
    4. Estadísticas de proyectos
    5. Creación automática desde GAP
    
    ENDPOINTS:
    - GET    /api/proyectos-remediacion/                          → Listar proyectos
    - POST   /api/proyectos-remediacion/                          → Crear proyecto
    - GET    /api/proyectos-remediacion/{id}/                     → Detalle de proyecto
    - PATCH  /api/proyectos-remediacion/{id}/                     → Actualizar proyecto
    - DELETE /api/proyectos-remediacion/{id}/                     → Desactivar proyecto
    
    - POST   /api/proyectos-remediacion/crear_desde_gap/          → Crear proyecto desde GAP
    - GET    /api/proyectos-remediacion/mis_proyectos/            → Mis proyectos asignados
    - GET    /api/proyectos-remediacion/estadisticas/             → Estadísticas generales
    - GET    /api/proyectos-remediacion/por_estado/               → Agrupar por estado
    - GET    /api/proyectos-remediacion/vencidos/                 → Proyectos vencidos
    - GET    /api/proyectos-remediacion/proximos_a_vencer/        → Proyectos próximos a vencer
    
    PERMISOS:
    - SuperAdmin: Ve y gestiona TODOS los proyectos
    - Admin: Ve y gestiona solo proyectos de SU empresa
    - Usuario: Ve solo proyectos donde está asignado
    """
    
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']
    
    def get_serializer_class(self):
        """Seleccionar serializer según acción"""
        if self.action == 'list':
            return ProyectoCierreBrechaListSerializer
        elif self.action == 'retrieve':
            return ProyectoCierreBrechaDetailSerializer
        elif self.action == 'create' or self.action == 'crear_desde_gap':
            return ProyectoCierreBrechaCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProyectoCierreBrechaUpdateSerializer
        return ProyectoCierreBrechaDetailSerializer
    
    def get_queryset(self):
        """
        Filtrar proyectos según rol del usuario
        
        - SuperAdmin: Ve TODOS los proyectos
        - Admin: Ve proyectos de SU empresa
        - Usuario/Auditor: Ve proyectos donde está asignado
        """
        user = self.request.user
        
        queryset = ProyectoCierreBrecha.objects.select_related(
            'empresa',
            'calculo_nivel',
            'calculo_nivel__dimension',
            'dueno_proyecto',
            'responsable_implementacion',
            'validador_interno',
            'auditor_verificacion',
            'creado_por'
        ).prefetch_related(
            'equipo_implementacion',
            'preguntas_abordadas'
        ).filter(activo=True)
        
        # ═══ FILTRO POR ROL ═══
        if user.rol == 'superadmin':
            # SuperAdmin ve TODO
            pass
        
        elif user.rol == 'administrador':
            # Admin ve solo de su empresa
            if user.empresa:
                queryset = queryset.filter(empresa=user.empresa)
            else:
                queryset = queryset.none()
        
        else:
            # Usuario/Auditor solo ve donde está asignado
            queryset = queryset.filter(
                Q(dueno_proyecto=user) |
                Q(responsable_implementacion=user) |
                Q(equipo_implementacion=user) |
                Q(validador_interno=user) |
                Q(auditor_verificacion=user) |
                Q(responsable_validacion=user)
            ).distinct()
        
        # ═══ FILTROS ADICIONALES (Query Params) ═══
        # Filtro por GAP específico (CalculoNivel)
        calculo_nivel_id = self.request.query_params.get('calculo_nivel')
        if calculo_nivel_id:
            queryset = queryset.filter(calculo_nivel_id=calculo_nivel_id)
        
        # Filtro por estado
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Filtro por prioridad
        prioridad = self.request.query_params.get('prioridad')
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
        
        # Filtro por categoría
        categoria = self.request.query_params.get('categoria')
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        # Filtro por empresa (solo para SuperAdmin)
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id and user.rol == 'superadmin':
            queryset = queryset.filter(empresa_id=empresa_id)
        
        # Búsqueda por código o nombre
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(codigo_proyecto__icontains=search) |
                Q(nombre_proyecto__icontains=search) |
                Q(descripcion__icontains=search)
            )
        
        # Ordenamiento
        ordering = self.request.query_params.get('ordering', '-fecha_creacion')
        queryset = queryset.order_by(ordering)
        
        return queryset
    
    @action(detail=False, methods=['get'], url_path='listar_por_dimension')
    def listar_por_dimension(self, request):
        """
        Listar proyectos por dimensión
        GET /api/proyectos-remediacion/listar_por_dimension/?dimension_id=xxx
        """
        dimension_id = request.query_params.get('dimension_id')
        
        if not dimension_id:
            return Response(
                {'error': 'dimension_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener todos los calculos de esta dimensión
        from apps.respuestas.models import CalculoNivel
        calculos_ids = CalculoNivel.objects.filter(
            dimension_id=dimension_id,
            activo=True
        ).values_list('id', flat=True)
        
        # Filtrar proyectos
        queryset = self.get_queryset().filter(
            calculo_nivel_id__in=calculos_ids
        )
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': queryset.count()
            }
        })
    
    def get_permissions(self):
        """Permisos específicos por acción"""
        if self.action in ['create', 'crear_desde_gap']:
            # Solo Admin o SuperAdmin pueden crear
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        
        if self.action in ['update', 'partial_update', 'destroy']:
            # Solo Admin o SuperAdmin pueden editar/eliminar
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        
        # Para list, retrieve, etc: Solo autenticado
        return [IsAuthenticated()]
    
    # ═══════════════════════════════════════════════════════════════
    # MÉTODOS CRUD PERSONALIZADOS
    # ═══════════════════════════════════════════════════════════════
    
    def create(self, request, *args, **kwargs):
        """
        Crear nuevo proyecto de remediación
        POST /api/proyectos-remediacion/
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        proyecto = serializer.save()
        
        # Serializar con detalle completo para respuesta
        output_serializer = ProyectoCierreBrechaDetailSerializer(proyecto)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Proyecto {proyecto.codigo_proyecto} creado exitosamente',
            status_code=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """
        Actualizar proyecto existente
        PATCH /api/proyectos-remediacion/{id}/
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        proyecto = serializer.save()
        
        # Serializar con detalle completo
        output_serializer = ProyectoCierreBrechaDetailSerializer(proyecto)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Proyecto {proyecto.codigo_proyecto} actualizado exitosamente'
        )
    
    def destroy(self, request, *args, **kwargs):
        """
        Desactivar proyecto (soft delete)
        DELETE /api/proyectos-remediacion/{id}/
        """
        instance = self.get_object()
        
        # Validar que se pueda eliminar
        if instance.estado in ['cerrado']:
            return self.error_response(
                message='No se puede eliminar un proyecto cerrado',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete
        instance.activo = False
        instance.estado = 'cancelado'
        instance.save()
        
        return self.success_response(
            message=f'Proyecto {instance.codigo_proyecto} desactivado exitosamente',
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    # ═══════════════════════════════════════════════════════════════
    # ACCIONES PERSONALIZADAS
    # ═══════════════════════════════════════════════════════════════
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def crear_desde_gap(self, request):
        """
        Crear proyecto automáticamente desde un GAP identificado
        POST /api/proyectos-remediacion/crear_desde_gap/
        
        Body:
        {
            "calculo_nivel_id": "uuid-del-gap",
            "nombre_proyecto": "Nombre personalizado (opcional)",
            "fecha_inicio": "2025-02-01",
            "fecha_fin_estimada": "2025-05-01",
            "dueno_proyecto_id": 123,
            "responsable_implementacion_id": 456,
            "presupuesto_asignado": 50000,
            "moneda": "USD"
        }
        
        IMPORTANTE:
        - El sistema pre-llena automáticamente campos de la brecha
        - Solo se requieren campos mínimos
        - Genera código automático
        """
        
        # ═══ 1. VALIDAR DATOS MÍNIMOS ═══
        calculo_nivel_id = request.data.get('calculo_nivel_id')
        if not calculo_nivel_id:
            return self.error_response(
                message='Se requiere calculo_nivel_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ 2. OBTENER EL GAP ═══
        try:
            calculo_nivel = CalculoNivel.objects.select_related(
                'dimension',
                'empresa',
                'asignacion'
            ).get(id=calculo_nivel_id, activo=True)
        except CalculoNivel.DoesNotExist:
            return self.error_response(
                message='GAP no encontrado',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # ═══ 3. VALIDAR PERMISOS ═══
        user = request.user
        if user.rol == 'administrador':
            if calculo_nivel.empresa != user.empresa:
                return self.error_response(
                    message='Solo puedes crear proyectos para GAPs de tu empresa',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        # ═══ 4. VERIFICAR QUE NO EXISTA YA UN PROYECTO PARA ESTE GAP ═══
        proyectos_previos_count = ProyectoCierreBrecha.objects.filter(
            calculo_nivel=calculo_nivel,
            activo=True
        ).count()

        
        # ═══ 5. PRE-LLENAR DATOS ═══
        # Si ya existen proyectos, podemos añadir un sufijo al nombre para diferenciar
        nombre_base = request.data.get('nombre_proyecto') or f'Remediación: {calculo_nivel.dimension.nombre}'
        if proyectos_previos_count > 0:
            nombre_base = f"{nombre_base} (Fase {proyectos_previos_count + 1})"
            
        datos_proyecto = {
            'calculo_nivel': calculo_nivel.id,
            'nombre_proyecto': nombre_base,

            'descripcion': request.data.get('descripcion') or 
                          f'Proyecto de remediación para cerrar brecha en {calculo_nivel.dimension.nombre}. '
                          f'GAP identificado: {calculo_nivel.gap} ({calculo_nivel.get_clasificacion_gap_display()})',
            
            'fecha_inicio': request.data.get('fecha_inicio'),
            'fecha_fin_estimada': request.data.get('fecha_fin_estimada'),
            
            # Prioridad según clasificación del GAP
            'prioridad': self._mapear_prioridad_gap(calculo_nivel.clasificacion_gap),
            
            'categoria': request.data.get('categoria', 'tecnico'),
            
            # Datos de la brecha (auto-llenado)
            'normativa': request.data.get('normativa', 'iso_27001'),
            'control_no_conforme': request.data.get('control_no_conforme') or 
                                  f'{calculo_nivel.dimension.codigo} - {calculo_nivel.dimension.nombre}',
            
            'tipo_brecha': self._determinar_tipo_brecha(calculo_nivel),
            
            'nivel_criticidad_original': self._mapear_criticidad(calculo_nivel.clasificacion_gap),
            
            'impacto_riesgo': request.data.get('impacto_riesgo') or 
                             f'GAP de {calculo_nivel.gap} puntos en {calculo_nivel.dimension.nombre}. '
                             f'Nivel actual: {calculo_nivel.nivel_actual}, Nivel deseado: {calculo_nivel.nivel_deseado}',
            
            'evidencia_no_conformidad': f'CalculoNivel ID: {calculo_nivel.id}',
            'fecha_identificacion_gap': calculo_nivel.calculado_at.date(),
            
            # Planificación
            'estrategia_cierre': request.data.get('estrategia_cierre', 'implementacion_nueva'),
            
            'alcance_proyecto': request.data.get('alcance_proyecto') or 
                               f'Cerrar brecha en {calculo_nivel.dimension.nombre}, '
                               f'pasando de nivel {calculo_nivel.nivel_actual} a {calculo_nivel.nivel_deseado}',
            
            'objetivos_especificos': request.data.get('objetivos_especificos') or 
                                    f'1. Reducir GAP de {calculo_nivel.gap} a 0\n'
                                    f'2. Alcanzar nivel {calculo_nivel.nivel_deseado} en {calculo_nivel.dimension.nombre}\n'
                                    f'3. Implementar controles faltantes\n'
                                    f'4. Documentar cumplimiento',
            
            'criterios_aceptacion': request.data.get('criterios_aceptacion') or 
                                   f'✓ Nivel actual >= {calculo_nivel.nivel_deseado}\n'
                                   f'✓ GAP <= 0.5\n'
                                   f'✓ Evidencias documentadas\n'
                                   f'✓ Validación de auditoría aprobada',
            
            'supuestos': request.data.get('supuestos', ''),
            'restricciones': request.data.get('restricciones', ''),
            'riesgos_proyecto': request.data.get('riesgos_proyecto', ''),
            
            # Responsables (requeridos)
            'dueno_proyecto': request.data.get('dueno_proyecto_id'),
            'responsable_implementacion': request.data.get('responsable_implementacion_id'),
            'equipo_implementacion': request.data.get('equipo_implementacion_ids', []),
            'validador_interno': request.data.get('validador_interno_id'),
            'auditor_verificacion': request.data.get('auditor_verificacion_id'),
            
            # Recursos
            'presupuesto_asignado': request.data.get('presupuesto_asignado', 0),
            'moneda': request.data.get('moneda', 'USD'),
            'recursos_humanos_asignados': request.data.get('recursos_humanos_asignados', 0),
            'recursos_tecnicos': request.data.get('recursos_tecnicos', ''),
            
            # Seguimiento
            'frecuencia_reporte': request.data.get('frecuencia_reporte', 'semanal'),
            'metricas_desempeno': request.data.get('metricas_desempeno', ''),
            'umbrales_alerta': request.data.get('umbrales_alerta', 'Retraso > 10% → Alerta\nRetraso > 25% → Escalación'),
            'canal_comunicacion': request.data.get('canal_comunicacion', 'email'),
            
            # Validación
            'criterios_validacion': request.data.get('criterios_validacion') or 
                                   f'Validar que se alcanzó nivel {calculo_nivel.nivel_deseado} mediante auditoría',
            
            'metodo_verificacion': request.data.get('metodo_verificacion', 'revision_documental'),
            'responsable_validacion': request.data.get('responsable_validacion_id'),
        }
        
        # ═══ 6. CREAR PROYECTO CON SERIALIZER ═══
        serializer = ProyectoCierreBrechaCreateSerializer(
            data=datos_proyecto,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return self.error_response(
                message='Error en validación de datos',
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        proyecto = serializer.save()
        
        # ═══ 7. VINCULAR PREGUNTAS NO CONFORMES AUTOMÁTICAMENTE ═══
        # Buscar respuestas "No Cumple" o "Cumple Parcial" en la asignación
        if calculo_nivel.asignacion:
            from apps.respuestas.models import Respuesta
            
            respuestas_problematicas = Respuesta.objects.filter(
                asignacion=calculo_nivel.asignacion,
                respuesta__in=['NO_CUMPLE', 'CUMPLE_PARCIAL'],
                activo=True
            ).select_related('pregunta')
            
            preguntas_ids = [r.pregunta.id for r in respuestas_problematicas]
            
            if preguntas_ids:
                proyecto.preguntas_abordadas.set(preguntas_ids)
        
        # ═══ 8. RESPUESTA ═══
        output_serializer = ProyectoCierreBrechaDetailSerializer(proyecto)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Proyecto {proyecto.codigo_proyecto} creado exitosamente desde GAP',
            status_code=status.HTTP_201_CREATED
        )
    
    def _mapear_prioridad_gap(self, clasificacion_gap):
        """Mapear clasificación de GAP a prioridad de proyecto"""
        mapeo = {
            'critico': 'critica',
            'alto': 'alta',
            'medio': 'media',
            'bajo': 'baja',
            'cumplido': 'baja',
            'superado': 'baja',
        }
        return mapeo.get(clasificacion_gap, 'media')
    
    def _mapear_criticidad(self, clasificacion_gap):
        """Mapear clasificación de GAP a nivel de criticidad (1-5)"""
        mapeo = {
            'critico': 5,
            'alto': 4,
            'medio': 3,
            'bajo': 2,
            'cumplido': 1,
            'superado': 1,
        }
        return mapeo.get(clasificacion_gap, 3)
    
    def _determinar_tipo_brecha(self, calculo_nivel):
        """Determinar tipo de brecha según el GAP"""
        # Analizar respuestas si están disponibles
        if calculo_nivel.respuestas_no_cumple > 0:
            return 'ausencia_total'
        elif calculo_nivel.respuestas_cumple_parcial > 0:
            return 'parcial'
        else:
            return 'no_efectiva'
    
    # ═══════════════════════════════════════════════════════════════
    # ENDPOINTS DE CONSULTA
    # ═══════════════════════════════════════════════════════════════
    
    @action(detail=False, methods=['get'])
    def mis_proyectos(self, request):
        """
        Obtener proyectos donde estoy asignado
        GET /api/proyectos-remediacion/mis_proyectos/
        
        Query params opcionales:
        - rol: 'dueno', 'responsable', 'equipo', 'validador', 'auditor'
        """
        user = request.user
        
        queryset = ProyectoCierreBrecha.objects.filter(activo=True)
        
        # Filtro por rol específico
        rol = request.query_params.get('rol')
        
        if rol == 'dueno':
            queryset = queryset.filter(dueno_proyecto=user)
        elif rol == 'responsable':
            queryset = queryset.filter(responsable_implementacion=user)
        elif rol == 'equipo':
            queryset = queryset.filter(equipo_implementacion=user)
        elif rol == 'validador':
            queryset = queryset.filter(validador_interno=user)
        elif rol == 'auditor':
            queryset = queryset.filter(auditor_verificacion=user)
        else:
            # Todos los proyectos donde estoy
            queryset = queryset.filter(
                Q(dueno_proyecto=user) |
                Q(responsable_implementacion=user) |
                Q(equipo_implementacion=user) |
                Q(validador_interno=user) |
                Q(auditor_verificacion=user) |
                Q(responsable_validacion=user)
            ).distinct()
        
        # Aplicar otros filtros
        estado = request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        queryset = queryset.order_by('-fecha_creacion')
        
        # Paginar
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProyectoCierreBrechaListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProyectoCierreBrechaListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas generales de proyectos
        GET /api/proyectos-remediacion/estadisticas/
        """
        user = request.user
        
        # Obtener queryset según permisos
        if user.rol == 'superadmin':
            queryset = ProyectoCierreBrecha.objects.filter(activo=True)
        elif user.rol == 'administrador' and user.empresa:
            queryset = ProyectoCierreBrecha.objects.filter(empresa=user.empresa, activo=True)
        else:
            queryset = ProyectoCierreBrecha.objects.filter(
                Q(dueno_proyecto=user) |
                Q(responsable_implementacion=user) |
                Q(equipo_implementacion=user)
            ).distinct().filter(activo=True)
        
        # Calcular estadísticas
        total_proyectos = queryset.count()
        
        # Por estado
        por_estado = {
            'planificado': queryset.filter(estado='planificado').count(),
            'en_ejecucion': queryset.filter(estado='en_ejecucion').count(),
            'en_validacion': queryset.filter(estado='en_validacion').count(),
            'cerrado': queryset.filter(estado='cerrado').count(),
            'suspendido': queryset.filter(estado='suspendido').count(),
            'cancelado': queryset.filter(estado='cancelado').count(),
        }
        
        # Por prioridad
        por_prioridad = {
            'critica': queryset.filter(prioridad='critica').count(),
            'alta': queryset.filter(prioridad='alta').count(),
            'media': queryset.filter(prioridad='media').count(),
            'baja': queryset.filter(prioridad='baja').count(),
        }
        
        # Por categoría
        por_categoria = {
            'tecnico': queryset.filter(categoria='tecnico').count(),
            'documental': queryset.filter(categoria='documental').count(),
            'procesal': queryset.filter(categoria='procesal').count(),
            'organizacional': queryset.filter(categoria='organizacional').count(),
            'capacitacion': queryset.filter(categoria='capacitacion').count(),
        }
        
        # Vencidos
        vencidos = queryset.filter(
            fecha_fin_estimada__lt=timezone.now().date(),
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).count()
        
        # Próximos a vencer (próximos 7 días)
        from datetime import timedelta
        fecha_limite = timezone.now().date() + timedelta(days=7)
        proximos_vencer = queryset.filter(
            fecha_fin_estimada__lte=fecha_limite,
            fecha_fin_estimada__gte=timezone.now().date(),
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).count()
        
        # Presupuesto
        presupuesto_total = queryset.aggregate(Sum('presupuesto_asignado'))['presupuesto_asignado__sum'] or 0
        presupuesto_gastado = queryset.aggregate(Sum('presupuesto_gastado'))['presupuesto_gastado__sum'] or 0
        
        return Response({
            'total_proyectos': total_proyectos,
            'por_estado': por_estado,
            'por_prioridad': por_prioridad,
            'por_categoria': por_categoria,
            'alertas': {
                'vencidos': vencidos,
                'proximos_a_vencer': proximos_vencer,
            },
            'presupuesto': {
                'total_asignado': float(presupuesto_total),
                'total_gastado': float(presupuesto_gastado),
                'disponible': float(presupuesto_total - presupuesto_gastado),
                'porcentaje_gastado': round((presupuesto_gastado / presupuesto_total * 100) if presupuesto_total > 0 else 0, 2)
            }
        })
    
    @action(detail=False, methods=['get'])
    def por_estado(self, request):
        """
        Proyectos agrupados por estado
        GET /api/proyectos-remediacion/por_estado/
        """
        queryset = self.get_queryset()
        
        estado = request.query_params.get('estado')
        if not estado:
            return self.error_response(
                message='Parámetro "estado" requerido',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        proyectos = queryset.filter(estado=estado).order_by('-fecha_creacion')
        
        serializer = ProyectoCierreBrechaListSerializer(proyectos, many=True)
        
        return Response({
            'estado': estado,
            'count': proyectos.count(),
            'proyectos': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def vencidos(self, request):
        """
        Proyectos vencidos (fecha_fin_estimada pasada y no cerrados)
        GET /api/proyectos-remediacion/vencidos/
        """
        queryset = self.get_queryset()
        
        proyectos_vencidos = queryset.filter(
            fecha_fin_estimada__lt=timezone.now().date(),
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).order_by('fecha_fin_estimada')
        
        serializer = ProyectoCierreBrechaListSerializer(proyectos_vencidos, many=True)
        
        return Response({
            'count': proyectos_vencidos.count(),
            'proyectos': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def proximos_a_vencer(self, request):
        """
        Proyectos próximos a vencer (próximos N días)
        GET /api/proyectos-remediacion/proximos_a_vencer/?dias=7
        """
        from datetime import timedelta
        
        dias = int(request.query_params.get('dias', 7))
        
        queryset = self.get_queryset()
        
        fecha_limite = timezone.now().date() + timedelta(days=dias)
        
        proyectos = queryset.filter(
            fecha_fin_estimada__lte=fecha_limite,
            fecha_fin_estimada__gte=timezone.now().date(),
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).order_by('fecha_fin_estimada')
        
        serializer = ProyectoCierreBrechaListSerializer(proyectos, many=True)
        
        return Response({
            'dias': dias,
            'count': proyectos.count(),
            'proyectos': serializer.data
        })