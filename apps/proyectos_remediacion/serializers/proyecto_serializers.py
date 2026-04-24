# apps/proyectos_remediacion/serializers/proyecto_serializers.py

from rest_framework import serializers
from django.db import transaction

from apps.proyectos_remediacion.models import ProyectoCierreBrecha
from apps.proyectos_remediacion.serializers.item_serializers import ItemProyectoListSerializer
from apps.encuestas.models import Pregunta
from apps.empresas.serializers import EmpresaSerializer
from apps.usuarios.serializers import UsuarioListSerializer


class ProyectoCierreBrechaListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para LISTADO de proyectos
    """

    empresa_nombre     = serializers.CharField(source='empresa.nombre',                    read_only=True)
    dimension_nombre   = serializers.CharField(source='calculo_nivel.dimension.nombre',    read_only=True)
    dueno_nombre       = serializers.CharField(source='dueno_proyecto.nombre_completo',    read_only=True)
    responsable_nombre = serializers.CharField(source='responsable_implementacion.nombre_completo', read_only=True)

    gap_original = serializers.ReadOnlyField()

    # Display fields
    estado_display          = serializers.CharField(source='get_estado_display',          read_only=True)
    prioridad_display       = serializers.CharField(source='get_prioridad_display',       read_only=True)
    categoria_display       = serializers.CharField(source='get_categoria_display',       read_only=True)
    modo_presupuesto_display = serializers.CharField(source='get_modo_presupuesto_display', read_only=True)

    evaluacion_id = serializers.SerializerMethodField()

    # Propiedades calculadas
    dias_restantes                = serializers.ReadOnlyField()
    dias_transcurridos            = serializers.ReadOnlyField()
    esta_vencido                  = serializers.ReadOnlyField()
    presupuesto_total_planificado = serializers.ReadOnlyField()
    presupuesto_total_ejecutado   = serializers.ReadOnlyField()
    porcentaje_presupuesto_gastado = serializers.ReadOnlyField()
    total_items                   = serializers.ReadOnlyField()
    items_completados             = serializers.ReadOnlyField()
    porcentaje_avance_items       = serializers.ReadOnlyField()

    class Meta:
        model  = ProyectoCierreBrecha
        fields = [
            'id', 'codigo_proyecto', 'nombre_proyecto',
            'empresa', 'empresa_nombre',
            'dimension_nombre', 'gap_original',
            'estado', 'estado_display',
            'prioridad', 'prioridad_display',
            'categoria', 'categoria_display',
            'modo_presupuesto', 'modo_presupuesto_display',
            'dueno_nombre', 'responsable_nombre',
            'fecha_inicio', 'evaluacion_id', 'fecha_fin_estimada',
            'dias_restantes', 'dias_transcurridos', 'esta_vencido',
            'presupuesto_total_planificado', 'presupuesto_total_ejecutado',
            'porcentaje_presupuesto_gastado', 'moneda',
            'total_items', 'items_completados', 'porcentaje_avance_items',
            'fecha_creacion',
        ]

    def get_evaluacion_id(self, obj):
        try:
            if obj.calculo_nivel:
                if hasattr(obj.calculo_nivel, 'evaluacion') and obj.calculo_nivel.evaluacion:
                    return str(obj.calculo_nivel.evaluacion.id)
                if hasattr(obj.calculo_nivel, 'asignacion') and obj.calculo_nivel.asignacion:
                    if hasattr(obj.calculo_nivel.asignacion, 'encuesta') and obj.calculo_nivel.asignacion.encuesta:
                        return str(obj.calculo_nivel.asignacion.encuesta.id)
        except Exception:
            pass
        return None


class ProyectoCierreBrechaDetailSerializer(serializers.ModelSerializer):
    """
    Serializer COMPLETO para DETALLE de un proyecto
    """

    empresa_info                   = EmpresaSerializer(source='empresa', read_only=True)
    calculo_nivel_info             = serializers.SerializerMethodField()
    dueno_proyecto_info            = UsuarioListSerializer(source='dueno_proyecto',            read_only=True)
    responsable_implementacion_info = UsuarioListSerializer(source='responsable_implementacion', read_only=True)
    validador_interno_info         = UsuarioListSerializer(source='validador_interno',          read_only=True)
    creado_por_info                = UsuarioListSerializer(source='creado_por',                 read_only=True)

    preguntas_abordadas_info = serializers.SerializerMethodField()
    items                    = ItemProyectoListSerializer(many=True, read_only=True)

    # Display fields
    estado_display           = serializers.CharField(source='get_estado_display',           read_only=True)
    prioridad_display        = serializers.CharField(source='get_prioridad_display',        read_only=True)
    categoria_display        = serializers.CharField(source='get_categoria_display',        read_only=True)
    modo_presupuesto_display = serializers.CharField(source='get_modo_presupuesto_display', read_only=True)
    moneda_display           = serializers.CharField(source='get_moneda_display',           read_only=True)
    resultado_final_display  = serializers.CharField(source='get_resultado_final_display',  read_only=True)

    # Propiedades calculadas
    dias_restantes                 = serializers.ReadOnlyField()
    dias_transcurridos             = serializers.ReadOnlyField()
    duracion_estimada_dias         = serializers.ReadOnlyField()
    porcentaje_tiempo_transcurrido = serializers.ReadOnlyField()
    esta_vencido                   = serializers.ReadOnlyField()
    gap_original                   = serializers.ReadOnlyField()
    dimension_nombre               = serializers.ReadOnlyField()
    presupuesto_total_planificado  = serializers.ReadOnlyField()
    presupuesto_total_ejecutado    = serializers.ReadOnlyField()
    presupuesto_disponible         = serializers.ReadOnlyField()
    porcentaje_presupuesto_gastado = serializers.ReadOnlyField()
    total_items                    = serializers.ReadOnlyField()
    items_completados              = serializers.ReadOnlyField()
    porcentaje_avance_items        = serializers.ReadOnlyField()

    class Meta:
        model  = ProyectoCierreBrecha
        fields = '__all__'

    def get_calculo_nivel_info(self, obj):
        if obj.calculo_nivel:
            return {
                'id':                        str(obj.calculo_nivel.id),
                'dimension':                 obj.calculo_nivel.dimension.nombre,
                'dimension_codigo':          obj.calculo_nivel.dimension.codigo,
                'nivel_deseado':             float(obj.calculo_nivel.nivel_deseado),
                'nivel_actual':              float(obj.calculo_nivel.nivel_actual),
                'gap':                       float(obj.calculo_nivel.gap),
                'clasificacion_gap':         obj.calculo_nivel.clasificacion_gap,
                'clasificacion_gap_display': obj.calculo_nivel.get_clasificacion_gap_display(),
                'porcentaje_cumplimiento':   float(obj.calculo_nivel.porcentaje_cumplimiento),
                'calculado_at':              obj.calculo_nivel.calculado_at,
            }
        return None

    def get_preguntas_abordadas_info(self, obj):
        return [
            {
                'id':     str(p.id),
                'codigo': p.codigo,
                'titulo': p.titulo,
                'texto':  p.texto,
            }
            for p in obj.preguntas_abordadas.filter(activo=True)
        ]


class ProyectoCierreBrechaCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para CREAR un nuevo proyecto
    """

    preguntas_abordadas_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model  = ProyectoCierreBrecha
        fields = [
            'nombre_proyecto', 'descripcion', 'calculo_nivel',
            'fecha_inicio', 'fecha_fin_estimada', 'prioridad', 'categoria',
            'dueno_proyecto', 'responsable_implementacion', 'validador_interno',
            'modo_presupuesto', 'moneda', 'presupuesto_global',
            'alcance_proyecto', 'objetivos_especificos', 'criterios_aceptacion',
            'riesgos_proyecto', 'preguntas_abordadas_ids',
        ]

    def validate_calculo_nivel(self, value):
        if not value.activo:
            raise serializers.ValidationError('El GAP seleccionado no está activo')
        return value

    def validate(self, attrs):
        # ─── Fechas ──────────────────────────────────────────────────────────
        fecha_inicio = attrs.get('fecha_inicio')
        fecha_fin    = attrs.get('fecha_fin_estimada')

        if fecha_fin <= fecha_inicio:
            raise serializers.ValidationError({'fecha_fin_estimada': 'La fecha de fin debe ser posterior a la fecha de inicio'})

        if (fecha_fin - fecha_inicio).days > 730:
            raise serializers.ValidationError({'fecha_fin_estimada': 'El proyecto no puede durar más de 2 años'})

        # ─── Permisos ────────────────────────────────────────────────────────
        user          = self.context['request'].user
        calculo_nivel = attrs.get('calculo_nivel')

        if user.rol not in ['administrador', 'superadmin']:
            raise serializers.ValidationError('Solo administradores pueden crear proyectos')

        if user.rol == 'administrador' and calculo_nivel.empresa != user.empresa:
            raise serializers.ValidationError({'calculo_nivel': 'Solo puedes crear proyectos para GAPs de tu empresa'})

        # ─── Responsables ────────────────────────────────────────────────────
        empresa = calculo_nivel.empresa

        dueno = attrs.get('dueno_proyecto')
        if dueno.empresa != empresa:
            raise serializers.ValidationError({'dueno_proyecto': f'El dueño debe pertenecer a {empresa.nombre}'})

        responsable = attrs.get('responsable_implementacion')
        if responsable.empresa != empresa:
            raise serializers.ValidationError({'responsable_implementacion': f'El responsable debe pertenecer a {empresa.nombre}'})

        validador = attrs.get('validador_interno')
        if validador and validador.empresa != empresa:
            raise serializers.ValidationError({'validador_interno': f'El validador debe pertenecer a {empresa.nombre}'})

        # ─── Presupuesto ─────────────────────────────────────────────────────
        modo_presupuesto  = attrs.get('modo_presupuesto', 'global')
        presupuesto_global = attrs.get('presupuesto_global', 0)

        if modo_presupuesto == 'global' and presupuesto_global <= 0:
            raise serializers.ValidationError({'presupuesto_global': 'Debe especificar un presupuesto mayor a 0 en modo global'})

        # ─── Preguntas ───────────────────────────────────────────────────────
        preguntas_ids = attrs.pop('preguntas_abordadas_ids', [])
        if preguntas_ids:
            dimension  = calculo_nivel.dimension
            preguntas  = Pregunta.objects.filter(id__in=preguntas_ids, activo=True)

            if preguntas.count() != len(preguntas_ids):
                raise serializers.ValidationError({'preguntas_abordadas_ids': 'Una o más preguntas no existen o están inactivas'})

            for pregunta in preguntas:
                if pregunta.dimension != dimension:
                    raise serializers.ValidationError({
                        'preguntas_abordadas_ids': f'La pregunta {pregunta.codigo} no pertenece a la dimensión {dimension.nombre}'
                    })

            attrs['_preguntas_validadas'] = preguntas

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        preguntas_validadas = validated_data.pop('_preguntas_validadas', [])

        validated_data['empresa']    = validated_data['calculo_nivel'].empresa
        validated_data['creado_por'] = self.context['request'].user
        validated_data['estado']     = 'planificado'

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
        model  = ProyectoCierreBrecha
        fields = [
            'nombre_proyecto', 'descripcion', 'fecha_fin_estimada',
            'prioridad', 'categoria', 'estado',
            'alcance_proyecto', 'objetivos_especificos', 'criterios_aceptacion',
            'riesgos_proyecto',
            'dueno_proyecto', 'responsable_implementacion', 'validador_interno',
            'presupuesto_global', 'presupuesto_global_gastado',
            'lecciones_aprendidas', 'preguntas_abordadas_ids',
        ]

    def validate_estado(self, value):
        if self.instance:
            estado_actual = self.instance.estado
            transiciones_validas = {
                'planificado':   ['en_ejecucion', 'cancelado'],
                'en_ejecucion':  ['en_validacion', 'suspendido', 'cancelado'],
                'en_validacion': ['cerrado', 'en_ejecucion'],
                'suspendido':    ['en_ejecucion', 'cancelado'],
                'cerrado':       [],
                'cancelado':     [],
            }
            if value != estado_actual and value not in transiciones_validas.get(estado_actual, []):
                raise serializers.ValidationError(f'No se puede cambiar de "{estado_actual}" a "{value}"')
        return value

    def validate(self, attrs):
        user = self.context['request'].user

        if user.rol == 'administrador' and self.instance.empresa != user.empresa:
            raise serializers.ValidationError('Solo puedes editar proyectos de tu empresa')
        elif user.rol not in ['superadmin', 'administrador']:
            raise serializers.ValidationError('No tienes permisos para editar proyectos')

        fecha_fin = attrs.get('fecha_fin_estimada')
        if fecha_fin and fecha_fin <= self.instance.fecha_inicio:
            raise serializers.ValidationError({'fecha_fin_estimada': 'La fecha de fin debe ser posterior a la fecha de inicio'})

        empresa = self.instance.empresa

        dueno = attrs.get('dueno_proyecto')
        if dueno and dueno.empresa != empresa:
            raise serializers.ValidationError({'dueno_proyecto': f'El dueño debe pertenecer a {empresa.nombre}'})

        responsable = attrs.get('responsable_implementacion')
        if responsable and responsable.empresa != empresa:
            raise serializers.ValidationError({'responsable_implementacion': f'El responsable debe pertenecer a {empresa.nombre}'})

        preguntas_ids = attrs.pop('preguntas_abordadas_ids', None)
        if preguntas_ids is not None:
            dimension  = self.instance.calculo_nivel.dimension
            preguntas  = Pregunta.objects.filter(id__in=preguntas_ids, activo=True)

            for pregunta in preguntas:
                if pregunta.dimension != dimension:
                    raise serializers.ValidationError({
                        'preguntas_abordadas_ids': f'La pregunta {pregunta.codigo} no pertenece a la dimensión {dimension.nombre}'
                    })

            attrs['_preguntas_validadas'] = preguntas

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        preguntas_validadas = validated_data.pop('_preguntas_validadas', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.version += 1
        instance.save()

        if preguntas_validadas is not None:
            instance.preguntas_abordadas.set(preguntas_validadas)

        return instance


class ProyectoSimpleSerializer(serializers.ModelSerializer):
    """Serializer ultra-simple para referencias rápidas"""

    modo_presupuesto_display = serializers.CharField(source='get_modo_presupuesto_display', read_only=True)

    class Meta:
        model  = ProyectoCierreBrecha
        fields = ['id', 'codigo_proyecto', 'nombre_proyecto', 'estado', 'modo_presupuesto', 'modo_presupuesto_display']