# apps/riesgos/serializers/tratamiento.py

from rest_framework import serializers
from django.utils import timezone
from ..models import PlanTratamiento, KRI, RegistroMonitoreo


class PlanTratamientoListSerializer(serializers.ModelSerializer):
    responsable_nombre = serializers.CharField(
        source='responsable_accion.get_full_name', read_only=True
    )
    tipo_display = serializers.CharField(
        source='get_tipo_display', read_only=True
    )
    estado_display = serializers.CharField(
        source='get_estado_display', read_only=True
    )
    prioridad_display = serializers.CharField(
        source='get_prioridad_display', read_only=True
    )
    esta_atrasado = serializers.BooleanField(read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = PlanTratamiento
        fields = [
            'id', 'riesgo', 'tipo', 'tipo_display',
            'descripcion_accion', 'estado', 'estado_display',
            'prioridad', 'prioridad_display',
            'responsable_accion', 'responsable_nombre',
            'fecha_inicio', 'fecha_fin_plan',
            'porcentaje_avance', 'costo_estimado', 'moneda',
            'esta_atrasado', 'dias_restantes',
        ]
        read_only_fields = ['id']


class PlanTratamientoDetailSerializer(serializers.ModelSerializer):
    responsable_nombre = serializers.CharField(
        source='responsable_accion.get_full_name', read_only=True
    )
    aprobado_por_nombre = serializers.CharField(
        source='aprobado_por.get_full_name', read_only=True
    )
    tipo_display = serializers.CharField(
        source='get_tipo_display', read_only=True
    )
    estado_display = serializers.CharField(
        source='get_estado_display', read_only=True
    )
    esta_atrasado = serializers.BooleanField(read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = PlanTratamiento
        fields = '__all__'
        read_only_fields = [
            'id', 'fecha_fin_real', 'fecha_aprobacion',
            'fecha_creacion', 'fecha_actualizacion',
        ]


class PlanTratamientoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanTratamiento
        fields = [
            'riesgo', 'tipo', 'descripcion_accion', 'objetivos',
            'controles_propuestos', 'responsable_accion', 'prioridad',
            'fecha_inicio', 'fecha_fin_plan',
            'recursos_requeridos', 'costo_estimado', 'moneda',
            'eficacia_esperada', 'nivel_riesgo_objetivo',
        ]

    def validate_riesgo(self, value):
        user = self.context['request'].user
        if value.empresa != user.empresa:
            raise serializers.ValidationError(
                'No puedes crear un plan para un riesgo de otra empresa.'
            )
        if value.estado not in ['aprobado', 'en_tratamiento']:
            raise serializers.ValidationError(
                f'El riesgo debe estar aprobado para crear un plan. '
                f'Estado actual: {value.get_estado_display()}'
            )
        return value

    def validate(self, data):
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin_plan')
        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise serializers.ValidationError({
                'fecha_fin_plan': 'La fecha de fin debe ser posterior a la de inicio.'
            })

        responsable = data.get('responsable_accion')
        user = self.context['request'].user
        if responsable and responsable.empresa != user.empresa:
            raise serializers.ValidationError({
                'responsable_accion': 'El responsable debe pertenecer a tu empresa.'
            })
        return data

    def create(self, validated_data):
        plan = PlanTratamiento.objects.create(**validated_data)
        # Actualizar estado del riesgo a en_tratamiento
        riesgo = plan.riesgo
        if riesgo.estado == 'aprobado':
            riesgo.estado = 'en_tratamiento'
            riesgo.save()
        return plan


class ActualizarAvancePlanSerializer(serializers.Serializer):
    """Actualiza el avance y estado de un plan de tratamiento."""

    porcentaje_avance = serializers.IntegerField(min_value=0, max_value=100)
    estado = serializers.ChoiceField(
        choices=['no_iniciada', 'en_curso', 'completada', 'atrasada', 'cancelada'],
        required=False
    )
    notas_avance = serializers.CharField(required=False, allow_blank=True)
    costo_real = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False
    )

    def save(self):
        plan = self.instance
        plan.porcentaje_avance = self.validated_data['porcentaje_avance']

        if 'estado' in self.validated_data:
            plan.estado = self.validated_data['estado']

        if 'notas_avance' in self.validated_data:
            plan.notas_avance = self.validated_data['notas_avance']

        if 'costo_real' in self.validated_data:
            plan.costo_real = self.validated_data['costo_real']

        plan.save()
        return plan


# ─────────────────────────────────────────────────────────────────────────────
# KRI
# ─────────────────────────────────────────────────────────────────────────────

class KRIListSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(
        source='get_estado_actual_display', read_only=True
    )
    responsable_nombre = serializers.CharField(
        source='responsable_medicion.get_full_name', read_only=True
    )

    class Meta:
        model = KRI
        fields = [
            'id', 'riesgo', 'codigo', 'nombre',
            'tipo_metrica', 'unidad_medida',
            'umbral_amarillo', 'umbral_rojo',
            'valor_actual', 'estado_actual', 'estado_display',
            'fecha_ultima_medicion', 'frecuencia_medicion',
            'responsable_medicion', 'responsable_nombre',
        ]


class KRICreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KRI
        fields = [
            'riesgo', 'codigo', 'nombre', 'descripcion',
            'tipo_metrica', 'unidad_medida',
            'umbral_amarillo', 'umbral_rojo',
            'frecuencia_medicion', 'responsable_medicion',
            'notificar_al_superar',
        ]

    def validate_riesgo(self, value):
        user = self.context['request'].user
        if value.empresa != user.empresa:
            raise serializers.ValidationError(
                'No puedes crear un KRI para un riesgo de otra empresa.'
            )
        return value

    def validate(self, data):
        if float(data['umbral_amarillo']) >= float(data['umbral_rojo']):
            raise serializers.ValidationError({
                'umbral_rojo': 'El umbral rojo debe ser mayor que el umbral amarillo.'
            })
        return data


class RegistrarMedicionKRISerializer(serializers.Serializer):
    """Registra una nueva medición para un KRI."""

    valor = serializers.DecimalField(max_digits=15, decimal_places=2)
    observaciones = serializers.CharField(required=False, allow_blank=True)

    def save(self):
        kri = self.instance
        nuevo_estado = kri.actualizar_valor(self.validated_data['valor'])
        return kri, nuevo_estado


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRO MONITOREO
# ─────────────────────────────────────────────────────────────────────────────

class RegistroMonitoreoSerializer(serializers.ModelSerializer):
    revisado_por_nombre = serializers.CharField(
        source='revisado_por.get_full_name', read_only=True
    )
    resultado_display = serializers.CharField(
        source='get_resultado_display', read_only=True
    )

    class Meta:
        model = RegistroMonitoreo
        fields = [
            'id', 'riesgo',
            'probabilidad_revisada', 'impacto_revisado', 'nivel_riesgo_revisado',
            'resultado', 'resultado_display',
            'observaciones', 'acciones_adicionales',
            'revisado_por', 'revisado_por_nombre',
            'fecha_revision', 'proxima_revision',
            'fecha_creacion',
        ]
        read_only_fields = ['id', 'fecha_creacion']

    def validate_riesgo(self, value):
        user = self.context['request'].user
        if value.empresa != user.empresa:
            raise serializers.ValidationError(
                'No puedes registrar monitoreo para un riesgo de otra empresa.'
            )
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['revisado_por'] = user

        registro = RegistroMonitoreo.objects.create(**validated_data)

        # Actualizar probabilidad/impacto del riesgo si se revisaron
        riesgo = registro.riesgo
        actualizar = False
        if registro.probabilidad_revisada:
            riesgo.probabilidad = registro.probabilidad_revisada
            actualizar = True
        if registro.impacto_revisado:
            riesgo.impacto = registro.impacto_revisado
            actualizar = True
        if registro.proxima_revision:
            riesgo.fecha_revision = registro.proxima_revision
            actualizar = True
        if actualizar:
            riesgo.save()

        return registro