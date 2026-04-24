# apps/proyectos_remediacion/views/proyecto_views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta, date

from apps.proyectos_remediacion.models import ProyectoCierreBrecha, ItemProyecto
from apps.proyectos_remediacion.serializers import (
    ProyectoCierreBrechaListSerializer,
    ProyectoCierreBrechaDetailSerializer,
    ProyectoCierreBrechaCreateSerializer,
    ProyectoCierreBrechaUpdateSerializer,
    ItemProyectoListSerializer,
    ItemProyectoDetailSerializer,
    ItemProyectoCreateUpdateSerializer,
)
from apps.proyectos_remediacion.views.aprobacion_views import AprobacionMixin
from apps.core.permissions import EsAdminOSuperAdmin
from apps.core.mixins import ResponseMixin
from apps.respuestas.models import CalculoNivel
from apps.encuestas.models import EvaluacionEmpresa
from apps.respuestas.models import CalculoNivel

class ProyectoCierreBrechaViewSet(AprobacionMixin, ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet principal para Proyectos de Cierre de Brecha.
    Hereda AprobacionMixin para los endpoints de aprobación.

    ENDPOINTS CRUD:
    - GET    /api/proyectos-remediacion/               → Listar
    - GET    /api/proyectos-remediacion/{id}/          → Detalle
    - POST   /api/proyectos-remediacion/               → Crear
    - PATCH  /api/proyectos-remediacion/{id}/          → Actualizar
    - DELETE /api/proyectos-remediacion/{id}/          → Desactivar

    ENDPOINTS DE ÍTEMS:
    - GET    .../items/
    - POST   .../agregar-item/
    - PATCH  .../actualizar-item/
    - DELETE .../eliminar-item/
    - POST   .../reordenar-items/
    - POST   .../completar_item/

    ENDPOINTS DE CONSULTA:
    - GET    .../mis_proyectos/
    - GET    .../estadisticas/
    - GET    .../vencidos/
    - GET    .../proximos_a_vencer/
    - GET    .../por_dimension_y_evaluacion/
    - POST   .../crear_desde_gap/

    ENDPOINTS DE APROBACIÓN (heredados de AprobacionMixin):
    - POST   .../solicitar_aprobacion/
    - POST   .../aprobar_cierre_gap/
    - POST   .../rechazar_cierre_gap/
    - GET    .../aprobaciones_pendientes/
    """

    permission_classes = [IsAuthenticated]
    http_method_names  = ['get', 'post', 'patch', 'delete']

    # ── Serializer ────────────────────────────────────────────────────────────

    def get_serializer_class(self):
        if self.action == 'list':
            return ProyectoCierreBrechaListSerializer
        elif self.action == 'retrieve':
            return ProyectoCierreBrechaDetailSerializer
        elif self.action in ['create', 'crear_desde_gap']:
            return ProyectoCierreBrechaCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProyectoCierreBrechaUpdateSerializer
        return ProyectoCierreBrechaDetailSerializer

    # ── Queryset ──────────────────────────────────────────────────────────────

    def get_queryset(self):
        user = self.request.user

        queryset = ProyectoCierreBrecha.objects.select_related(
            'empresa',
            'calculo_nivel',
            'calculo_nivel__dimension',
            'dueno_proyecto',
            'responsable_implementacion',
            'validador_interno',
            'creado_por',
        ).prefetch_related(
            'preguntas_abordadas',
            'items',
            'items__proveedor',
            'items__responsable_ejecucion',
        ).filter(activo=True)

        # ─── Filtro por rol ───────────────────────────────────────────────────
        if user.rol == 'superadmin':
            pass
        elif user.rol == 'administrador':
            queryset = queryset.filter(empresa=user.empresa) if user.empresa else queryset.none()
        else:
            queryset = queryset.filter(
                Q(dueno_proyecto=user) |
                Q(responsable_implementacion=user) |
                Q(validador_interno=user) |
                Q(items__responsable_ejecucion=user)
            ).distinct()

        # ─── Filtros adicionales ──────────────────────────────────────────────
        params = self.request.query_params

        if params.get('calculo_nivel'):
            queryset = queryset.filter(calculo_nivel_id=params['calculo_nivel'])
        if params.get('estado'):
            queryset = queryset.filter(estado=params['estado'])
        if params.get('prioridad'):
            queryset = queryset.filter(prioridad=params['prioridad'])
        if params.get('categoria'):
            queryset = queryset.filter(categoria=params['categoria'])
        if params.get('modo_presupuesto'):
            queryset = queryset.filter(modo_presupuesto=params['modo_presupuesto'])
        if params.get('empresa') and user.rol == 'superadmin':
            queryset = queryset.filter(empresa_id=params['empresa'])
        if params.get('search'):
            search = params['search']
            queryset = queryset.filter(
                Q(codigo_proyecto__icontains=search) |
                Q(nombre_proyecto__icontains=search) |
                Q(descripcion__icontains=search)
            )

        ordering = params.get('ordering', '-fecha_creacion')
        return queryset.order_by(ordering)

    # ── Permisos por acción ───────────────────────────────────────────────────

    def get_permissions(self):
        if self.action in ['create', 'crear_desde_gap', 'update', 'partial_update',
                           'destroy', 'agregar_item', 'actualizar_item', 'eliminar_item']:
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        return [IsAuthenticated()]

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proyecto = serializer.save()

        return self.success_response(
            data=ProyectoCierreBrechaDetailSerializer(proyecto).data,
            message=f'Proyecto {proyecto.codigo_proyecto} creado exitosamente',
            status_code=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial  = kwargs.pop('partial', False)
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        proyecto = serializer.save()

        return self.success_response(
            data=ProyectoCierreBrechaDetailSerializer(proyecto).data,
            message=f'Proyecto {proyecto.codigo_proyecto} actualizado exitosamente'
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.estado == 'cerrado':
            return self.error_response(
                message='No se puede eliminar un proyecto cerrado',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if instance.modo_presupuesto == 'por_items':
            instance.items.update(activo=False)

        instance.activo = False
        instance.estado = 'cancelado'
        instance.save()

        return self.success_response(
            message=f'Proyecto {instance.codigo_proyecto} desactivado exitosamente',
            status_code=status.HTTP_204_NO_CONTENT
        )

    # ── Gestión de ítems ──────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='items')
    def listar_items(self, request, pk=None):
        """GET /api/proyectos-remediacion/{id}/items/"""
        proyecto = self.get_object()

        if proyecto.modo_presupuesto != 'por_items':
            return self.error_response(
                message='Este proyecto no está en modo "por_items"',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        items = proyecto.items.filter(activo=True).select_related(
            'proveedor', 'responsable_ejecucion', 'item_dependencia'
        ).order_by('numero_item')

        if request.query_params.get('estado'):
            items = items.filter(estado=request.query_params['estado'])

        requiere_proveedor = request.query_params.get('requiere_proveedor')
        if requiere_proveedor is not None:
            items = items.filter(requiere_proveedor=requiere_proveedor.lower() == 'true')

        return Response({
            'success': True,
            'data': {
                'proyecto_id':     str(proyecto.id),
                'codigo_proyecto': proyecto.codigo_proyecto,
                'total_items':     items.count(),
                'items':           ItemProyectoListSerializer(items, many=True).data,
                'resumen': {
                    'total_presupuesto_planificado': sum(i.presupuesto_planificado for i in items),
                    'total_presupuesto_ejecutado':   sum(i.presupuesto_ejecutado   for i in items),
                    'items_completados':             items.filter(estado='completado').count(),
                    'items_bloqueados':              items.filter(estado='bloqueado').count(),
                },
            }
        })

    @action(detail=True, methods=['post'], url_path='agregar-item',
            permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def agregar_item(self, request, pk=None):
        """POST /api/proyectos-remediacion/{id}/agregar-item/"""
        proyecto = self.get_object()

        if proyecto.modo_presupuesto != 'por_items':
            return self.error_response(
                message='Este proyecto no está en modo "por_items"',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        ultimo     = proyecto.items.filter(activo=True).order_by('-numero_item').first()
        numero_item = (ultimo.numero_item + 1) if ultimo else 1

        data = request.data.copy()
        data['proyecto']    = proyecto.id
        data['numero_item'] = numero_item

        for old_key, new_key in [('proveedor_id', 'proveedor'),
                                  ('responsable_ejecucion_id', 'responsable_ejecucion'),
                                  ('item_dependencia_id', 'item_dependencia')]:
            if old_key in data:
                data[new_key] = data.pop(old_key)

        serializer = ItemProyectoCreateUpdateSerializer(data=data)
        if not serializer.is_valid():
            return self.error_response(
                message='Error en validación de datos',
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        item = serializer.save()

        if item.tiene_dependencia and not item.puede_iniciar:
            item.estado = 'bloqueado'
            item.save()

        return self.success_response(
            data=ItemProyectoDetailSerializer(item).data,
            message=f'Ítem #{numero_item} agregado exitosamente',
            status_code=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['patch'], url_path='actualizar-item',
            permission_classes=[IsAuthenticated])
    def actualizar_item(self, request, pk=None):
        """PATCH /api/proyectos-remediacion/{id}/actualizar-item/"""
        proyecto = self.get_object()
        user     = request.user
        item_id  = request.data.get('item_id')

        if not item_id:
            return self.error_response(message='El campo item_id es requerido',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        try:
            item = proyecto.items.get(id=item_id, activo=True)
        except ItemProyecto.DoesNotExist:
            return self.error_response(message='Ítem no encontrado en este proyecto',
                                       status_code=status.HTTP_404_NOT_FOUND)

        es_responsable = item.responsable_ejecucion == user or proyecto.dueno_proyecto == user
        if user.rol not in ['superadmin', 'administrador'] and not es_responsable:
            return self.error_response(message='No tienes permisos para actualizar este ítem',
                                       status_code=status.HTTP_403_FORBIDDEN)

        nuevo_estado = request.data.get('estado')
        if nuevo_estado in ['en_proceso', 'completado'] and not item.puede_iniciar:
            dep_info = f' #{item.item_dependencia.numero_item}' if item.item_dependencia else ''
            return self.error_response(
                message=f'El ítem está bloqueado. Debe completarse primero el ítem antecedente{dep_info}.',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        datos_update = request.data.copy()

        if float(datos_update.get('porcentaje_avance', 0)) >= 100:
            datos_update['estado'] = 'completado'

        if datos_update.get('estado') == 'completado':
            datos_update['porcentaje_avance'] = 100
            if not item.fecha_completado:
                item.fecha_completado = timezone.now().date()

        serializer = ItemProyectoCreateUpdateSerializer(
            item, data=datos_update, partial=True, context={'request': request}
        )
        if not serializer.is_valid():
            return self.error_response(message='Error en validación de datos',
                                       errors=serializer.errors,
                                       status_code=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                item_actualizado = serializer.save()

                if item_actualizado.estado == 'completado':
                    for dep in item_actualizado.items_dependientes.filter(estado='bloqueado', activo=True):
                        if dep.puede_iniciar:
                            dep.estado = 'pendiente'
                            dep.save(update_fields=['estado'])

                return self.success_response(
                    data=ItemProyectoDetailSerializer(item_actualizado).data,
                    message=f'Ítem #{item_actualizado.numero_item} actualizado exitosamente'
                )
        except Exception as e:
            return self.error_response(message=f'Error al procesar: {str(e)}',
                                       status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='eliminar-item',
            permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def eliminar_item(self, request, pk=None):
        """DELETE /api/proyectos-remediacion/{id}/eliminar-item/?item_id=xxx"""
        proyecto = self.get_object()
        item_id  = request.query_params.get('item_id')

        if not item_id:
            return self.error_response(message='Se requiere item_id',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        try:
            item = proyecto.items.get(id=item_id, activo=True)
        except ItemProyecto.DoesNotExist:
            return self.error_response(message='Ítem no encontrado',
                                       status_code=status.HTTP_404_NOT_FOUND)

        if item.items_dependientes.filter(activo=True).exists():
            return self.error_response(message='No se puede eliminar. Otros ítems dependen de este',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        item.activo = False
        item.save()

        return self.success_response(
            message=f'Ítem #{item.numero_item} eliminado exitosamente',
            status_code=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['post'], url_path='reordenar-items',
            permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def reordenar_items(self, request, pk=None):
        """POST /api/proyectos-remediacion/{id}/reordenar-items/"""
        proyecto = self.get_object()
        orden    = request.data.get('orden', [])

        if not orden:
            return self.error_response(message='Se requiere "orden" con lista de IDs',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for idx, item_id in enumerate(orden, start=1):
                try:
                    item            = proyecto.items.get(id=item_id, activo=True)
                    item.numero_item = idx
                    item.save()
                except ItemProyecto.DoesNotExist:
                    return self.error_response(message=f'Ítem {item_id} no encontrado',
                                               status_code=status.HTTP_404_NOT_FOUND)

        return self.success_response(message='Ítems reordenados exitosamente')

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def completar_item(self, request, pk=None):
        """POST /api/proyectos-remediacion/{id}/completar_item/"""
        proyecto = self.get_object()
        item_id  = request.data.get('item_id')

        if not item_id:
            return self.error_response(message='El campo item_id es requerido',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        try:
            item = ItemProyecto.objects.get(id=item_id, proyecto=proyecto, activo=True)
        except ItemProyecto.DoesNotExist:
            return self.error_response(message='Ítem no encontrado',
                                       status_code=status.HTTP_404_NOT_FOUND)

        item.estado           = 'completado'
        item.porcentaje_avance = 100
        item.fecha_completado  = date.today()

        update_fields = ['estado', 'porcentaje_avance', 'fecha_completado']
        if 'observaciones' in request.data:
            item.observaciones = request.data['observaciones']
            update_fields.append('observaciones')

        item.save(update_fields=update_fields)

        return self.success_response(
            data=ItemProyectoListSerializer(item).data,
            message=f'Ítem #{item.numero_item} marcado como completado'
        )

    # ── Endpoints de consulta ─────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def crear_desde_gap(self, request):
        """POST /api/proyectos-remediacion/crear_desde_gap/"""
        calculo_nivel_id = request.data.get('calculo_nivel_id')
        if not calculo_nivel_id:
            return self.error_response(message='Se requiere calculo_nivel_id',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        try:
            calculo_nivel = CalculoNivel.objects.select_related(
                'dimension', 'empresa', 'asignacion'
            ).get(id=calculo_nivel_id, activo=True)
        except CalculoNivel.DoesNotExist:
            return self.error_response(message='GAP no encontrado',
                                       status_code=status.HTTP_404_NOT_FOUND)

        user = request.user
        if user.rol == 'administrador' and calculo_nivel.empresa != user.empresa:
            return self.error_response(
                message='Solo puedes crear proyectos para GAPs de tu empresa',
                status_code=status.HTTP_403_FORBIDDEN
            )

        proyectos_previos_count = ProyectoCierreBrecha.objects.filter(
            calculo_nivel=calculo_nivel, activo=True
        ).count()

        nombre_base = request.data.get('nombre_proyecto') or f'Remediación: {calculo_nivel.dimension.nombre}'
        if proyectos_previos_count > 0:
            nombre_base = f'{nombre_base} (Fase {proyectos_previos_count + 1})'

        # ─── Determinar validador automático ──────────────────────────────────
        validador_id = request.data.get('validador_interno_id')
        if not validador_id:
            try:
                asignacion = calculo_nivel.asignacion
                if asignacion:
                    validador_id = (
                        asignacion.asignado_por.id if asignacion.asignado_por
                        else asignacion.evaluacion_empresa.administrador.id
                    )
                else:
                    validador_id = request.user.id
            except Exception:
                validador_id = request.user.id

        datos_proyecto = {
            'calculo_nivel':           calculo_nivel.id,
            'nombre_proyecto':         nombre_base,
            'descripcion':             request.data.get('descripcion') or
                                       f'Proyecto para cerrar brecha en {calculo_nivel.dimension.nombre}. '
                                       f'GAP: {calculo_nivel.gap} ({calculo_nivel.get_clasificacion_gap_display()})',
            'fecha_inicio':            request.data.get('fecha_inicio'),
            'fecha_fin_estimada':      request.data.get('fecha_fin_estimada'),
            'prioridad':               self._mapear_prioridad_gap(calculo_nivel.clasificacion_gap),
            'categoria':               request.data.get('categoria', 'tecnico'),
            'modo_presupuesto':        request.data.get('modo_presupuesto', 'global'),
            'moneda':                  request.data.get('moneda', 'USD'),
            'presupuesto_global':      request.data.get('presupuesto_global', 0),
            'alcance_proyecto':        request.data.get('alcance_proyecto') or
                                       f'Cerrar brecha en {calculo_nivel.dimension.nombre}',
            'objetivos_especificos':   request.data.get('objetivos_especificos') or
                                       f'1. Reducir GAP de {calculo_nivel.gap} a 0\n'
                                       f'2. Alcanzar nivel {calculo_nivel.nivel_deseado}',
            'criterios_aceptacion':    request.data.get('criterios_aceptacion') or
                                       f'✓ Nivel actual >= {calculo_nivel.nivel_deseado}\n✓ GAP <= 0.5',
            'riesgos_proyecto':        request.data.get('riesgos_proyecto', ''),
            'dueno_proyecto':          request.data.get('dueno_proyecto_id'),
            'responsable_implementacion': request.data.get('responsable_implementacion_id'),
            'validador_interno':       validador_id,
        }

        serializer = ProyectoCierreBrechaCreateSerializer(
            data=datos_proyecto, context={'request': request}
        )
        if not serializer.is_valid():
            return self.error_response(message='Error en validación de datos',
                                       errors=serializer.errors,
                                       status_code=status.HTTP_400_BAD_REQUEST)

        proyecto = serializer.save()

        # Vincular preguntas no conformes automáticamente
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

        return self.success_response(
            data=ProyectoCierreBrechaDetailSerializer(proyecto).data,
            message=f'Proyecto {proyecto.codigo_proyecto} creado exitosamente desde GAP',
            status_code=status.HTTP_201_CREATED
        )

# ═══════════════════════════════════════════════════════════════
# AGREGAR ESTE MÉTODO DENTRO DE ProyectoCierreBrechaViewSet
# ═══════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'])
    def dashboard_cumplimiento(self, request):
        """
        Dashboard de cumplimiento de una evaluación.
        GET /api/proyectos-remediacion/dashboard_cumplimiento/

        Query params:
            evaluacion_id   (requerido) — UUID de EvaluacionEmpresa
            fecha_desde     (opcional)  — YYYY-MM-DD
            fecha_hasta     (opcional)  — YYYY-MM-DD
            estado_proyecto (opcional)  — planificado | en_ejecucion | en_validacion | cerrado
        """
        from apps.encuestas.models import EvaluacionEmpresa

        user          = request.user
        evaluacion_id = request.query_params.get('evaluacion_id')

        if not evaluacion_id:
            return self.error_response(
                message='Se requiere evaluacion_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # ─── Obtener evaluación ───────────────────────────────────────────────
        try:
            evaluacion = EvaluacionEmpresa.objects.select_related(
                'empresa', 'encuesta'
            ).get(id=evaluacion_id, activo=True)
        except EvaluacionEmpresa.DoesNotExist:
            return self.error_response(
                message='Evaluación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )

        # ─── Validar permisos ─────────────────────────────────────────────────
        if user.rol == 'administrador' and evaluacion.empresa != user.empresa:
            return self.error_response(
                message='No tienes permisos para ver esta evaluación',
                status_code=status.HTTP_403_FORBIDDEN
            )

        # ─── Filtros opcionales ───────────────────────────────────────────────
        params      = request.query_params
        fecha_desde = params.get('fecha_desde')
        fecha_hasta = params.get('fecha_hasta')
        estado_filtro = params.get('estado_proyecto')

        # ─── 1. CÁLCULOS DE NIVEL (brechas) ──────────────────────────────────
        calculos_qs = CalculoNivel.objects.filter(
            evaluacion_empresa=evaluacion,
            activo=True
        ).select_related('dimension', 'asignacion')

        if fecha_desde:
            calculos_qs = calculos_qs.filter(calculado_at__date__gte=fecha_desde)
        if fecha_hasta:
            calculos_qs = calculos_qs.filter(calculado_at__date__lte=fecha_hasta)

        calculos = list(calculos_qs)

        # ─── 2. PROYECTOS DE REMEDIACIÓN ──────────────────────────────────────
        proyectos_qs = ProyectoCierreBrecha.objects.filter(
            calculo_nivel__in=calculos_qs,
            activo=True
        ).select_related('calculo_nivel', 'calculo_nivel__dimension')

        if estado_filtro:
            proyectos_qs = proyectos_qs.filter(estado=estado_filtro)

        proyectos = list(proyectos_qs)

        # Mapear calculo_nivel_id → proyecto (el más reciente si hay varios)
        mapa_proyectos = {}
        for p in proyectos:
            cid = str(p.calculo_nivel_id)
            if cid not in mapa_proyectos:
                mapa_proyectos[cid] = p
            else:
                # Quedarse con el más reciente
                if p.fecha_creacion > mapa_proyectos[cid].fecha_creacion:
                    mapa_proyectos[cid] = p

        # ─── 3. RESUMEN GENERAL ───────────────────────────────────────────────
        total_dimensiones     = len(calculos)
        nivel_promedio_actual = (
            sum(float(c.nivel_actual) for c in calculos) / total_dimensiones
            if total_dimensiones > 0 else 0
        )
        nivel_promedio_deseado = (
            sum(float(c.nivel_deseado) for c in calculos) / total_dimensiones
            if total_dimensiones > 0 else 0
        )
        porcentaje_cumplimiento_global = (
            sum(
                min(float(c.nivel_actual) / float(c.nivel_deseado) * 100, 100)
                for c in calculos
                if float(c.nivel_deseado) > 0
            ) / total_dimensiones
            if total_dimensiones > 0 else 0
        )

        # ─── 4. BRECHAS POR ESTADO ────────────────────────────────────────────
        brechas_criticas  = sum(1 for c in calculos if c.clasificacion_gap == 'critico')
        brechas_altas     = sum(1 for c in calculos if c.clasificacion_gap == 'alto')
        brechas_medias    = sum(1 for c in calculos if c.clasificacion_gap == 'medio')
        brechas_bajas     = sum(1 for c in calculos if c.clasificacion_gap == 'bajo')
        brechas_cumplidas = sum(1 for c in calculos if c.clasificacion_gap in ['cumplido', 'superado'])

        # Brechas remediadas (CalculoNivel con remediado=True)
        brechas_remediadas = sum(1 for c in calculos if getattr(c, 'remediado', False))
        brechas_abiertas   = total_dimensiones - brechas_cumplidas - brechas_remediadas

        # ─── 5. ESTADO DE PROYECTOS ───────────────────────────────────────────
        total_proyectos      = len(proyectos)
        proyectos_planificados = sum(1 for p in proyectos if p.estado == 'planificado')
        proyectos_ejecucion  = sum(1 for p in proyectos if p.estado == 'en_ejecucion')
        proyectos_validacion = sum(1 for p in proyectos if p.estado == 'en_validacion')
        proyectos_cerrados   = sum(1 for p in proyectos if p.estado == 'cerrado')
        proyectos_vencidos   = sum(1 for p in proyectos if p.esta_vencido)

        # ─── 6. GAP POR DIMENSIÓN (detalle) ──────────────────────────────────
        gap_por_dimension = []
        for calculo in sorted(calculos, key=lambda c: float(c.gap), reverse=True):
            cid     = str(calculo.id)
            proyecto = mapa_proyectos.get(str(calculo.id))

            gap_por_dimension.append({
                'calculo_id':              cid,
                'dimension_id':            str(calculo.dimension.id),
                'dimension_nombre':        calculo.dimension.nombre,
                'dimension_codigo':        calculo.dimension.codigo,
                'nivel_actual':            float(calculo.nivel_actual),
                'nivel_deseado':           float(calculo.nivel_deseado),
                'gap':                     float(calculo.gap),
                'clasificacion_gap':       calculo.clasificacion_gap,
                'clasificacion_gap_display': calculo.get_clasificacion_gap_display(),
                'porcentaje_cumplimiento': round(
                    min(float(calculo.nivel_actual) / float(calculo.nivel_deseado) * 100, 100)
                    if float(calculo.nivel_deseado) > 0 else 0,
                    2
                ),
                'remediado':               getattr(calculo, 'remediado', False),
                'fecha_remediacion':       getattr(calculo, 'fecha_remediacion', None),
                # Resumen de respuestas
                'respuestas': {
                    'total':           calculo.total_preguntas,
                    'si_cumple':       calculo.respuestas_si_cumple,
                    'cumple_parcial':  calculo.respuestas_cumple_parcial,
                    'no_cumple':       calculo.respuestas_no_cumple,
                    'no_aplica':       calculo.respuestas_no_aplica,
                },
                # Proyecto asociado (si existe)
                'proyecto': {
                    'id':                    str(proyecto.id),
                    'codigo_proyecto':        proyecto.codigo_proyecto,
                    'nombre_proyecto':        proyecto.nombre_proyecto,
                    'estado':                 proyecto.estado,
                    'estado_display':         proyecto.get_estado_display(),
                    'prioridad':              proyecto.prioridad,
                    'fecha_fin_estimada':     proyecto.fecha_fin_estimada,
                    'esta_vencido':           proyecto.esta_vencido,
                    'porcentaje_avance_items': proyecto.porcentaje_avance_items,
                    'presupuesto_total_planificado': float(proyecto.presupuesto_total_planificado),
                    'presupuesto_total_ejecutado':   float(proyecto.presupuesto_total_ejecutado),
                } if proyecto else None,
            })

        # ─── 7. EVOLUCIÓN PRESUPUESTAL ────────────────────────────────────────
        presupuesto_total_planificado = sum(
            float(p.presupuesto_total_planificado) for p in proyectos
        )
        presupuesto_total_ejecutado = sum(
            float(p.presupuesto_total_ejecutado) for p in proyectos
        )

        # ─── 8. ALERTAS ───────────────────────────────────────────────────────
        alertas = []

        if brechas_criticas > 0:
            alertas.append({
                'tipo':     'critico',
                'mensaje':  f'{brechas_criticas} dimensión(es) con brecha CRÍTICA sin proyecto de remediación',
                'cantidad': brechas_criticas,
            })

        if proyectos_vencidos > 0:
            alertas.append({
                'tipo':     'vencido',
                'mensaje':  f'{proyectos_vencidos} proyecto(s) vencido(s) sin cerrar',
                'cantidad': proyectos_vencidos,
            })

        brechas_sin_proyecto = sum(
            1 for c in calculos
            if c.clasificacion_gap not in ['cumplido', 'superado']
            and not getattr(c, 'remediado', False)
            and str(c.id) not in mapa_proyectos
        )
        if brechas_sin_proyecto > 0:
            alertas.append({
                'tipo':     'advertencia',
                'mensaje':  f'{brechas_sin_proyecto} brecha(s) sin proyecto de remediación asignado',
                'cantidad': brechas_sin_proyecto,
            })

        # ─── RESPUESTA FINAL ──────────────────────────────────────────────────
        return Response({
            'success': True,
            'evaluacion': {
                'id':              str(evaluacion.id),
                'nombre':          str(evaluacion),
                'empresa':         evaluacion.empresa.nombre,
                'encuesta':        evaluacion.encuesta.nombre if evaluacion.encuesta else '',
                'estado':          evaluacion.estado,
            },
            'resumen': {
                'total_dimensiones':             total_dimensiones,
                'nivel_promedio_actual':          round(nivel_promedio_actual, 2),
                'nivel_promedio_deseado':         round(nivel_promedio_deseado, 2),
                'porcentaje_cumplimiento_global': round(porcentaje_cumplimiento_global, 2),
            },
            'brechas': {
                'total':      total_dimensiones,
                'criticas':   brechas_criticas,
                'altas':      brechas_altas,
                'medias':     brechas_medias,
                'bajas':      brechas_bajas,
                'cumplidas':  brechas_cumplidas,
                'remediadas': brechas_remediadas,
                'abiertas':   brechas_abiertas,
            },
            'proyectos': {
                'total':        total_proyectos,
                'planificados': proyectos_planificados,
                'en_ejecucion': proyectos_ejecucion,
                'en_validacion': proyectos_validacion,
                'cerrados':     proyectos_cerrados,
                'vencidos':     proyectos_vencidos,
            },
            'presupuesto': {
                'total_planificado': round(presupuesto_total_planificado, 2),
                'total_ejecutado':   round(presupuesto_total_ejecutado, 2),
                'disponible':        round(presupuesto_total_planificado - presupuesto_total_ejecutado, 2),
                'porcentaje_gastado': round(
                    (presupuesto_total_ejecutado / presupuesto_total_planificado * 100)
                    if presupuesto_total_planificado > 0 else 0, 2
                ),
            },
            'gap_por_dimension': gap_por_dimension,
            'alertas':           alertas,
        })

    def _mapear_prioridad_gap(self, clasificacion_gap):
        return {
            'critico':  'critica',
            'alto':     'alta',
            'medio':    'media',
            'bajo':     'baja',
            'cumplido': 'baja',
            'superado': 'baja',
        }.get(clasificacion_gap, 'media')

    @action(detail=False, methods=['get'])
    def mis_proyectos(self, request):
        """GET /api/proyectos-remediacion/mis_proyectos/"""
        user = request.user

        queryset = ProyectoCierreBrecha.objects.filter(activo=True).filter(
            Q(dueno_proyecto=user) |
            Q(responsable_implementacion=user) |
            Q(validador_interno=user) |
            Q(items__responsable_ejecucion=user)
        ).distinct()

        if request.query_params.get('estado'):
            queryset = queryset.filter(estado=request.query_params['estado'])

        queryset = queryset.order_by('-fecha_creacion')

        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                ProyectoCierreBrechaListSerializer(page, many=True).data
            )

        return Response(ProyectoCierreBrechaListSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """GET /api/proyectos-remediacion/estadisticas/"""
        user = request.user

        if user.rol == 'superadmin':
            queryset = ProyectoCierreBrecha.objects.filter(activo=True)
        elif user.rol == 'administrador' and user.empresa:
            queryset = ProyectoCierreBrecha.objects.filter(empresa=user.empresa, activo=True)
        else:
            queryset = ProyectoCierreBrecha.objects.filter(
                Q(dueno_proyecto=user) | Q(responsable_implementacion=user)
            ).distinct().filter(activo=True)

        hoy          = timezone.now().date()
        fecha_limite = hoy + timedelta(days=7)

        presupuesto_planificado = sum(float(p.presupuesto_total_planificado) for p in queryset)
        presupuesto_ejecutado   = sum(float(p.presupuesto_total_ejecutado)   for p in queryset)

        return Response({
            'total_proyectos': queryset.count(),
            'por_estado': {
                'planificado':   queryset.filter(estado='planificado').count(),
                'en_ejecucion':  queryset.filter(estado='en_ejecucion').count(),
                'en_validacion': queryset.filter(estado='en_validacion').count(),
                'cerrado':       queryset.filter(estado='cerrado').count(),
                'suspendido':    queryset.filter(estado='suspendido').count(),
                'cancelado':     queryset.filter(estado='cancelado').count(),
            },
            'por_prioridad': {
                'critica': queryset.filter(prioridad='critica').count(),
                'alta':    queryset.filter(prioridad='alta').count(),
                'media':   queryset.filter(prioridad='media').count(),
                'baja':    queryset.filter(prioridad='baja').count(),
            },
            'por_modo_presupuesto': {
                'global':    queryset.filter(modo_presupuesto='global').count(),
                'por_items': queryset.filter(modo_presupuesto='por_items').count(),
            },
            'alertas': {
                'vencidos':          queryset.filter(fecha_fin_estimada__lt=hoy,
                                                     estado__in=['planificado', 'en_ejecucion', 'en_validacion']).count(),
                'proximos_a_vencer': queryset.filter(fecha_fin_estimada__lte=fecha_limite,
                                                     fecha_fin_estimada__gte=hoy,
                                                     estado__in=['planificado', 'en_ejecucion', 'en_validacion']).count(),
            },
            'presupuesto': {
                'total_planificado': round(presupuesto_planificado, 2),
                'total_ejecutado':   round(presupuesto_ejecutado,   2),
                'disponible':        round(presupuesto_planificado - presupuesto_ejecutado, 2),
                'porcentaje_gastado': round(
                    (presupuesto_ejecutado / presupuesto_planificado * 100)
                    if presupuesto_planificado > 0 else 0, 2
                ),
            },
        })

    @action(detail=False, methods=['get'])
    def vencidos(self, request):
        """GET /api/proyectos-remediacion/vencidos/"""
        proyectos = self.get_queryset().filter(
            fecha_fin_estimada__lt=timezone.now().date(),
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).order_by('fecha_fin_estimada')

        return Response({
            'count':     proyectos.count(),
            'proyectos': ProyectoCierreBrechaListSerializer(proyectos, many=True).data,
        })

    @action(detail=False, methods=['get'])
    def proximos_a_vencer(self, request):
        """GET /api/proyectos-remediacion/proximos_a_vencer/?dias=7"""
        dias         = int(request.query_params.get('dias', 7))
        hoy          = timezone.now().date()
        fecha_limite = hoy + timedelta(days=dias)

        proyectos = self.get_queryset().filter(
            fecha_fin_estimada__lte=fecha_limite,
            fecha_fin_estimada__gte=hoy,
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).order_by('fecha_fin_estimada')

        return Response({
            'dias':      dias,
            'count':     proyectos.count(),
            'proyectos': ProyectoCierreBrechaListSerializer(proyectos, many=True).data,
        })

    @action(detail=False, methods=['get'])
    def por_dimension_y_evaluacion(self, request):
        """GET /api/proyectos-remediacion/por_dimension_y_evaluacion/?dimension_id=X&evaluacion_id=Y"""
        dimension_id  = request.query_params.get('dimension_id')
        evaluacion_id = request.query_params.get('evaluacion_id')

        if not dimension_id:
            return self.error_response(message='Se requiere dimension_id',
                                       status_code=status.HTTP_400_BAD_REQUEST)
        if not evaluacion_id:
            return self.error_response(message='Se requiere evaluacion_id',
                                       status_code=status.HTTP_400_BAD_REQUEST)

        calculos = CalculoNivel.objects.filter(
            dimension_id=dimension_id,
            evaluacion_id=evaluacion_id,
            activo=True
        )

        if not calculos.exists():
            return Response({
                'success': True,
                'dimension_id': dimension_id, 'evaluacion_id': evaluacion_id,
                'dimension_nombre': '', 'total': 0, 'proyectos': [],
            })

        user     = request.user
        queryset = ProyectoCierreBrecha.objects.filter(
            calculo_nivel__in=calculos, activo=True
        ).select_related(
            'empresa', 'calculo_nivel', 'calculo_nivel__dimension',
            'dueno_proyecto', 'responsable_implementacion', 'validador_interno',
        ).prefetch_related('items').order_by('-fecha_creacion')

        if user.rol == 'administrador':
            queryset = queryset.filter(empresa=user.empresa) if user.empresa else queryset.none()
        elif user.rol != 'superadmin':
            queryset = queryset.filter(
                Q(dueno_proyecto=user) | Q(responsable_implementacion=user) | Q(validador_interno=user)
            ).distinct()

        return Response({
            'success':         True,
            'dimension_id':    dimension_id,
            'evaluacion_id':   evaluacion_id,
            'dimension_nombre': calculos.first().dimension.nombre,
            'total':           queryset.count(),
            'proyectos':       ProyectoCierreBrechaListSerializer(queryset, many=True).data,
        })