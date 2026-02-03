# apps/proyectos_remediacion/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta

from .models import ProyectoCierreBrecha, ItemProyecto
from apps.respuestas.models import CalculoNivel
from apps.usuarios.models import Usuario
from apps.encuestas.models import Pregunta
from apps.proveedores.models import Proveedor
from apps.empresas.serializers import EmpresaSerializer
from apps.usuarios.serializers import UsuarioListSerializer


# ═══════════════════════════════════════════════════════════════
# SERIALIZER PARA ITEM PROYECTO (ACTUALIZADO CON NUEVOS CAMPOS)
# ═══════════════════════════════════════════════════════════════

class ItemProyectoListSerializer(serializers.ModelSerializer):
    """
    Serializer para listar ítems (actualizado con fechas laborables y elasticidad)
    """
    
    proveedor_nombre = serializers.CharField(
        source='proveedor.razon_social',
        read_only=True,
        allow_null=True
    )
    
    responsable_nombre = serializers.CharField(
        source='responsable_ejecucion.nombre_completo',
        read_only=True,
        allow_null=True
    )
    
    item_dependencia_numero = serializers.IntegerField(
        source='item_dependencia.numero_item',
        read_only=True,
        allow_null=True
    )
    
    # ⭐ NUEVOS CAMPOS CALCULADOS
    fecha_fin_estimada = serializers.ReadOnlyField()
    dias_laborables_restantes = serializers.ReadOnlyField()
    esta_retrasado = serializers.ReadOnlyField()
    
    # ⭐ ELASTICIDAD DE PRESUPUESTO
    presupuesto_elasticidad = serializers.ReadOnlyField()
    presupuesto_limite = serializers.ReadOnlyField()
    porcentaje_presupuesto_usado = serializers.ReadOnlyField()
    esta_en_elasticidad = serializers.ReadOnlyField()
    excede_presupuesto_limite = serializers.ReadOnlyField()
    monto_excedido = serializers.ReadOnlyField()
    estado_presupuesto = serializers.ReadOnlyField()
    
    # Campos existentes
    puede_iniciar = serializers.ReadOnlyField()
    estado_dependencia = serializers.ReadOnlyField()
    
    class Meta:
        model = ItemProyecto
        fields = [
            'id',
            'numero_item',
            'nombre_item',
            'descripcion',
            'requiere_proveedor',
            'proveedor',
            'proveedor_nombre',
            'nombre_responsable_proveedor',
            'responsable_ejecucion',
            'responsable_nombre',
            'presupuesto_planificado',
            'presupuesto_ejecutado',
            'presupuesto_elasticidad',  # ⭐ NUEVO
            'presupuesto_limite',  # ⭐ NUEVO
            'porcentaje_presupuesto_usado',  # ⭐ NUEVO
            'esta_en_elasticidad',  # ⭐ NUEVO
            'excede_presupuesto_limite',  # ⭐ NUEVO
            'monto_excedido',  # ⭐ NUEVO
            'estado_presupuesto',  # ⭐ NUEVO
            'fecha_inicio',
            'duracion_dias',
            'fecha_fin_estimada',  # ⭐ NUEVO (calculado con días laborables)
            'dias_laborables_restantes',  # ⭐ NUEVO
            'esta_retrasado',  # ⭐ NUEVO
            'tiene_dependencia',
            'item_dependencia',
            'item_dependencia_numero',
            'estado',
            'porcentaje_avance',
            'puede_iniciar',
            'estado_dependencia',
            'fecha_completado',
            'observaciones',
            'fecha_creacion',
        ]



class ItemProyectoDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado de ítem con toda la información
    """
    responsable_info = UsuarioListSerializer(source='responsable_ejecucion', read_only=True)
    proveedor_info = serializers.SerializerMethodField()
    item_dependencia_info = serializers.SerializerMethodField()
    items_que_dependen = serializers.SerializerMethodField()
    
    # Display fields
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    # Propiedades calculadas
    diferencia_presupuesto = serializers.ReadOnlyField()
    puede_iniciar = serializers.ReadOnlyField()
    dias_restantes = serializers.ReadOnlyField()
    esta_vencido = serializers.ReadOnlyField()
    
    class Meta:
        model = ItemProyecto
        fields = '__all__'
    
    def get_proveedor_info(self, obj):
        """Información del proveedor si existe"""
        if obj.proveedor:
            return {
                'id': str(obj.proveedor.id),
                'razon_social': obj.proveedor.razon_social,
                'numero_documento_fiscal': obj.proveedor.numero_documento_fiscal,
                'tipo_documento_fiscal': obj.proveedor.tipo_documento_fiscal,
                'tipo_proveedor': obj.proveedor.tipo_proveedor.nombre if obj.proveedor.tipo_proveedor else None,  # ✅ CORRECTO
                'clasificacion': obj.proveedor.clasificacion.nombre if obj.proveedor.clasificacion else None,  # ✅ CORRECTO
                'email': obj.proveedor.email_contacto,
                'telefono': obj.proveedor.telefono_contacto,
            }
        return None
    
    def get_item_dependencia_info(self, obj):
        """Información del ítem del que depende"""
        if obj.item_dependencia:
            return {
                'id': str(obj.item_dependencia.id),
                'numero_item': obj.item_dependencia.numero_item,
                'nombre_item': obj.item_dependencia.nombre_item,
                'estado': obj.item_dependencia.estado,
                'estado_display': obj.item_dependencia.get_estado_display(),
                'porcentaje_avance': obj.item_dependencia.porcentaje_avance,
            }
        return None
    
    def get_items_que_dependen(self, obj):
        """Ítems que dependen de este"""
        dependientes = obj.items_dependientes.all()
        return [
            {
                'id': str(item.id),
                'numero_item': item.numero_item,
                'nombre_item': item.nombre_item,
                'estado': item.estado,
            }
            for item in dependientes
        ]


class ItemProyectoCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para CREAR/ACTUALIZAR ítems de proyecto
    """
    
    class Meta:
        model = ItemProyecto
        fields = [
            'proyecto',
            'numero_item',
            'nombre_item',
            'descripcion',
            'requiere_proveedor',
            'proveedor',
            'nombre_responsable_proveedor',
            'responsable_ejecucion',
            'presupuesto_planificado',
            'presupuesto_ejecutado',
            'fecha_inicio',
            'duracion_dias',
            'tiene_dependencia',
            'item_dependencia',
            'estado',
            'porcentaje_avance',
        ]
        read_only_fields = ['fecha_fin']  # Se calcula automáticamente

        extra_kwargs = {
            'requiere_proveedor': {'required': False},
            'proveedor': {'required': False},
            'tiene_dependencia': {'required': False},
            'item_dependencia': {'required': False},
        }
        
    def validate(self, attrs):
        """Validaciones cruzadas"""
        
        # ═══ 1. VALIDAR PROYECTO EN MODO POR_ITEMS ═══
        proyecto = attrs.get('proyecto') or (self.instance.proyecto if self.instance else None)
        
        if not proyecto:
            raise serializers.ValidationError({
                'proyecto': 'Debe especificar un proyecto'
            })
        
        if proyecto.modo_presupuesto != 'por_items':
            raise serializers.ValidationError({
                'proyecto': 'El proyecto debe estar en modo "por_items" para agregar ítems'
            })
        
        # ═══ 2. VALIDAR PROVEEDOR (solo si se está modificando) ═══
        # Solo validar si se envía requiere_proveedor o proveedor en la actualización
        if 'requiere_proveedor' in attrs or 'proveedor' in attrs:
            requiere_proveedor = attrs.get('requiere_proveedor', getattr(self.instance, 'requiere_proveedor', False))
            proveedor = attrs.get('proveedor', getattr(self.instance, 'proveedor', None) if self.instance else None)
            
            if requiere_proveedor and not proveedor:
                raise serializers.ValidationError({
                    'proveedor': 'Debe seleccionar un proveedor si requiere_proveedor=True'
                })
            
            if not requiere_proveedor and proveedor:
                raise serializers.ValidationError({
                    'proveedor': 'No debe seleccionar proveedor si requiere_proveedor=False'
                })
            
            # ⭐ VALIDAR EMPRESA (con soporte para proveedores globales)
            if proveedor:
                # Validar que esté activo
                if not proveedor.activo:
                    raise serializers.ValidationError({
                        'proveedor': 'El proveedor seleccionado no está activo'
                    })
                
                # Validar empresa (permitir proveedores globales)
                if proveedor.empresa is not None and proveedor.empresa != proyecto.empresa:
                    raise serializers.ValidationError({
                        'proveedor': f'El proveedor debe pertenecer a {proyecto.empresa.nombre} o ser un proveedor global'
                    })
        
        # ═══ 3. VALIDAR RESPONSABLE (solo si se está modificando) ═══
        if 'responsable_ejecucion' in attrs:
            responsable = attrs.get('responsable_ejecucion')
            if responsable and responsable.empresa != proyecto.empresa:
                raise serializers.ValidationError({
                    'responsable_ejecucion': f'El responsable debe pertenecer a {proyecto.empresa.nombre}'
                })
        
        # ═══ 4. VALIDAR FECHAS (solo si se modifican) ═══
        fecha_inicio = attrs.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None) if self.instance else None)
        duracion_dias = attrs.get('duracion_dias', getattr(self.instance, 'duracion_dias', None) if self.instance else None)
        
        if fecha_inicio and duracion_dias:
            # Validar que esté dentro del rango del proyecto
            fecha_fin_item = fecha_inicio + timedelta(days=duracion_dias)
            
            if fecha_inicio < proyecto.fecha_inicio:
                raise serializers.ValidationError({
                    'fecha_inicio': f'No puede ser anterior a la fecha de inicio del proyecto ({proyecto.fecha_inicio})'
                })
            
            if fecha_fin_item > proyecto.fecha_fin_estimada:
                raise serializers.ValidationError({
                    'duracion_dias': f'El ítem terminaría después del proyecto ({proyecto.fecha_fin_estimada})'
                })
        
        # ═══ 5. VALIDAR DEPENDENCIAS (solo si se modifican) ═══
        if 'tiene_dependencia' in attrs or 'item_dependencia' in attrs:
            tiene_dependencia = attrs.get('tiene_dependencia', getattr(self.instance, 'tiene_dependencia', False) if self.instance else False)
            item_dependencia = attrs.get('item_dependencia', getattr(self.instance, 'item_dependencia', None) if self.instance else None)
            
            if tiene_dependencia and not item_dependencia:
                raise serializers.ValidationError({
                    'item_dependencia': 'Debe seleccionar el ítem del que depende'
                })
            
            if not tiene_dependencia and item_dependencia:
                raise serializers.ValidationError({
                    'item_dependencia': 'No debe seleccionar dependencia si tiene_dependencia=False'
                })
            
            # Validar que la dependencia sea del mismo proyecto
            if item_dependencia and item_dependencia.proyecto != proyecto:
                raise serializers.ValidationError({
                    'item_dependencia': 'El ítem de dependencia debe ser del mismo proyecto'
                })
            
            # Validar que no se cree dependencia circular
            if item_dependencia and self.instance:
                numero_actual = attrs.get('numero_item', self.instance.numero_item)
                if item_dependencia.numero_item >= numero_actual:
                    raise serializers.ValidationError({
                        'item_dependencia': 'Solo puede depender de ítems anteriores (número menor)'
                    })
        
        # ═══ 6. VALIDAR PRESUPUESTO (solo si se modifican) ═══
        if 'presupuesto_planificado' in attrs:
            presupuesto_planificado = attrs.get('presupuesto_planificado')
            if presupuesto_planificado < 0:
                raise serializers.ValidationError({
                    'presupuesto_planificado': 'El presupuesto no puede ser negativo'
                })
        
        if 'presupuesto_ejecutado' in attrs:
            presupuesto_ejecutado = attrs.get('presupuesto_ejecutado')
            if presupuesto_ejecutado < 0:
                raise serializers.ValidationError({
                    'presupuesto_ejecutado': 'El presupuesto ejecutado no puede ser negativo'
                })
        
        # ═══ 7. VALIDAR ESTADO Y AVANCE ═══
        estado = attrs.get('estado', getattr(self.instance, 'estado', 'pendiente') if self.instance else 'pendiente')
        porcentaje_avance = attrs.get('porcentaje_avance', getattr(self.instance, 'porcentaje_avance', 0) if self.instance else 0)
        
        if estado == 'completado' and porcentaje_avance < 100:
            raise serializers.ValidationError({
                'porcentaje_avance': 'El avance debe ser 100% si el estado es "completado"'
            })
        
        return attrs

    def create(self, validated_data):
        """Crear ítem"""
        return ItemProyecto.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Actualizar ítem"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ═══════════════════════════════════════════════════════════════
