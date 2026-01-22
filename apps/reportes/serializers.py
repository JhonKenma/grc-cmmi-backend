# apps/reportes/serializers.py

from rest_framework import serializers


class ReporteGAPEmpresaSerializer(serializers.Serializer):
    empresa_id = serializers.UUIDField(required=False)  # <-- CAMBIA ESTO
    dimension_id = serializers.UUIDField(required=False, allow_null=True)


class TopBrechasSerializer(serializers.Serializer):
    """Serializer para validar parámetros de top brechas"""
    empresa_id = serializers.IntegerField(required=True)  # ⭐ CAMBIAR A IntegerField
    limite = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50)