# apps/proyectos_remediacion/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta, date

from .models import ProyectoCierreBrecha, ItemProyecto
from .serializers import (
    ProyectoCierreBrechaListSerializer,
    ProyectoCierreBrechaDetailSerializer,
    ProyectoCierreBrechaCreateSerializer,
    ProyectoCierreBrechaUpdateSerializer,
    ItemProyectoListSerializer,
    ItemProyectoDetailSerializer,
    ItemProyectoCreateUpdateSerializer,
)
from apps.core.permissions import EsSuperAdmin, EsAdminOSuperAdmin
from apps.core.mixins import ResponseMixin
from apps.respuestas.models import CalculoNivel


class ProyectoCierreBrechaViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de Proyectos de Cierre de Brecha
    
    ENDPOINTS PRINCIPALES:
    - GET    /api/proyectos-remediacion/                          → Listar proyectos
    - POST   /api/proyectos-remediacion/                          → Crear proyecto
    - GET    /api/proyectos-remediacion/{id}/                     → Detalle de proyecto
    - PATCH  /api/proyectos-remediacion/{id}/                     → Actualizar proyecto
    - DELETE /api/proyectos-remediacion/{id}/                     → Desactivar proyecto
    
    ENDPOINTS DE ÍTEMS:
    - GET    /api/proyectos-remediacion/{id}/items/               → Listar ítems del proyecto
    - POST   /api/proyectos-remediacion/{id}/agregar_item/        → Agregar ítem
    - PATCH  /api/proyectos-remediacion/{id}/actualizar_item/     → Actualizar ítem
    - DELETE /api/proyectos-remediacion/{id}/eliminar_item/       → Eliminar ítem
    - POST   /api/proyectos-remediacion/{id}/reordenar_items/     → Reordenar ítems
    
    ENDPOINTS ESPECIALES:
    - POST   /api/proyectos-remediacion/crear_desde_gap/          → Crear proyecto desde GAP
    - GET    /api/proyectos-remediacion/mis_proyectos/            → Mis proyectos asignados
    - GET    /api/proyectos-remediacion/estadisticas/             → Estadísticas generales
    - GET    /api/proyectos-remediacion/vencidos/                 → Proyectos vencidos
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
        """
        user = self.request.user
        
        queryset = ProyectoCierreBrecha.objects.select_related(
            'empresa',
            'calculo_nivel',
            'calculo_nivel__dimension',
            'dueno_proyecto',
            'responsable_implementacion',
            'validador_interno',
            'creado_por'
        ).prefetch_related(
            'preguntas_abordadas',
            'items',  # ⭐ Nuevo: prefetch de ítems
            'items__proveedor',
            'items__responsable_ejecucion',
        ).filter(activo=True)
        
        # ═══ FILTRO POR ROL ═══
        if user.rol == 'superadmin':
            pass
        elif user.rol == 'administrador':
            if user.empresa:
                queryset = queryset.filter(empresa=user.empresa)
            else:
                queryset = queryset.none()
        else:
            # Usuario solo ve donde está asignado
            queryset = queryset.filter(
                Q(dueno_proyecto=user) |
                Q(responsable_implementacion=user) |
                Q(validador_interno=user) |
                Q(items__responsable_ejecucion=user)  # ⭐ Nuevo: también si es responsable de algún ítem
            ).distinct()
        
        # ═══ FILTROS ADICIONALES ═══
        calculo_nivel_id = self.request.query_params.get('calculo_nivel')
        if calculo_nivel_id:
            queryset = queryset.filter(calculo_nivel_id=calculo_nivel_id)
        
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        prioridad = self.request.query_params.get('prioridad')
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
        
        categoria = self.request.query_params.get('categoria')
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        # ⭐ Nuevo: Filtro por modo de presupuesto
        modo_presupuesto = self.request.query_params.get('modo_presupuesto')
        if modo_presupuesto:
            queryset = queryset.filter(modo_presupuesto=modo_presupuesto)
        
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id and user.rol == 'superadmin':
            queryset = queryset.filter(empresa_id=empresa_id)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(codigo_proyecto__icontains=search) |
                Q(nombre_proyecto__icontains=search) |
                Q(descripcion__icontains=search)
            )
        
        ordering = self.request.query_params.get('ordering', '-fecha_creacion')
        queryset = queryset.order_by(ordering)
        
        return queryset
    
    def get_permissions(self):
        """Permisos específicos por acción"""
        if self.action in ['create', 'crear_desde_gap']:
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        
        if self.action in ['update', 'partial_update', 'destroy', 'agregar_item', 'actualizar_item', 'eliminar_item']:
            return [IsAuthenticated(), EsAdminOSuperAdmin()]
        
        return [IsAuthenticated()]
    
    # ═══════════════════════════════════════════════════════════════
    # MÉTODOS CRUD BÁSICOS
    # ═══════════════════════════════════════════════════════════════
    
    def create(self, request, *args, **kwargs):
        """Crear nuevo proyecto"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        proyecto = serializer.save()
        
        output_serializer = ProyectoCierreBrechaDetailSerializer(proyecto)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Proyecto {proyecto.codigo_proyecto} creado exitosamente',
            status_code=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Actualizar proyecto"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        proyecto = serializer.save()
        
        output_serializer = ProyectoCierreBrechaDetailSerializer(proyecto)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Proyecto {proyecto.codigo_proyecto} actualizado exitosamente'
        )
    
    def destroy(self, request, *args, **kwargs):
        """Desactivar proyecto (soft delete)"""
        instance = self.get_object()
        
        if instance.estado in ['cerrado']:
            return self.error_response(
                message='No se puede eliminar un proyecto cerrado',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ⭐ Nuevo: También desactivar ítems si es modo por_items
        if instance.modo_presupuesto == 'por_items':
            instance.items.update(activo=False)
        
        instance.activo = False
        instance.estado = 'cancelado'
        instance.save()
        
        return self.success_response(
            message=f'Proyecto {instance.codigo_proyecto} desactivado exitosamente',
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    # ═══════════════════════════════════════════════════════════════
    # GESTIÓN DE ÍTEMS (NUEVO) ⭐
    # ═══════════════════════════════════════════════════════════════
    
    @action(detail=True, methods=['get'], url_path='items')
    def listar_items(self, request, pk=None):
        """
        Listar ítems de un proyecto
        GET /api/proyectos-remediacion/{id}/items/
        
        Query params:
        - estado: pendiente, en_proceso, completado, bloqueado
        - requiere_proveedor: true/false
        """
        proyecto = self.get_object()
        
        if proyecto.modo_presupuesto != 'por_items':
            return self.error_response(
                message='Este proyecto no está en modo "por_items"',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        items = proyecto.items.filter(activo=True).select_related(
            'proveedor',
            'responsable_ejecucion',
            'item_dependencia'
        ).order_by('numero_item')
        
        # Filtros opcionales
        estado = request.query_params.get('estado')
        if estado:
            items = items.filter(estado=estado)
        
        requiere_proveedor = request.query_params.get('requiere_proveedor')
        if requiere_proveedor is not None:
            items = items.filter(requiere_proveedor=requiere_proveedor.lower() == 'true')
        
        serializer = ItemProyectoListSerializer(items, many=True)
        
        return Response({
            'success': True,
            'data': {
                'proyecto_id': str(proyecto.id),
                'codigo_proyecto': proyecto.codigo_proyecto,
                'total_items': items.count(),
                'items': serializer.data,
                # Resumen
                'resumen': {
                    'total_presupuesto_planificado': sum(item.presupuesto_planificado for item in items),
                    'total_presupuesto_ejecutado': sum(item.presupuesto_ejecutado for item in items),
                    'items_completados': items.filter(estado='completado').count(),
                    'items_bloqueados': items.filter(estado='bloqueado').count(),
                }
            }
        })
    
    @action(detail=True, methods=['post'], url_path='agregar-item', permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def agregar_item(self, request, pk=None):
        """
        Agregar un ítem al proyecto
        POST /api/proyectos-remediacion/{id}/agregar-item/
        
        Body:
        {
            "nombre_item": "Adquisición de Licencia Antivirus",
            "descripcion": "...",
            "requiere_proveedor": true,
            "proveedor_id": "uuid",
            "nombre_responsable_proveedor": "Responsable de Compras",
            "responsable_ejecucion_id": "uuid",
            "presupuesto_planificado": 5000,
            "fecha_inicio": "2025-01-19",
            "duracion_dias": 3,
            "tiene_dependencia": false,
            "item_dependencia_id": null
        }
        """
        proyecto = self.get_object()
        
        if proyecto.modo_presupuesto != 'por_items':
            return self.error_response(
                message='Este proyecto no está en modo "por_items"',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ 1. GENERAR NÚMERO DE ÍTEM AUTOMÁTICAMENTE ═══
        ultimo_item = proyecto.items.filter(activo=True).order_by('-numero_item').first()
        numero_item = (ultimo_item.numero_item + 1) if ultimo_item else 1
        
        # ═══ 2. PREPARAR DATOS ═══
        data = request.data.copy()
        data['proyecto'] = proyecto.id
        data['numero_item'] = numero_item
        
        # Convertir IDs de foreign keys
        if 'proveedor_id' in data:
            data['proveedor'] = data.pop('proveedor_id')
        if 'responsable_ejecucion_id' in data:
            data['responsable_ejecucion'] = data.pop('responsable_ejecucion_id')
        if 'item_dependencia_id' in data:
            data['item_dependencia'] = data.pop('item_dependencia_id')
        
        # ═══ 3. VALIDAR Y CREAR ═══
        serializer = ItemProyectoCreateUpdateSerializer(data=data)
        
        if not serializer.is_valid():
            return self.error_response(
                message='Error en validación de datos',
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        item = serializer.save()
        
        # ═══ 4. VERIFICAR SI ESTÁ BLOQUEADO POR DEPENDENCIA ═══
        if item.tiene_dependencia and not item.puede_iniciar:
            item.estado = 'bloqueado'
            item.save()
        
        # ═══ 5. RESPUESTA ═══
        output_serializer = ItemProyectoDetailSerializer(item)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Ítem #{numero_item} agregado exitosamente',
            status_code=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['patch'], url_path='actualizar-item', permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def actualizar_item(self, request, pk=None):
        """
        Actualizar un ítem existente
        PATCH /api/proyectos-remediacion/{id}/actualizar-item/
        
        Body:
        {
            "item_id": "uuid",
            "porcentaje_avance": 50,
            "presupuesto_ejecutado": 2500,
            "estado": "en_proceso"
        }
        """
        proyecto = self.get_object()
        
        item_id = request.data.get('item_id')
        if not item_id:
            return self.error_response(
                message='Se requiere item_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            item = proyecto.items.get(id=item_id, activo=True)
        except ItemProyecto.DoesNotExist:
            return self.error_response(
                message='Ítem no encontrado',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # ═══ VALIDAR SI PUEDE ACTUALIZAR ESTADO ═══
        nuevo_estado = request.data.get('estado')
        if nuevo_estado == 'en_proceso' or nuevo_estado == 'completado':
            if not item.puede_iniciar:
                return self.error_response(
                    message=f'El ítem está bloqueado. Debe completarse primero el ítem #{item.item_dependencia.numero_item}',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # ═══ ACTUALIZAR ═══
        serializer = ItemProyectoCreateUpdateSerializer(
            item,
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return self.error_response(
                message='Error en validación de datos',
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        item = serializer.save()
        
        # ═══ SI SE COMPLETÓ, DESBLOQUEAR DEPENDIENTES ═══
        if item.estado == 'completado':
            dependientes = item.items_dependientes.filter(estado='bloqueado', activo=True)
            for dep in dependientes:
                if dep.puede_iniciar:
                    dep.estado = 'pendiente'
                    dep.save()
        
        # ═══ RESPUESTA ═══
        output_serializer = ItemProyectoDetailSerializer(item)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Ítem #{item.numero_item} actualizado exitosamente'
        )
    
    @action(detail=True, methods=['delete'], url_path='eliminar-item', permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def eliminar_item(self, request, pk=None):
        """
        Eliminar un ítem
        DELETE /api/proyectos-remediacion/{id}/eliminar-item/?item_id=xxx
        """
        proyecto = self.get_object()
        
        item_id = request.query_params.get('item_id')
        if not item_id:
            return self.error_response(
                message='Se requiere item_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            item = proyecto.items.get(id=item_id, activo=True)
        except ItemProyecto.DoesNotExist:
            return self.error_response(
                message='Ítem no encontrado',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # ═══ VALIDAR QUE NO HAYA DEPENDIENTES ═══
        if item.items_dependientes.filter(activo=True).exists():
            return self.error_response(
                message='No se puede eliminar. Otros ítems dependen de este',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ ELIMINAR (SOFT DELETE) ═══
        item.activo = False
        item.save()
        
        return self.success_response(
            message=f'Ítem #{item.numero_item} eliminado exitosamente',
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=True, methods=['post'], url_path='reordenar-items', permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def reordenar_items(self, request, pk=None):
        """
        Reordenar ítems del proyecto
        POST /api/proyectos-remediacion/{id}/reordenar-items/
        
        Body:
        {
            "orden": ["uuid1", "uuid2", "uuid3"]
        }
        """
        proyecto = self.get_object()
        
        orden = request.data.get('orden', [])
        if not orden:
            return self.error_response(
                message='Se requiere "orden" con lista de IDs',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ ACTUALIZAR NÚMEROS ═══
        with transaction.atomic():
            for idx, item_id in enumerate(orden, start=1):
                try:
                    item = proyecto.items.get(id=item_id, activo=True)
                    item.numero_item = idx
                    item.save()
                except ItemProyecto.DoesNotExist:
                    return self.error_response(
                        message=f'Ítem {item_id} no encontrado',
                        status_code=status.HTTP_404_NOT_FOUND
                    )
        
        return self.success_response(
            message='Ítems reordenados exitosamente'
        )
    
    # ═══════════════════════════════════════════════════════════════
    # CREAR PROYECTO DESDE GAP (ACTUALIZADO)
    # ═══════════════════════════════════════════════════════════════
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def crear_desde_gap(self, request):
        """
        Crear proyecto automáticamente desde un GAP
        POST /api/proyectos-remediacion/crear_desde_gap/
        
        Body:
        {
            "calculo_nivel_id": "uuid",
            "modo_presupuesto": "por_items",  # ⭐ NUEVO
            "fecha_inicio": "2025-01-19",
            "fecha_fin_estimada": "2025-04-19",
            "dueno_proyecto_id": "uuid",
            "responsable_implementacion_id": "uuid",
            "moneda": "USD"
        }
        """
        
        # ═══ 1. VALIDAR DATOS ═══
        calculo_nivel_id = request.data.get('calculo_nivel_id')
        if not calculo_nivel_id:
            return self.error_response(
                message='Se requiere calculo_nivel_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ 2. OBTENER GAP ═══
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
        
        # ═══ 4. VERIFICAR PROYECTOS EXISTENTES ═══
        proyectos_previos_count = ProyectoCierreBrecha.objects.filter(
            calculo_nivel=calculo_nivel,
            activo=True
        ).count()
        
        # ═══ 5. PRE-LLENAR DATOS ═══
        nombre_base = request.data.get('nombre_proyecto') or f'Remediación: {calculo_nivel.dimension.nombre}'
        if proyectos_previos_count > 0:
            nombre_base = f"{nombre_base} (Fase {proyectos_previos_count + 1})"
        
        datos_proyecto = {
            'calculo_nivel': calculo_nivel.id,
            'nombre_proyecto': nombre_base,
            'descripcion': request.data.get('descripcion') or 
                          f'Proyecto para cerrar brecha en {calculo_nivel.dimension.nombre}. '
                          f'GAP: {calculo_nivel.gap} ({calculo_nivel.get_clasificacion_gap_display()})',
            
            'fecha_inicio': request.data.get('fecha_inicio'),
            'fecha_fin_estimada': request.data.get('fecha_fin_estimada'),
            
            'prioridad': self._mapear_prioridad_gap(calculo_nivel.clasificacion_gap),
            'categoria': request.data.get('categoria', 'tecnico'),
            
            # ⭐ NUEVO: Modo de presupuesto
            'modo_presupuesto': request.data.get('modo_presupuesto', 'global'),
            'moneda': request.data.get('moneda', 'USD'),
            'presupuesto_global': request.data.get('presupuesto_global', 0),
            
            # Planificación
            'alcance_proyecto': request.data.get('alcance_proyecto') or 
                               f'Cerrar brecha en {calculo_nivel.dimension.nombre}',
            
            'objetivos_especificos': request.data.get('objetivos_especificos') or 
                                    f'1. Reducir GAP de {calculo_nivel.gap} a 0\n'
                                    f'2. Alcanzar nivel {calculo_nivel.nivel_deseado}',
            
            'criterios_aceptacion': request.data.get('criterios_aceptacion') or 
                                   f'✓ Nivel actual >= {calculo_nivel.nivel_deseado}\n'
                                   f'✓ GAP <= 0.5',
            
            'riesgos_proyecto': request.data.get('riesgos_proyecto', ''),
            
            # Responsables
            'dueno_proyecto': request.data.get('dueno_proyecto_id'),
            'responsable_implementacion': request.data.get('responsable_implementacion_id'),
            'validador_interno': request.data.get('validador_interno_id'),
        }
        
        # ═══ 6. CREAR PROYECTO ═══
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
        
        # ═══ 7. VINCULAR PREGUNTAS NO CONFORMES ═══
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
        """Mapear clasificación de GAP a prioridad"""
        mapeo = {
            'critico': 'critica',
            'alto': 'alta',
            'medio': 'media',
            'bajo': 'baja',
            'cumplido': 'baja',
            'superado': 'baja',
        }
        return mapeo.get(clasificacion_gap, 'media')
    
    # ═══════════════════════════════════════════════════════════════
    # ENDPOINTS DE CONSULTA
    # ═══════════════════════════════════════════════════════════════
    
    @action(detail=False, methods=['get'])
    def mis_proyectos(self, request):
        """
        Obtener proyectos donde estoy asignado
        GET /api/proyectos-remediacion/mis_proyectos/
        """
        user = request.user
        
        queryset = ProyectoCierreBrecha.objects.filter(activo=True)
        
        # Proyectos donde estoy asignado
        queryset = queryset.filter(
            Q(dueno_proyecto=user) |
            Q(responsable_implementacion=user) |
            Q(validador_interno=user) |
            Q(items__responsable_ejecucion=user)  # ⭐ También como responsable de ítems
        ).distinct()
        
        estado = request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        queryset = queryset.order_by('-fecha_creacion')
        
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
        
        if user.rol == 'superadmin':
            queryset = ProyectoCierreBrecha.objects.filter(activo=True)
        elif user.rol == 'administrador' and user.empresa:
            queryset = ProyectoCierreBrecha.objects.filter(empresa=user.empresa, activo=True)
        else:
            queryset = ProyectoCierreBrecha.objects.filter(
                Q(dueno_proyecto=user) |
                Q(responsable_implementacion=user)
            ).distinct().filter(activo=True)
        
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
        
        # ⭐ NUEVO: Por modo de presupuesto
        por_modo_presupuesto = {
            'global': queryset.filter(modo_presupuesto='global').count(),
            'por_items': queryset.filter(modo_presupuesto='por_items').count(),
        }
        
        # Vencidos
        vencidos = queryset.filter(
            fecha_fin_estimada__lt=timezone.now().date(),
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).count()
        
        # Próximos a vencer
        fecha_limite = timezone.now().date() + timedelta(days=7)
        proximos_vencer = queryset.filter(
            fecha_fin_estimada__lte=fecha_limite,
            fecha_fin_estimada__gte=timezone.now().date(),
            estado__in=['planificado', 'en_ejecucion', 'en_validacion']
        ).count()
        
        # ⭐ NUEVO: Presupuesto inteligente (global + ítems)
        presupuesto_total_planificado = 0
        presupuesto_total_ejecutado = 0
        
        for proyecto in queryset:
            presupuesto_total_planificado += float(proyecto.presupuesto_total_planificado)
            presupuesto_total_ejecutado += float(proyecto.presupuesto_total_ejecutado)
        
        return Response({
            'total_proyectos': total_proyectos,
            'por_estado': por_estado,
            'por_prioridad': por_prioridad,
            'por_modo_presupuesto': por_modo_presupuesto,
            'alertas': {
                'vencidos': vencidos,
                'proximos_a_vencer': proximos_vencer,
            },
            'presupuesto': {
                'total_planificado': round(presupuesto_total_planificado, 2),
                'total_ejecutado': round(presupuesto_total_ejecutado, 2),
                'disponible': round(presupuesto_total_planificado - presupuesto_total_ejecutado, 2),
                'porcentaje_gastado': round((presupuesto_total_ejecutado / presupuesto_total_planificado * 100) if presupuesto_total_planificado > 0 else 0, 2)
            }
        })
    
    @action(detail=False, methods=['get'])
    def vencidos(self, request):
        """Proyectos vencidos"""
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
        """Proyectos próximos a vencer"""
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


# ═══════════════════════════════════════════════════════════════
# VIEWSET PARA ITEMPROYECTO (ALTERNATIVA) ⭐
# ═══════════════════════════════════════════════════════════════

class ItemProyectoViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet alternativo para gestionar ítems directamente
    
    ENDPOINTS:
    - GET    /api/items-proyecto/                     → Listar todos los ítems
    - GET    /api/items-proyecto/{id}/                → Detalle de ítem
    - POST   /api/items-proyecto/                     → Crear ítem
    - PATCH  /api/items-proyecto/{id}/                → Actualizar ítem
    - DELETE /api/items-proyecto/{id}/                → Eliminar ítem
    """
    
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ItemProyectoListSerializer
        elif self.action == 'retrieve':
            return ItemProyectoDetailSerializer
        else:
            return ItemProyectoCreateUpdateSerializer
    
    def get_queryset(self):
        """Filtrar ítems según permisos"""
        user = self.request.user
        
        queryset = ItemProyecto.objects.select_related(
            'proyecto',
            'proveedor',
            'responsable_ejecucion',
            'item_dependencia'
        ).filter(activo=True)
        
        # Filtrar según rol
        if user.rol == 'superadmin':
            pass
        elif user.rol == 'administrador':
            if user.empresa:
                queryset = queryset.filter(proyecto__empresa=user.empresa)
            else:
                queryset = queryset.none()
        else:
            queryset = queryset.filter(
                Q(proyecto__dueno_proyecto=user) |
                Q(responsable_ejecucion=user)
            )
        
        # Filtros adicionales
        proyecto_id = self.request.query_params.get('proyecto')
        if proyecto_id:
            queryset = queryset.filter(proyecto_id=proyecto_id)
        
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        return queryset.order_by('proyecto', 'numero_item')