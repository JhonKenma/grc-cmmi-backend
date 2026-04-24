# apps/dashboard/serializers/auditor.py
from rest_framework import serializers


class KpiAuditorSerializer(serializers.Serializer):
    iq_pendientes_auditoria = serializers.IntegerField()
    iq_en_revision_mia = serializers.IntegerField()
    iq_auditadas_este_mes = serializers.IntegerField()
    iq_vencidas = serializers.IntegerField()
    asignaciones_encuesta_pendientes = serializers.IntegerField()
    gap_promedio_mis_auditorias = serializers.FloatField(allow_null=True)


class AlertaAuditorSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    nivel = serializers.CharField()
    mensaje = serializers.CharField()


class AuditorDashboardSerializer(serializers.Serializer):
    kpis = KpiAuditorSerializer()
    alertas = AlertaAuditorSerializer(many=True)
    charts = serializers.DictField()