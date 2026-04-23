# apps/dashboard/serializers/usuario.py
from rest_framework import serializers


class ProximoVencimientoSerializer(serializers.Serializer):
    id = serializers.CharField()
    fecha_limite = serializers.DateField()
    # nombre dinámico: dimension__nombre o evaluacion__nombre
    # se incluye tal como viene del values() del ORM


class AsignacionEncuestaKpiSerializer(serializers.Serializer):
    pendientes = serializers.IntegerField()
    en_progreso = serializers.IntegerField()
    completadas = serializers.IntegerField()
    vencidas = serializers.IntegerField()
    proxima_vencimiento = serializers.DictField(allow_null=True)


class EvaluacionIQUsuarioKpiSerializer(serializers.Serializer):
    pendientes = serializers.IntegerField()
    completadas = serializers.IntegerField()
    vencidas = serializers.IntegerField()
    proxima_vencimiento = serializers.DictField(allow_null=True)


class KpiUsuarioSerializer(serializers.Serializer):
    asignaciones_encuesta = AsignacionEncuestaKpiSerializer()
    evaluaciones_iq = EvaluacionIQUsuarioKpiSerializer()


class AlertaUsuarioSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    nivel = serializers.CharField()
    mensaje = serializers.CharField()
    asignacion_id = serializers.CharField(required=False, allow_null=True)


class UsuarioDashboardSerializer(serializers.Serializer):
    kpis = KpiUsuarioSerializer()
    alertas = AlertaUsuarioSerializer(many=True)
    charts = serializers.DictField()