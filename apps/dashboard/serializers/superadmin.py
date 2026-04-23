# apps/dashboard/serializers/superadmin.py
from rest_framework import serializers


class AlertaSuperAdminSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    nivel = serializers.CharField()
    mensaje = serializers.CharField()
    empresa_id = serializers.CharField(required=False, allow_null=True)


class KpiSuperAdminSerializer(serializers.Serializer):
    total_empresas = serializers.IntegerField()
    planes_vencidos = serializers.IntegerField()
    planes_por_vencer_30d = serializers.IntegerField()
    total_usuarios = serializers.IntegerField()
    total_proveedores = serializers.IntegerField()
    evaluaciones_encuesta_total = serializers.IntegerField()
    evaluaciones_encuesta_vencidas = serializers.IntegerField()
    evaluaciones_iq_total = serializers.IntegerField()
    evaluaciones_iq_completadas = serializers.IntegerField()


class ChartItemSerializer(serializers.Serializer):
    """Genérico para cualquier gráfico clave/valor."""
    # Los campos extra se pasan como additional_fields
    def to_representation(self, instance):
        return instance  # ya viene como dict desde el service


class SuperAdminDashboardSerializer(serializers.Serializer):
    kpis = KpiSuperAdminSerializer()
    alertas = AlertaSuperAdminSerializer(many=True)
    charts = serializers.DictField()