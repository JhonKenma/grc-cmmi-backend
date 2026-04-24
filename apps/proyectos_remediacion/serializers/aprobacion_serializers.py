# apps/proyectos_remediacion/serializers/aprobacion_serializers.py

from rest_framework import serializers

from apps.proyectos_remediacion.models import AprobacionGAP


class AprobacionGAPListSerializer(serializers.ModelSerializer):
    """
    Serializer para listar aprobaciones
    """

    proyecto_codigo      = serializers.CharField(source='proyecto.codigo_proyecto',  read_only=True)
    proyecto_nombre      = serializers.CharField(source='proyecto.nombre_proyecto',  read_only=True)
    solicitado_por_nombre = serializers.CharField(source='solicitado_por.nombre_completo', read_only=True)
    validador_nombre     = serializers.CharField(source='validador.nombre_completo', read_only=True)

    # Campos calculados
    esta_pendiente              = serializers.ReadOnlyField()
    dias_pendiente              = serializers.ReadOnlyField()
    porcentaje_completitud      = serializers.ReadOnlyField()
    porcentaje_presupuesto_usado = serializers.ReadOnlyField()

    class Meta:
        model  = AprobacionGAP
        fields = [
            'id',
            'proyecto', 'proyecto_codigo', 'proyecto_nombre',
            'solicitado_por', 'solicitado_por_nombre',
            'validador', 'validador_nombre',
            'fecha_solicitud', 'estado', 'fecha_revision',
            'esta_pendiente', 'dias_pendiente',
            'items_completados', 'items_totales', 'porcentaje_completitud',
            'presupuesto_ejecutado', 'presupuesto_planificado', 'porcentaje_presupuesto_usado',
            'gap_original',
            'fecha_creacion',
        ]


class AprobacionGAPDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para una aprobación
    """

    # Se importa inline para evitar importaciones circulares
    proyecto_info         = serializers.SerializerMethodField()
    solicitado_por_info   = serializers.SerializerMethodField()
    validador_info        = serializers.SerializerMethodField()

    # Campos calculados
    esta_pendiente              = serializers.ReadOnlyField()
    fue_aprobado                = serializers.ReadOnlyField()
    fue_rechazado               = serializers.ReadOnlyField()
    dias_pendiente              = serializers.ReadOnlyField()
    porcentaje_completitud      = serializers.ReadOnlyField()
    porcentaje_presupuesto_usado = serializers.ReadOnlyField()

    class Meta:
        model  = AprobacionGAP
        fields = [
            'id',
            'proyecto', 'proyecto_info',
            'solicitado_por', 'solicitado_por_info',
            'validador', 'validador_info',
            'fecha_solicitud', 'comentarios_solicitud',
            'estado', 'fecha_revision', 'observaciones',
            'documentos_adjuntos',
            'items_completados', 'items_totales',
            'presupuesto_ejecutado', 'presupuesto_planificado',
            'gap_original',
            'esta_pendiente', 'fue_aprobado', 'fue_rechazado',
            'dias_pendiente', 'porcentaje_completitud', 'porcentaje_presupuesto_usado',
            'fecha_creacion',
        ]

    def get_proyecto_info(self, obj):
        # Import inline para evitar circular
        from apps.proyectos_remediacion.serializers.proyecto_serializers import ProyectoCierreBrechaDetailSerializer
        return ProyectoCierreBrechaDetailSerializer(obj.proyecto).data

    def get_solicitado_por_info(self, obj):
        return {
            'id':             str(obj.solicitado_por.id),
            'nombre_completo': obj.solicitado_por.nombre_completo,
            'email':          obj.solicitado_por.email,
        }

    def get_validador_info(self, obj):
        return {
            'id':             str(obj.validador.id),
            'nombre_completo': obj.validador.nombre_completo,
            'email':          obj.validador.email,
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
        if not attrs.get('aprobado') and not attrs.get('observaciones'):
            raise serializers.ValidationError({
                'observaciones': 'Las observaciones son obligatorias al rechazar'
            })
        return attrs