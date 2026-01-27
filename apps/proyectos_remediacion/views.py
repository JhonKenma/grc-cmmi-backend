# apps/proyectos_remediacion/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from .models import AprobacionGAP, ProyectoCierreBrecha, ItemProyecto
from .serializers import (
    AprobacionGAPListSerializer,
    ProyectoCierreBrechaListSerializer,
    ProyectoCierreBrechaDetailSerializer,
    ProyectoCierreBrechaCreateSerializer,
    ProyectoCierreBrechaUpdateSerializer,
    ItemProyectoListSerializer,
    ItemProyectoDetailSerializer,
    ItemProyectoCreateUpdateSerializer,
    SolicitarAprobacionSerializer,  # ⭐ AGREGAR
    ResponderAprobacionSerializer,  # ⭐ AGREGAR
)
from apps.core.permissions import EsSuperAdmin, EsAdminOSuperAdmin
from apps.core.mixins import ResponseMixin
from apps.respuestas.models import CalculoNivel
from apps.notificaciones.models import Notificacion  # ⭐ AGREGAR ESTE IMPORT
from .serializers import AprobacionGAPDetailSerializer
from datetime import date

class ProyectoCierreBrechaViewSet(ResponseMixin, viewsets.ModelViewSet):

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
    
    @action(detail=True, methods=['patch'], url_path='actualizar-item', permission_classes=[IsAuthenticated])
    def actualizar_item(self, request, pk=None):
            """
            Acción unificada para actualizar un ítem (estado, avance, presupuesto).
            PATCH /api/proyectos-remediacion/{id}/actualizar-item/
            """
            proyecto = self.get_object()
            user = request.user
            item_id = request.data.get('item_id')

            if not item_id:
                return self.error_response(
                    message='El campo item_id es requerido',
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # ═══ 1. OBTENER ÍTEM Y VALIDAR PERMISOS ═══
            try:
                item = proyecto.items.get(id=item_id, activo=True)
            except ItemProyecto.DoesNotExist:
                return self.error_response(
                    message='Ítem no encontrado en este proyecto',
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Solo Admins o el Responsable del ítem/Dueño del proyecto pueden editar
            es_responsable = item.responsable_ejecucion == user or proyecto.dueno_proyecto == user
            if user.rol not in ['superadmin', 'administrador'] and not es_responsable:
                return self.error_response(
                    message='No tienes permisos para actualizar este ítem',
                    status_code=status.HTTP_403_FORBIDDEN
                )

            # ═══ 2. VALIDAR BLOQUEO POR DEPENDENCIAS ═══
            nuevo_estado = request.data.get('estado')
            if nuevo_estado in ['en_proceso', 'completado']:
                if not item.puede_iniciar:
                    # Si existe 'item_dependencia', informamos cuál es
                    dep_info = f" #{item.item_dependencia.numero_item}" if item.item_dependencia else ""
                    return self.error_response(
                        message=f'El ítem está bloqueado. Debe completarse primero el ítem antecedente{dep_info}.',
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            # ═══ 3. PREPARAR DATOS Y SERIALIZADOR ═══
            # Clonamos los datos para poder manipularlos antes de validar
            datos_update = request.data.copy()

            # Lógica de negocio automática: si el avance es 100, forzar estado completado
            if float(datos_update.get('porcentaje_avance', 0)) >= 100:
                datos_update['estado'] = 'completado'
            
            # Si el estado es completado, asegurar que el avance sea 100
            if datos_update.get('estado') == 'completado':
                datos_update['porcentaje_avance'] = 100
                if not item.fecha_completado:
                    item.fecha_completado = timezone.now().date()

            serializer = ItemProyectoCreateUpdateSerializer(
                item, 
                data=datos_update, 
                partial=True,
                context={'request': request}
            )

            if not serializer.is_valid():
                return self.error_response(
                    message='Error en validación de datos',
                    errors=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # ═══ 4. GUARDAR Y GESTIONAR DESBLOQUEOS ═══
            try:
                with transaction.atomic():
                    item_actualizado = serializer.save()

                    # Si se completó, buscar ítems dependientes para desbloquearlos
                    if item_actualizado.estado == 'completado':
                        # Desbloquear hijos directos que ahora "pueden iniciar"
                        dependientes = item_actualizado.items_dependientes.filter(
                            estado='bloqueado', 
                            activo=True
                        )
                        for dep in dependientes:
                            if dep.puede_iniciar: # Propiedad del modelo que valida todas sus dependencias
                                dep.estado = 'pendiente'
                                dep.save(update_fields=['estado'])

                    # ═══ 5. RESPUESTA ═══
                    output_serializer = ItemProyectoDetailSerializer(item_actualizado)
                    return self.success_response(
                        data=output_serializer.data,
                        message=f'Ítem #{item_actualizado.numero_item} actualizado exitosamente'
                    )

            except Exception as e:
                return self.error_response(
                    message=f'Error al procesar la actualización: {str(e)}',
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
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

        # --- Lógica de Validador Automático ---
        # 1. Intentar obtenerlo del request
        validador_id = request.data.get('validador_interno_id')
        
        # 2. Si no viene, intentar obtener el creador de la asignación del GAP
        if not validador_id:
                asignacion = calculo_nivel.asignacion
                if asignacion:
                    # Tu modelo usa 'asignado_por', no 'creado_por'
                    # Usamos .id solo si el objeto existe para evitar nuevos errores
                    if asignacion.asignado_por:
                        validador_id = asignacion.asignado_por.id
                    else:
                        # Si nadie la asignó, usamos el administrador de la evaluación empresa
                        validador_id = asignacion.evaluacion_empresa.administrador.id
                else:
                    # Último recurso: el usuario que está operando ahora
                    validador_id = request.user.id

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
            
            'modo_presupuesto': request.data.get('modo_presupuesto', 'global'),
            'moneda': request.data.get('moneda', 'USD'),
            'presupuesto_global': request.data.get('presupuesto_global', 0),
            
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
            'validador_interno': validador_id,  # <--- Validador asignado aquí
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

    @action(detail=False, methods=['get'])
    def por_dimension_y_evaluacion(self, request):
        """
        Obtener proyectos de una dimensión específica en una evaluación específica
        GET /api/proyectos-remediacion/por_dimension_y_evaluacion/?dimension_id=X&evaluacion_id=Y
        """
        dimension_id = request.query_params.get('dimension_id')
        evaluacion_id = request.query_params.get('evaluacion_id')
        
        if not dimension_id:
            return self.error_response(
                message='Se requiere dimension_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if not evaluacion_id:
            return self.error_response(
                message='Se requiere evaluacion_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ 1. OBTENER CALCULOS DE NIVEL DE ESA DIMENSIÓN EN ESA EVALUACIÓN ═══
        calculos = CalculoNivel.objects.filter(
            dimension_id=dimension_id,
            evaluacion_id=evaluacion_id,
            activo=True
        )
        
        if not calculos.exists():
            return Response({
                'success': True,
                'dimension_id': dimension_id,
                'evaluacion_id': evaluacion_id,
                'dimension_nombre': '',
                'total': 0,
                'proyectos': []
            })
        
        # ═══ 2. OBTENER PROYECTOS DE ESOS CÁLCULOS ═══
        proyectos_queryset = ProyectoCierreBrecha.objects.filter(
            calculo_nivel__in=calculos,
            activo=True
        ).select_related(
            'empresa',
            'calculo_nivel',
            'calculo_nivel__dimension',
            'dueno_proyecto',
            'responsable_implementacion',
            'validador_interno'
        ).prefetch_related(
            'items'
        ).order_by('-fecha_creacion')
        
        # ═══ 3. FILTRAR POR PERMISOS ═══
        user = request.user
        
        if user.rol == 'administrador':
            if user.empresa:
                proyectos_queryset = proyectos_queryset.filter(empresa=user.empresa)
            else:
                proyectos_queryset = proyectos_queryset.none()
        elif user.rol not in ['superadmin']:
            # Usuario solo ve donde está asignado
            proyectos_queryset = proyectos_queryset.filter(
                Q(dueno_proyecto=user) |
                Q(responsable_implementacion=user) |
                Q(validador_interno=user)
            ).distinct()
        
        # ═══ 4. SERIALIZAR ═══
        serializer = ProyectoCierreBrechaListSerializer(proyectos_queryset, many=True)
        
        # ═══ 5. RESPUESTA ═══
        dimension_nombre = calculos.first().dimension.nombre if calculos.exists() else ''
        
        return Response({
            'success': True,
            'dimension_id': dimension_id,
            'evaluacion_id': evaluacion_id,
            'dimension_nombre': dimension_nombre,
            'total': proyectos_queryset.count(),
            'proyectos': serializer.data
        })

    
    # Nuevos ENDPOINTS 26/01/2026
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def solicitar_aprobacion(self, request, pk=None):
        """
        Solicita la aprobación para cerrar el GAP del proyecto.
        """
        proyecto = self.get_object()
        user = request.user
        
        # ═══ VALIDACIONES ═══
        
        # 1. MODIFICADO: Incluir 'pendiente' y cualquier estado inicial lógico
        estados_validos = ['en_ejecucion', 'planificado', 'pendiente', 'en_progreso']
        if proyecto.estado not in estados_validos:
            return self.error_response(
                message=f'El proyecto está en estado "{proyecto.estado}". No puede solicitar aprobación en este estado.',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # 2. Si es modo por_items, validar que todos estén completados
        if proyecto.modo_presupuesto == 'por_items':
            # Verificar si existen ítems primero
            if proyecto.total_items == 0:
                return self.error_response(
                    message='No puedes solicitar aprobación de un proyecto sin ítems de planificación.',
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            items_pendientes = proyecto.items.filter(
                activo=True
            ).exclude(estado='completado').count()
            
            if items_pendientes > 0:
                return self.error_response(
                    message=f'Aún hay {items_pendientes} ítem(s) pendiente(s) de completar',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # 3. Verificar que no haya una aprobación pendiente (se mantiene igual)
        aprobacion_pendiente = AprobacionGAP.objects.filter(
            proyecto=proyecto,
            estado='pendiente',
            activo=True
        ).first()
        
        if aprobacion_pendiente:
            return self.error_response(
                message='Ya existe una solicitud de aprobación pendiente para este proyecto',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # 4. Determinar el validador (CORREGIDO campo asignado_por)
        validador = proyecto.validador_interno
        
        if not validador and proyecto.calculo_nivel:
            try:
                asignacion = proyecto.calculo_nivel.asignacion
                if asignacion:
                    # ⭐ CAMBIO AQUÍ: 'asignado_por' en lugar de 'creado_por'
                    validador = asignacion.asignado_por
            except Exception as e:
                print(f"Error al buscar validador: {e}")
        
        if not validador:
            return self.error_response(
                message='No se pudo determinar el validador para este proyecto. Por favor, asígnale un validador interno manualmente.',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ CREAR SOLICITUD DE APROBACIÓN ═══
        
        serializer = SolicitarAprobacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                # Crear aprobación
                aprobacion = AprobacionGAP.objects.create(
                    proyecto=proyecto,
                    solicitado_por=user,
                    validador=validador,
                    comentarios_solicitud=serializer.validated_data.get('comentarios', ''),
                    documentos_adjuntos=serializer.validated_data.get('documentos_adjuntos', []),
                    items_completados=proyecto.items_completados if proyecto.modo_presupuesto == 'por_items' else 0,
                    items_totales=proyecto.total_items if proyecto.modo_presupuesto == 'por_items' else 0,
                    presupuesto_ejecutado=proyecto.presupuesto_total_ejecutado,
                    presupuesto_planificado=proyecto.presupuesto_total_planificado,
                    gap_original=proyecto.gap_original,
                )
                
                # Cambiar estado del proyecto
                proyecto.estado = 'en_validacion'
                proyecto.save(update_fields=['estado'])
                
        except Exception as e:
            return self.error_response(
                message=f'Error al crear la solicitud: {str(e)}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # ═══ RESPUESTA ═══
        # Asegúrate de que AprobacionGAPDetailSerializer esté importado arriba
        output_serializer = AprobacionGAPDetailSerializer(aprobacion)
        
        return self.success_response(
            data=output_serializer.data,
            message=f'Solicitud de aprobación enviada a {validador.nombre_completo}',
            status_code=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def aprobar_cierre_gap(self, request, pk=None):
        """
        Aprueba el cierre del GAP de un proyecto.
        POST /api/proyectos-remediacion/{id}/aprobar_cierre_gap/
        
        Body:
        {
            "observaciones": "Excelente trabajo, todo documentado correctamente"
        }
        """
        proyecto = self.get_object()
        user = request.user
        
        # ═══ VALIDACIONES ═══
        
        # 1. Verificar que exista una aprobación pendiente
        aprobacion = AprobacionGAP.objects.filter(
            proyecto=proyecto,
            estado='pendiente',
            activo=True
        ).first()
        
        if not aprobacion:
            return self.error_response(
                message='No hay una solicitud de aprobación pendiente para este proyecto',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 2. Verificar que el usuario sea el validador
        if aprobacion.validador != user:
            return self.error_response(
                message='No tienes permisos para aprobar esta solicitud',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # ═══ APROBAR ═══
        
        serializer = ResponderAprobacionSerializer(data={
            'aprobado': True,
            'observaciones': request.data.get('observaciones', '')
        })
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                # Actualizar aprobación
                aprobacion.estado = 'aprobado'
                aprobacion.fecha_revision = timezone.now()
                aprobacion.observaciones = serializer.validated_data.get('observaciones', '')
                aprobacion.save()
                
                # Cerrar proyecto
                proyecto.estado = 'cerrado'
                proyecto.fecha_fin_real = date.today()
                proyecto.save(update_fields=['estado', 'fecha_fin_real'])
                
                # ⭐ CERRAR GAP (Actualizar CalculoNivel)
                if proyecto.calculo_nivel:
                    # Aquí puedes agregar lógica adicional para marcar el GAP como cerrado
                    # Por ejemplo, agregar un campo `gap_cerrado = True` en CalculoNivel
                    pass
                
                # Crear notificación al solicitante
                Notificacion.objects.create(
                    usuario=aprobacion.solicitado_por,
                    tipo='aprobacion',  # Asegúrate de que este valor esté en Notificacion.TIPOS
                    titulo=f'✅ GAP aprobado - {proyecto.codigo_proyecto}',
                    mensaje=(
                        f'Tu solicitud de cierre de GAP para el proyecto '
                        f'{proyecto.codigo_proyecto} ha sido APROBADA.'
                    ),
                    url_accion=f'/proyectos-remediacion/{proyecto.id}', # ANTES ERA 'url'
                    datos_adicionales={                                # ANTES ERA 'metadata'
                        'proyecto_id': str(proyecto.id),
                        'aprobacion_id': str(aprobacion.id),
                    }
                )
        
        # CAMBIA ESTO:
        except Exception as e:
            # Agrega esta línea para ver el error real en la terminal negra
            print(f"DEBUG ERROR: {str(e)}") 
            import traceback
            traceback.print_exc() # Esto imprimirá el error completo con línea y todo
            
            return self.error_response(
                message=f'Error al aprobar: {str(e)}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # ═══ RESPUESTA ═══
        output_serializer = AprobacionGAPDetailSerializer(aprobacion)
        
        return self.success_response(
            data=output_serializer.data,
            message='GAP aprobado exitosamente'
        )


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def rechazar_cierre_gap(self, request, pk=None):
        """
        Rechaza el cierre del GAP de un proyecto.
        POST /api/proyectos-remediacion/{id}/rechazar_cierre_gap/
        
        Body:
        {
            "observaciones": "Falta evidencia de capacitación al personal"
        }
        """
        proyecto = self.get_object()
        user = request.user
        
        # ═══ VALIDACIONES ═══
        
        # 1. Verificar que exista una aprobación pendiente
        aprobacion = AprobacionGAP.objects.filter(
            proyecto=proyecto,
            estado='pendiente',
            activo=True
        ).first()
        
        if not aprobacion:
            return self.error_response(
                message='No hay una solicitud de aprobación pendiente para este proyecto',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 2. Verificar que el usuario sea el validador
        if aprobacion.validador != user:
            return self.error_response(
                message='No tienes permisos para rechazar esta solicitud',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # ═══ RECHAZAR ═══
        
        serializer = ResponderAprobacionSerializer(data={
            'aprobado': False,
            'observaciones': request.data.get('observaciones', '')
        })
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                # Actualizar aprobación
                aprobacion.estado = 'rechazado'
                aprobacion.fecha_revision = timezone.now()
                aprobacion.observaciones = serializer.validated_data['observaciones']
                aprobacion.save()
                
                # Devolver proyecto a ejecución
                proyecto.estado = 'en_ejecucion'
                proyecto.save(update_fields=['estado'])
                
                # Crear notificación al solicitante
                Notificacion.objects.create(
                    usuario=aprobacion.solicitado_por,
                    tipo='aprobacion',
                    titulo=f'✅ GAP aprobado - {proyecto.codigo_proyecto}',
                    mensaje=(
                        f'Tu solicitud de cierre de GAP para el proyecto '
                        f'{proyecto.codigo_proyecto} ha sido APROBADA.\n\n'
                        f'Validador: {user.nombre_completo}\n'
                        f'Observaciones: {aprobacion.observaciones or "Sin observaciones"}'
                    ),
                    url_accion=f'/proyectos-remediacion/{proyecto.id}',
                    datos_adicionales={
                        'proyecto_id': str(proyecto.id),
                        'aprobacion_id': str(aprobacion.id),
                    }
                )
                        
        except Exception as e:
            return self.error_response(
                message=f'Error al rechazar: {str(e)}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # ═══ RESPUESTA ═══
        output_serializer = AprobacionGAPDetailSerializer(aprobacion)
        
        return self.success_response(
            data=output_serializer.data,
            message='Solicitud rechazada. Se ha notificado al responsable.'
        )


    @action(detail=False, methods=['get'])
    def aprobaciones_pendientes(self, request):
        """
        Obtiene las aprobaciones pendientes del usuario actual.
        GET /api/proyectos-remediacion/aprobaciones_pendientes/
        """
        user = request.user
        
        aprobaciones = AprobacionGAP.objects.filter(
            validador=user,
            estado='pendiente',
            activo=True
        ).select_related(
            'proyecto',
            'solicitado_por'
        ).order_by('-fecha_solicitud')
        
        serializer = AprobacionGAPListSerializer(aprobaciones, many=True)
        
        return Response({
            'count': aprobaciones.count(),
            'aprobaciones': serializer.data
        })


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def completar_item(self, request, pk=None):
        """
        Marca un ítem como completado.
        POST /api/proyectos-remediacion/{id}/completar_item/
        
        Body:
        {
            "item_id": "uuid-del-item",
            "observaciones": "Trabajo completado satisfactoriamente"  // opcional
        }
        """
        proyecto = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return self.error_response(
                message='El campo item_id es requerido',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            item = ItemProyecto.objects.get(id=item_id, proyecto=proyecto, activo=True)
        except ItemProyecto.DoesNotExist:
            return self.error_response(
                message='Ítem no encontrado',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # ═══ MARCAR COMO COMPLETADO ═══
        item.estado = 'completado'
        item.porcentaje_avance = 100
        item.fecha_completado = date.today()
        
        if 'observaciones' in request.data:
            item.observaciones = request.data['observaciones']
            item.save(update_fields=['estado', 'porcentaje_avance', 'fecha_completado', 'observaciones'])
        else:
            item.save(update_fields=['estado', 'porcentaje_avance', 'fecha_completado'])
        
        # ═══ RESPUESTA ═══
        serializer = ItemProyectoListSerializer(item)
        
        return self.success_response(
            data=serializer.data,
            message=f'Ítem #{item.numero_item} marcado como completado'
        )

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
    
