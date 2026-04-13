# apps/riesgos/serializers/riesgo.py

from rest_framework import serializers
from django.utils import timezone
from ..models import Riesgo, CategoriaRiesgo
from .categoria import CategoriaRiesgoListSerializer


class RiesgoListSerializer(serializers.ModelSerializer):
    """Serializer compacto para listados."""

    categoria_nombre = serializers.CharField(
        source='categoria.nombre', read_only=True
    )
    categoria_color = serializers.CharField(
        source='categoria.color', read_only=True
    )
    identificado_por_nombre = serializers.CharField(
        source='identificado_por.get_full_name', read_only=True
    )
    dueno_riesgo_nombre = serializers.CharField(
        source='dueno_riesgo.get_full_name', read_only=True
    )
    estado_display = serializers.CharField(
        source='get_estado_display', read_only=True
    )
    clasificacion_display = serializers.CharField(
        source='get_clasificacion_display', read_only=True
    )
    esta_sobre_apetito = serializers.BooleanField(read_only=True)

    class Meta:
        model = Riesgo
        fields = [
            'id', 'codigo', 'nombre',
            'categoria', 'categoria_nombre', 'categoria_color',
            'probabilidad', 'impacto', 'nivel_riesgo',
            'clasificacion', 'clasificacion_display',
            'estado', 'estado_display',
            'fuente', 'ale', 'moneda',
            'dueno_riesgo', 'dueno_riesgo_nombre',
            'identificado_por', 'identificado_por_nombre',
            'fecha_identificacion', 'fecha_revision',
            'esta_sobre_apetito', 'activo',
        ]
        read_only_fields = ['id', 'nivel_riesgo', 'clasificacion']


class RiesgoDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de un riesgo."""

    categoria_detail = CategoriaRiesgoListSerializer(
        source='categoria', read_only=True
    )
    identificado_por_nombre = serializers.CharField(
        source='identificado_por.get_full_name', read_only=True
    )
    dueno_riesgo_nombre = serializers.CharField(
        source='dueno_riesgo.get_full_name', read_only=True
    )
    aprobado_por_nombre = serializers.CharField(
        source='aprobado_por.get_full_name', read_only=True
    )
    estado_display = serializers.CharField(
        source='get_estado_display', read_only=True
    )
    clasificacion_display = serializers.CharField(
        source='get_clasificacion_display', read_only=True
    )
    fuente_display = serializers.CharField(
        source='get_fuente_display', read_only=True
    )
    velocidad_display = serializers.CharField(
        source='get_velocidad_materializacion_display', read_only=True
    )
    esta_sobre_apetito = serializers.BooleanField(read_only=True)
    estado_apetito = serializers.CharField(read_only=True)

    # Planes de tratamiento anidados (resumen)
    total_planes = serializers.SerializerMethodField()
    plan_activo = serializers.SerializerMethodField()

    # KRIs
    total_kris = serializers.SerializerMethodField()
    kris_en_alerta = serializers.SerializerMethodField()

    class Meta:
        model = Riesgo
        fields = [
            'id', 'codigo', 'nombre', 'descripcion',
            'empresa',
            'categoria', 'categoria_detail',
            # Análisis causal
            'causa_raiz', 'consecuencia', 'escenarios',
            'fuente', 'fuente_display',
            'velocidad_materializacion', 'velocidad_display',
            # Evaluación básica
            'probabilidad', 'impacto', 'nivel_riesgo',
            'clasificacion', 'clasificacion_display',
            # Evaluación avanzada
            'nivel_riesgo_inherente', 'nivel_riesgo_residual',
            'apetito_riesgo', 'tolerancia_riesgo',
            'eficacia_controles',
            'esta_sobre_apetito', 'estado_apetito',
            # Cuantitativo
            'sle', 'aro', 'ale', 'moneda',
            # Responsables
            'identificado_por', 'identificado_por_nombre',
            'dueno_riesgo', 'dueno_riesgo_nombre',
            'aprobado_por', 'aprobado_por_nombre',
            # Estado
            'estado', 'estado_display',
            'fecha_identificacion', 'fecha_aprobacion',
            'fecha_revision', 'frecuencia_revision',
            # ISO 31000
            'contexto', 'criterio_riesgo', 'documentacion', 'notas',
            # Relacionados
            'total_planes', 'plan_activo',
            'total_kris', 'kris_en_alerta',
            'activo', 'fecha_creacion', 'fecha_actualizacion',
        ]
        read_only_fields = [
            'id', 'nivel_riesgo', 'clasificacion', 'ale',
            'fecha_aprobacion', 'fecha_creacion', 'fecha_actualizacion',
        ]

    def get_total_planes(self, obj):
        return obj.planes_tratamiento.filter(activo=True).count()

    def get_plan_activo(self, obj):
        plan = obj.planes_tratamiento.filter(
            activo=True,
            estado__in=['no_iniciada', 'en_curso']
        ).first()
        if not plan:
            return None
        return {
            'id': str(plan.id),
            'tipo': plan.get_tipo_display(),
            'estado': plan.get_estado_display(),
            'porcentaje_avance': plan.porcentaje_avance,
            'fecha_fin_plan': plan.fecha_fin_plan,
            'esta_atrasado': plan.esta_atrasado,
        }

    def get_total_kris(self, obj):
        return obj.kris.filter(activo=True).count()

    def get_kris_en_alerta(self, obj):
        return obj.kris.filter(
            activo=True,
            estado_actual__in=['amarillo', 'rojo']
        ).count()


class RiesgoCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear un riesgo nuevo."""

    class Meta:
        model = Riesgo
        fields = [
            'codigo', 'nombre', 'descripcion',
            'categoria', 'fuente', 'velocidad_materializacion',
            'causa_raiz', 'consecuencia', 'escenarios',
            'probabilidad', 'impacto',
            'nivel_riesgo_inherente',
            'apetito_riesgo', 'tolerancia_riesgo',
            'sle', 'aro', 'moneda',
            'dueno_riesgo',
            'fecha_identificacion', 'fecha_revision',
            'contexto', 'criterio_riesgo', 'documentacion', 'notas',
        ]

    def validate_codigo(self, value):
        empresa = self.context['request'].user.empresa
        if Riesgo.objects.filter(empresa=empresa, codigo=value).exists():
            raise serializers.ValidationError(
                f'Ya existe un riesgo con el código {value} en tu empresa.'
            )
        return value.upper()

    def validate_categoria(self, value):
        """La categoría debe ser global o de la misma empresa."""
        user = self.context['request'].user
        if value.empresa is not None and value.empresa != user.empresa:
            raise serializers.ValidationError(
                'Esta categoría no pertenece a tu empresa.'
            )
        return value

    def validate(self, data):
        # Validar que el dueño del riesgo pertenezca a la empresa
        dueno = data.get('dueno_riesgo')
        user = self.context['request'].user
        if dueno and dueno.empresa != user.empresa:
            raise serializers.ValidationError({
                'dueno_riesgo': 'El dueño del riesgo debe pertenecer a tu empresa.'
            })
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['empresa'] = user.empresa
        validated_data['identificado_por'] = user
        validated_data['estado'] = 'borrador'
        return Riesgo.objects.create(**validated_data)


class RiesgoUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar un riesgo existente."""

    class Meta:
        model = Riesgo
        fields = [
            'nombre', 'descripcion',
            'categoria', 'fuente', 'velocidad_materializacion',
            'causa_raiz', 'consecuencia', 'escenarios',
            'probabilidad', 'impacto',
            'nivel_riesgo_inherente', 'nivel_riesgo_residual',
            'apetito_riesgo', 'tolerancia_riesgo', 'eficacia_controles',
            'sle', 'aro', 'moneda',
            'dueno_riesgo',
            'fecha_revision', 'frecuencia_revision',
            'contexto', 'criterio_riesgo', 'documentacion', 'notas',
        ]

    def validate_categoria(self, value):
        user = self.context['request'].user
        if value.empresa is not None and value.empresa != user.empresa:
            raise serializers.ValidationError(
                'Esta categoría no pertenece a tu empresa.'
            )
        return value

    def validate(self, data):
        dueno = data.get('dueno_riesgo')
        user = self.context['request'].user
        if dueno and dueno.empresa != user.empresa:
            raise serializers.ValidationError({
                'dueno_riesgo': 'El dueño del riesgo debe pertenecer a tu empresa.'
            })
        return data


class AprobarRiesgoSerializer(serializers.Serializer):
    """El administrador aprueba un riesgo en revisión."""

    notas_aprobacion = serializers.CharField(
        required=False, allow_blank=True
    )

    def validate(self, data):
        riesgo = self.instance
        if riesgo.estado != 'en_revision':
            raise serializers.ValidationError(
                f'Solo se pueden aprobar riesgos en revisión. '
                f'Estado actual: {riesgo.get_estado_display()}'
            )
        return data

    def save(self):
        riesgo = self.instance
        user = self.context['request'].user
        riesgo.estado = 'aprobado'
        riesgo.aprobado_por = user
        riesgo.fecha_aprobacion = timezone.now()
        if self.validated_data.get('notas_aprobacion'):
            riesgo.notas += f'\n[Aprobación] {self.validated_data["notas_aprobacion"]}'
        riesgo.save()
        return riesgo