# SERIALIZERS PARA PROYECTO (ACTUALIZADOS)
# ═══════════════════════════════════════════════════════════════

class ProyectoCierreBrechaListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para LISTADO de proyectos
    """
    
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    dimension_nombre = serializers.CharField(source='calculo_nivel.dimension.nombre', read_only=True)
    gap_original = serializers.ReadOnlyField()
    
    dueno_nombre = serializers.CharField(source='dueno_proyecto.nombre_completo', read_only=True)
    responsable_nombre = serializers.CharField(source='responsable_implementacion.nombre_completo', read_only=True)
    
    # Display fields
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)
    modo_presupuesto_display = serializers.CharField(source='get_modo_presupuesto_display', read_only=True)
    evaluacion_id = serializers.SerializerMethodField()
    # Propiedades calculadas
    dias_restantes = serializers.ReadOnlyField()
    dias_transcurridos = serializers.ReadOnlyField()
    esta_vencido = serializers.ReadOnlyField()
    presupuesto_total_planificado = serializers.ReadOnlyField()
    presupuesto_total_ejecutado = serializers.ReadOnlyField()
    porcentaje_presupuesto_gastado = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()
    items_completados = serializers.ReadOnlyField()
    porcentaje_avance_items = serializers.ReadOnlyField()
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = [
            'id',
            'codigo_proyecto',
            'nombre_proyecto',
            'empresa',
            'empresa_nombre',
            'dimension_nombre',
            'gap_original',
            'estado',
            'estado_display',
            'prioridad',
            'prioridad_display',
            'categoria',
            'categoria_display',
            'modo_presupuesto',
            'modo_presupuesto_display',
            'dueno_nombre',
            'responsable_nombre',
            'fecha_inicio',
            'evaluacion_id',
            'fecha_fin_estimada',
            'dias_restantes',
            'dias_transcurridos',
            'esta_vencido',
            'presupuesto_total_planificado',
            'presupuesto_total_ejecutado',
            'porcentaje_presupuesto_gastado',
            'moneda',
            'total_items',
            'items_completados',
            'porcentaje_avance_items',
            'fecha_creacion',
        ]
        
    def get_evaluacion_id(self, obj):
        """Obtener ID de la evaluación desde calculo_nivel"""
        try:
            if obj.calculo_nivel:
                # Intenta obtener desde el campo directo
                if hasattr(obj.calculo_nivel, 'evaluacion') and obj.calculo_nivel.evaluacion:
                    return str(obj.calculo_nivel.evaluacion.id)
                
                # Si no existe, intenta desde asignación
                if hasattr(obj.calculo_nivel, 'asignacion') and obj.calculo_nivel.asignacion:
                    if hasattr(obj.calculo_nivel.asignacion, 'encuesta') and obj.calculo_nivel.asignacion.encuesta:
                        return str(obj.calculo_nivel.asignacion.encuesta.id)
        except Exception as e:
            # Loggear el error si quieres debuggear
            # print(f"Error obteniendo evaluacion_id: {e}")
            pass
        
        return None

class ProyectoCierreBrechaDetailSerializer(serializers.ModelSerializer):
    """
    Serializer COMPLETO para DETALLE de un proyecto
    """
    
    # Relaciones
    empresa_info = EmpresaSerializer(source='empresa', read_only=True)
    calculo_nivel_info = serializers.SerializerMethodField()
    dueno_proyecto_info = UsuarioListSerializer(source='dueno_proyecto', read_only=True)
    responsable_implementacion_info = UsuarioListSerializer(source='responsable_implementacion', read_only=True)
    validador_interno_info = UsuarioListSerializer(source='validador_interno', read_only=True)
    creado_por_info = UsuarioListSerializer(source='creado_por', read_only=True)
    
    # Preguntas abordadas
    preguntas_abordadas_info = serializers.SerializerMethodField()
    
    # Ítems del proyecto (si modo_presupuesto='por_items')
    items = ItemProyectoListSerializer(many=True, read_only=True)
    
    # Display fields
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)
    modo_presupuesto_display = serializers.CharField(source='get_modo_presupuesto_display', read_only=True)
    moneda_display = serializers.CharField(source='get_moneda_display', read_only=True)
    resultado_final_display = serializers.CharField(source='get_resultado_final_display', read_only=True)
    
    # Propiedades calculadas
    dias_restantes = serializers.ReadOnlyField()
    dias_transcurridos = serializers.ReadOnlyField()
    duracion_estimada_dias = serializers.ReadOnlyField()
    esta_vencido = serializers.ReadOnlyField()
    gap_original = serializers.ReadOnlyField()
    dimension_nombre = serializers.ReadOnlyField()
    presupuesto_total_planificado = serializers.ReadOnlyField()
    presupuesto_total_ejecutado = serializers.ReadOnlyField()
    presupuesto_disponible = serializers.ReadOnlyField()
    porcentaje_presupuesto_gastado = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()
    items_completados = serializers.ReadOnlyField()
    porcentaje_avance_items = serializers.ReadOnlyField()
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = '__all__'
    
    def get_calculo_nivel_info(self, obj):
        """Información del GAP original"""
        if obj.calculo_nivel:
            return {
                'id': str(obj.calculo_nivel.id),
                'dimension': obj.calculo_nivel.dimension.nombre,
                'dimension_codigo': obj.calculo_nivel.dimension.codigo,
                'nivel_deseado': float(obj.calculo_nivel.nivel_deseado),
                'nivel_actual': float(obj.calculo_nivel.nivel_actual),
                'gap': float(obj.calculo_nivel.gap),
                'clasificacion_gap': obj.calculo_nivel.clasificacion_gap,
                'clasificacion_gap_display': obj.calculo_nivel.get_clasificacion_gap_display(),
                'porcentaje_cumplimiento': float(obj.calculo_nivel.porcentaje_cumplimiento),
                'calculado_at': obj.calculo_nivel.calculado_at,
            }
        return None
    
    def get_preguntas_abordadas_info(self, obj):
        """Información de las preguntas que aborda este proyecto"""
        preguntas = obj.preguntas_abordadas.filter(activo=True)
        return [
            {
                'id': str(p.id),
                'codigo': p.codigo,
                'titulo': p.titulo,
                'texto': p.texto,
            }
            for p in preguntas
        ]


class ProyectoCierreBrechaCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para CREAR un nuevo proyecto
    
    Soporta DOS modos:
    1. GLOBAL: Solo presupuesto_global
    2. POR_ITEMS: Se crean ítems después
    """
    
    preguntas_abordadas_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text='IDs de preguntas específicas'
    )
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = [
            # Básico
            'nombre_proyecto',
            'descripcion',
            'calculo_nivel',
            'fecha_inicio',
            'fecha_fin_estimada',
            'prioridad',
            'categoria',
            
            # Responsables
            'dueno_proyecto',
            'responsable_implementacion',
            'validador_interno',
            
            # Presupuesto
            'modo_presupuesto',
            'moneda',
            'presupuesto_global',  # Solo si modo_presupuesto='global'
            
            # Planificación
            'alcance_proyecto',
            'objetivos_especificos',
            'criterios_aceptacion',
            'riesgos_proyecto',
            'preguntas_abordadas_ids',
        ]
    
    def validate_calculo_nivel(self, value):
        """Validar que el GAP exista y esté activo"""
        if not value.activo:
            raise serializers.ValidationError('El GAP seleccionado no está activo')
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas"""
        
        # ═══ 1. VALIDAR FECHAS ═══
        fecha_inicio = attrs.get('fecha_inicio')
        fecha_fin = attrs.get('fecha_fin_estimada')
        
        if fecha_fin <= fecha_inicio:
            raise serializers.ValidationError({
                'fecha_fin_estimada': 'La fecha de fin debe ser posterior a la fecha de inicio'
            })
        
        duracion = (fecha_fin - fecha_inicio).days
        if duracion > 730:
            raise serializers.ValidationError({
                'fecha_fin_estimada': 'El proyecto no puede durar más de 2 años'
            })
        
        # ═══ 2. VALIDAR PERMISOS ═══
        user = self.context['request'].user
        calculo_nivel = attrs.get('calculo_nivel')
        
        if user.rol not in ['administrador', 'superadmin']:
            raise serializers.ValidationError(
                'Solo administradores pueden crear proyectos'
            )
        
        if user.rol == 'administrador':
            if calculo_nivel.empresa != user.empresa:
                raise serializers.ValidationError({
                    'calculo_nivel': 'Solo puedes crear proyectos para GAPs de tu empresa'
                })
        
        # ═══ 3. VALIDAR RESPONSABLES ═══
        empresa = calculo_nivel.empresa
        
        dueno = attrs.get('dueno_proyecto')
        if dueno.empresa != empresa:
            raise serializers.ValidationError({
                'dueno_proyecto': f'El dueño debe pertenecer a {empresa.nombre}'
            })
        
        responsable = attrs.get('responsable_implementacion')
        if responsable.empresa != empresa:
            raise serializers.ValidationError({
                'responsable_implementacion': f'El responsable debe pertenecer a {empresa.nombre}'
            })
        
        validador = attrs.get('validador_interno')
        if validador and validador.empresa != empresa:
            raise serializers.ValidationError({
                'validador_interno': f'El validador debe pertenecer a {empresa.nombre}'
            })
        
        # ═══ 4. VALIDAR MODO PRESUPUESTO ═══
        modo_presupuesto = attrs.get('modo_presupuesto', 'global')
        presupuesto_global = attrs.get('presupuesto_global', 0)
        
        if modo_presupuesto == 'global' and presupuesto_global <= 0:
            raise serializers.ValidationError({
                'presupuesto_global': 'Debe especificar un presupuesto mayor a 0 en modo global'
            })
        
        # ═══ 5. VALIDAR PREGUNTAS ═══
        preguntas_ids = attrs.pop('preguntas_abordadas_ids', [])
        if preguntas_ids:
            dimension = calculo_nivel.dimension
            preguntas = Pregunta.objects.filter(id__in=preguntas_ids, activo=True)
            
            if preguntas.count() != len(preguntas_ids):
                raise serializers.ValidationError({
                    'preguntas_abordadas_ids': 'Una o más preguntas no existen o están inactivas'
                })
            
            for pregunta in preguntas:
                if pregunta.dimension != dimension:
                    raise serializers.ValidationError({
                        'preguntas_abordadas_ids': f'La pregunta {pregunta.codigo} no pertenece a la dimensión {dimension.nombre}'
                    })
            
            attrs['_preguntas_validadas'] = preguntas
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Crear proyecto"""
        
        preguntas_validadas = validated_data.pop('_preguntas_validadas', [])
        
        calculo_nivel = validated_data['calculo_nivel']
        validated_data['empresa'] = calculo_nivel.empresa
        validated_data['creado_por'] = self.context['request'].user
        validated_data['estado'] = 'planificado'
        
        proyecto = ProyectoCierreBrecha.objects.create(**validated_data)
        
        if preguntas_validadas:
            proyecto.preguntas_abordadas.set(preguntas_validadas)
        
        return proyecto


class ProyectoCierreBrechaUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para ACTUALIZAR un proyecto existente
    """
    
    preguntas_abordadas_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = [
            'nombre_proyecto',
            'descripcion',
            'fecha_fin_estimada',
            'prioridad',
            'categoria',
            'estado',
            'alcance_proyecto',
            'objetivos_especificos',
            'criterios_aceptacion',
            'riesgos_proyecto',
            'dueno_proyecto',
            'responsable_implementacion',
            'validador_interno',
            'presupuesto_global',  # Solo en modo global
            'presupuesto_global_gastado',  # Solo en modo global
            'lecciones_aprendidas',
            'preguntas_abordadas_ids',
        ]
    
    def validate_estado(self, value):
        """Validar transiciones de estado"""
        if self.instance:
            estado_actual = self.instance.estado
            
            transiciones_validas = {
                'planificado': ['en_ejecucion', 'cancelado'],
                'en_ejecucion': ['en_validacion', 'suspendido', 'cancelado'],
                'en_validacion': ['cerrado', 'en_ejecucion'],
                'suspendido': ['en_ejecucion', 'cancelado'],
                'cerrado': [],
                'cancelado': [],
            }
            
            if value != estado_actual:
                if value not in transiciones_validas.get(estado_actual, []):
                    raise serializers.ValidationError(
                        f'No se puede cambiar de "{estado_actual}" a "{value}"'
                    )
        
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas"""
        
        user = self.context['request'].user
        
        # Validar permisos
        if user.rol == 'administrador':
            if self.instance.empresa != user.empresa:
                raise serializers.ValidationError('Solo puedes editar proyectos de tu empresa')
        elif user.rol not in ['superadmin']:
            raise serializers.ValidationError('No tienes permisos para editar proyectos')
        
        # Validar fechas
        fecha_fin = attrs.get('fecha_fin_estimada')
        if fecha_fin and fecha_fin <= self.instance.fecha_inicio:
            raise serializers.ValidationError({
                'fecha_fin_estimada': 'La fecha de fin debe ser posterior a la fecha de inicio'
            })
        
        # Validar responsables
        empresa = self.instance.empresa
        
        dueno = attrs.get('dueno_proyecto')
        if dueno and dueno.empresa != empresa:
            raise serializers.ValidationError({
                'dueno_proyecto': f'El dueño debe pertenecer a {empresa.nombre}'
            })
        
        responsable = attrs.get('responsable_implementacion')
        if responsable and responsable.empresa != empresa:
            raise serializers.ValidationError({
                'responsable_implementacion': f'El responsable debe pertenecer a {empresa.nombre}'
            })
        
        # Validar preguntas
        preguntas_ids = attrs.pop('preguntas_abordadas_ids', None)
        if preguntas_ids is not None:
            dimension = self.instance.calculo_nivel.dimension
            preguntas = Pregunta.objects.filter(id__in=preguntas_ids, activo=True)
            
            for pregunta in preguntas:
                if pregunta.dimension != dimension:
                    raise serializers.ValidationError({
                        'preguntas_abordadas_ids': f'La pregunta {pregunta.codigo} no pertenece a la dimensión {dimension.nombre}'
                    })
            
            attrs['_preguntas_validadas'] = preguntas
        
        return attrs
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Actualizar proyecto"""
        
        preguntas_validadas = validated_data.pop('_preguntas_validadas', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.version += 1
        instance.save()
        
        if preguntas_validadas is not None:
            instance.preguntas_abordadas.set(preguntas_validadas)
        
        return instance


# ═══════════════════════════════════════════════════════════════
# SERIALIZERS ESPECIALES
# ═══════════════════════════════════════════════════════════════

class ProyectoSimpleSerializer(serializers.ModelSerializer):
    """Serializer ultra-simple para referencias rápidas"""
    
    modo_presupuesto_display = serializers.CharField(source='get_modo_presupuesto_display', read_only=True)
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = [
            'id',
            'codigo_proyecto',
            'nombre_proyecto',
            'estado',
            'modo_presupuesto',
            'modo_presupuesto_display',
        ]
        
# SERIALIZERS nuevos agregados para ítems con nuevos campos y aprobaciones GAP

from apps.proyectos_remediacion.models import AprobacionGAP



# ═══════════════════════════════════════════════════════════════
# SERIALIZERS PARA APROBACIÓN DE GAP
# ═══════════════════════════════════════════════════════════════

class AprobacionGAPListSerializer(serializers.ModelSerializer):
    """
    Serializer para listar aprobaciones
    """
    
    proyecto_codigo = serializers.CharField(source='proyecto.codigo_proyecto', read_only=True)
    proyecto_nombre = serializers.CharField(source='proyecto.nombre_proyecto', read_only=True)
    solicitado_por_nombre = serializers.CharField(source='solicitado_por.nombre_completo', read_only=True)
    validador_nombre = serializers.CharField(source='validador.nombre_completo', read_only=True)
    
    # Campos calculados
    esta_pendiente = serializers.ReadOnlyField()
    dias_pendiente = serializers.ReadOnlyField()
    porcentaje_completitud = serializers.ReadOnlyField()
    porcentaje_presupuesto_usado = serializers.ReadOnlyField()
    
    class Meta:
        model = AprobacionGAP
        fields = [
            'id',
            'proyecto',
            'proyecto_codigo',
            'proyecto_nombre',
            'solicitado_por',
            'solicitado_por_nombre',
            'validador',
            'validador_nombre',
            'fecha_solicitud',
            'estado',
            'fecha_revision',
            'esta_pendiente',
            'dias_pendiente',
            'items_completados',
            'items_totales',
            'porcentaje_completitud',
            'presupuesto_ejecutado',
            'presupuesto_planificado',
            'porcentaje_presupuesto_usado',
            'gap_original',
            'fecha_creacion',
        ]


class AprobacionGAPDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para una aprobación
    """
    
    proyecto_info = ProyectoCierreBrechaDetailSerializer(source='proyecto', read_only=True)
    solicitado_por_info = serializers.SerializerMethodField()
    validador_info = serializers.SerializerMethodField()
    
    # Campos calculados
    esta_pendiente = serializers.ReadOnlyField()
    fue_aprobado = serializers.ReadOnlyField()
    fue_rechazado = serializers.ReadOnlyField()
    dias_pendiente = serializers.ReadOnlyField()
    porcentaje_completitud = serializers.ReadOnlyField()
    porcentaje_presupuesto_usado = serializers.ReadOnlyField()
    
    class Meta:
        model = AprobacionGAP
        fields = [
            'id',
            'proyecto',
            'proyecto_info',
            'solicitado_por',
            'solicitado_por_info',
            'validador',
            'validador_info',
            'fecha_solicitud',
            'comentarios_solicitud',
            'estado',
            'fecha_revision',
            'observaciones',
            'documentos_adjuntos',
            'items_completados',
            'items_totales',
            'presupuesto_ejecutado',
            'presupuesto_planificado',
            'gap_original',
            'esta_pendiente',
            'fue_aprobado',
            'fue_rechazado',
            'dias_pendiente',
            'porcentaje_completitud',
            'porcentaje_presupuesto_usado',
            'fecha_creacion',
        ]
    
    def get_solicitado_por_info(self, obj):
        return {
            'id': str(obj.solicitado_por.id),
            'nombre_completo': obj.solicitado_por.nombre_completo,
            'email': obj.solicitado_por.email,
        }
    
    def get_validador_info(self, obj):
        return {
            'id': str(obj.validador.id),
            'nombre_completo': obj.validador.nombre_completo,
            'email': obj.validador.email,
        }


class SolicitarAprobacionSerializer(serializers.Serializer):
    """
    Serializer para solicitar la aprobación de cierre de GAP
    """
    
    comentarios = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Comentarios opcionales al solicitar la aprobación'
    )
    
    documentos_adjuntos = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        allow_empty=True,
        help_text='URLs de documentos de evidencia'
    )


class ResponderAprobacionSerializer(serializers.Serializer):
    """
    Serializer para aprobar o rechazar una solicitud
    """
    
    aprobado = serializers.BooleanField(
        help_text='True para aprobar, False para rechazar'
    )
    
    observaciones = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Observaciones del validador (requerido si rechaza)'
    )
    
    def validate(self, attrs):
        # Si rechaza, las observaciones son obligatorias
        if not attrs.get('aprobado') and not attrs.get('observaciones'):
            raise serializers.ValidationError({
                'observaciones': 'Las observaciones son obligatorias al rechazar'
            })
        
        return attrs
    
