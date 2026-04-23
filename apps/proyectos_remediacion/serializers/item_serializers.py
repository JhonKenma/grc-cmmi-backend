# apps/proyectos_remediacion/serializers/item_serializers.py

from rest_framework import serializers
from datetime import timedelta

from apps.proyectos_remediacion.models import ItemProyecto
from apps.usuarios.serializers import UsuarioListSerializer


class ItemProyectoListSerializer(serializers.ModelSerializer):
    """
    Serializer para listar ítems con fechas laborables y elasticidad
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

    # Campos calculados — fechas laborables
    fecha_fin_estimada          = serializers.ReadOnlyField()
    dias_laborables_restantes   = serializers.ReadOnlyField()
    esta_retrasado              = serializers.ReadOnlyField()

    # Elasticidad de presupuesto
    presupuesto_elasticidad     = serializers.ReadOnlyField()
    presupuesto_limite          = serializers.ReadOnlyField()
    porcentaje_presupuesto_usado = serializers.ReadOnlyField()
    esta_en_elasticidad         = serializers.ReadOnlyField()
    excede_presupuesto_limite   = serializers.ReadOnlyField()
    monto_excedido              = serializers.ReadOnlyField()
    estado_presupuesto          = serializers.ReadOnlyField()

    # Campos existentes
    puede_iniciar               = serializers.ReadOnlyField()
    estado_dependencia          = serializers.ReadOnlyField()

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
            'presupuesto_elasticidad',
            'presupuesto_limite',
            'porcentaje_presupuesto_usado',
            'esta_en_elasticidad',
            'excede_presupuesto_limite',
            'monto_excedido',
            'estado_presupuesto',
            'fecha_inicio',
            'duracion_dias',
            'fecha_fin_estimada',
            'dias_laborables_restantes',
            'esta_retrasado',
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

    responsable_info      = UsuarioListSerializer(source='responsable_ejecucion', read_only=True)
    proveedor_info        = serializers.SerializerMethodField()
    item_dependencia_info = serializers.SerializerMethodField()
    items_que_dependen    = serializers.SerializerMethodField()

    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    # Propiedades calculadas
    diferencia_presupuesto = serializers.ReadOnlyField()
    puede_iniciar          = serializers.ReadOnlyField()
    dias_restantes         = serializers.ReadOnlyField()
    esta_vencido           = serializers.ReadOnlyField()

    class Meta:
        model  = ItemProyecto
        fields = '__all__'

    def get_proveedor_info(self, obj):
        if obj.proveedor:
            return {
                'id':                       str(obj.proveedor.id),
                'razon_social':             obj.proveedor.razon_social,
                'numero_documento_fiscal':  obj.proveedor.numero_documento_fiscal,
                'tipo_documento_fiscal':    obj.proveedor.tipo_documento_fiscal,
                'tipo_proveedor':           obj.proveedor.tipo_proveedor.nombre if obj.proveedor.tipo_proveedor else None,
                'clasificacion':            obj.proveedor.clasificacion.nombre if obj.proveedor.clasificacion else None,
                'email':                    obj.proveedor.email_contacto,
                'telefono':                 obj.proveedor.telefono_contacto,
            }
        return None

    def get_item_dependencia_info(self, obj):
        if obj.item_dependencia:
            return {
                'id':              str(obj.item_dependencia.id),
                'numero_item':     obj.item_dependencia.numero_item,
                'nombre_item':     obj.item_dependencia.nombre_item,
                'estado':          obj.item_dependencia.estado,
                'estado_display':  obj.item_dependencia.get_estado_display(),
                'porcentaje_avance': obj.item_dependencia.porcentaje_avance,
            }
        return None

    def get_items_que_dependen(self, obj):
        return [
            {
                'id':          str(item.id),
                'numero_item': item.numero_item,
                'nombre_item': item.nombre_item,
                'estado':      item.estado,
            }
            for item in obj.items_dependientes.all()
        ]


class ItemProyectoCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para CREAR / ACTUALIZAR ítems de proyecto
    """

    class Meta:
        model  = ItemProyecto
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
        read_only_fields = ['fecha_fin']

        extra_kwargs = {
            'requiere_proveedor': {'required': False},
            'proveedor':          {'required': False},
            'tiene_dependencia':  {'required': False},
            'item_dependencia':   {'required': False},
        }

    def validate(self, attrs):
        # ─── 1. Proyecto en modo por_items ───────────────────────────────────
        proyecto = attrs.get('proyecto') or (self.instance.proyecto if self.instance else None)

        if not proyecto:
            raise serializers.ValidationError({'proyecto': 'Debe especificar un proyecto'})

        if proyecto.modo_presupuesto != 'por_items':
            raise serializers.ValidationError({
                'proyecto': 'El proyecto debe estar en modo "por_items" para agregar ítems'
            })

        # ─── 2. Proveedor ────────────────────────────────────────────────────
        if 'requiere_proveedor' in attrs or 'proveedor' in attrs:
            requiere_proveedor = attrs.get('requiere_proveedor', getattr(self.instance, 'requiere_proveedor', False))
            proveedor          = attrs.get('proveedor', getattr(self.instance, 'proveedor', None) if self.instance else None)

            if requiere_proveedor and not proveedor:
                raise serializers.ValidationError({'proveedor': 'Debe seleccionar un proveedor si requiere_proveedor=True'})

            if not requiere_proveedor and proveedor:
                raise serializers.ValidationError({'proveedor': 'No debe seleccionar proveedor si requiere_proveedor=False'})

            if proveedor:
                if not proveedor.activo:
                    raise serializers.ValidationError({'proveedor': 'El proveedor seleccionado no está activo'})
                if proveedor.empresa is not None and proveedor.empresa != proyecto.empresa:
                    raise serializers.ValidationError({
                        'proveedor': f'El proveedor debe pertenecer a {proyecto.empresa.nombre} o ser un proveedor global'
                    })

        # ─── 3. Responsable ──────────────────────────────────────────────────
        if 'responsable_ejecucion' in attrs:
            responsable = attrs.get('responsable_ejecucion')
            if responsable and responsable.empresa != proyecto.empresa:
                raise serializers.ValidationError({
                    'responsable_ejecucion': f'El responsable debe pertenecer a {proyecto.empresa.nombre}'
                })

        # ─── 4. Fechas ───────────────────────────────────────────────────────
        fecha_inicio  = attrs.get('fecha_inicio',  getattr(self.instance, 'fecha_inicio',  None) if self.instance else None)
        duracion_dias = attrs.get('duracion_dias', getattr(self.instance, 'duracion_dias', None) if self.instance else None)

        if fecha_inicio and duracion_dias:
            fecha_fin_item = fecha_inicio + timedelta(days=duracion_dias)

            if fecha_inicio < proyecto.fecha_inicio:
                raise serializers.ValidationError({
                    'fecha_inicio': f'No puede ser anterior a la fecha de inicio del proyecto ({proyecto.fecha_inicio})'
                })
            if fecha_fin_item > proyecto.fecha_fin_estimada:
                raise serializers.ValidationError({
                    'duracion_dias': f'El ítem terminaría después del proyecto ({proyecto.fecha_fin_estimada})'
                })

        # ─── 5. Dependencias ─────────────────────────────────────────────────
        if 'tiene_dependencia' in attrs or 'item_dependencia' in attrs:
            tiene_dependencia = attrs.get('tiene_dependencia', getattr(self.instance, 'tiene_dependencia', False) if self.instance else False)
            item_dependencia  = attrs.get('item_dependencia', getattr(self.instance, 'item_dependencia', None) if self.instance else None)

            if tiene_dependencia and not item_dependencia:
                raise serializers.ValidationError({'item_dependencia': 'Debe seleccionar el ítem del que depende'})

            if not tiene_dependencia and item_dependencia:
                raise serializers.ValidationError({'item_dependencia': 'No debe seleccionar dependencia si tiene_dependencia=False'})

            if item_dependencia and item_dependencia.proyecto != proyecto:
                raise serializers.ValidationError({'item_dependencia': 'El ítem de dependencia debe ser del mismo proyecto'})

            if item_dependencia and self.instance:
                numero_actual = attrs.get('numero_item', self.instance.numero_item)
                if item_dependencia.numero_item >= numero_actual:
                    raise serializers.ValidationError({'item_dependencia': 'Solo puede depender de ítems anteriores (número menor)'})

        # ─── 6. Presupuesto ──────────────────────────────────────────────────
        if 'presupuesto_planificado' in attrs and attrs['presupuesto_planificado'] < 0:
            raise serializers.ValidationError({'presupuesto_planificado': 'El presupuesto no puede ser negativo'})

        if 'presupuesto_ejecutado' in attrs and attrs['presupuesto_ejecutado'] < 0:
            raise serializers.ValidationError({'presupuesto_ejecutado': 'El presupuesto ejecutado no puede ser negativo'})

        # ─── 7. Estado y avance ──────────────────────────────────────────────
        estado            = attrs.get('estado',            getattr(self.instance, 'estado',            'pendiente') if self.instance else 'pendiente')
        porcentaje_avance = attrs.get('porcentaje_avance', getattr(self.instance, 'porcentaje_avance', 0)           if self.instance else 0)

        if estado == 'completado' and porcentaje_avance < 100:
            raise serializers.ValidationError({'porcentaje_avance': 'El avance debe ser 100% si el estado es "completado"'})

        return attrs

    def create(self, validated_data):
        return ItemProyecto.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance