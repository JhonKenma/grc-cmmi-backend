# apps/dashboard/serializers/admin.py
from rest_framework import serializers


class PlanInfoSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    esta_activo = serializers.BooleanField()
    dias_restantes = serializers.IntegerField(allow_null=True)
    max_usuarios = serializers.IntegerField()


class EvaluacionEncuestaKpiSerializer(serializers.Serializer):
    activas = serializers.IntegerField()
    completadas = serializers.IntegerField()
    vencidas = serializers.IntegerField()


class EvaluacionIQKpiSerializer(serializers.Serializer):
    pendientes = serializers.IntegerField()
    en_auditoria = serializers.IntegerField()
    auditadas = serializers.IntegerField()


class AsignacionKpiSerializer(serializers.Serializer):
    pendientes = serializers.IntegerField()
    en_progreso = serializers.IntegerField()
    pendiente_auditoria = serializers.IntegerField()
    vencidas = serializers.IntegerField()


class ProveedorKpiSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    riesgo_alto = serializers.IntegerField()


class KpiAdminSerializer(serializers.Serializer):
    plan = PlanInfoSerializer(allow_null=True)
    usuarios_activos = serializers.IntegerField()
    evaluaciones_encuesta = EvaluacionEncuestaKpiSerializer()
    evaluaciones_iq = EvaluacionIQKpiSerializer()
    asignaciones = AsignacionKpiSerializer()
    proveedores = ProveedorKpiSerializer()
    gap_promedio = serializers.FloatField(allow_null=True)


class AlertaAdminSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    nivel = serializers.CharField()
    mensaje = serializers.CharField()
    evaluacion_id = serializers.CharField(required=False, allow_null=True)


class AdminDashboardSerializer(serializers.Serializer):
    kpis = KpiAdminSerializer()
    alertas = AlertaAdminSerializer(many=True)
    charts = serializers.DictField()