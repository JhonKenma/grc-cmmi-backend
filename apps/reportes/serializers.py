# apps/reportes/serializers.py

from rest_framework import serializers


class ReporteGAPEmpresaSerializer(serializers.Serializer):
    """Serializer para validar parámetros de reporte de empresa"""
    empresa_id = serializers.IntegerField(required=True)  # ⭐ CAMBIAR A IntegerField
    dimension_id = serializers.UUIDField(required=False, allow_null=True)


class TopBrechasSerializer(serializers.Serializer):
    """Serializer para validar parámetros de top brechas"""
    empresa_id = serializers.IntegerField(required=True)  # ⭐ CAMBIAR A IntegerField
    limite = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50)