# apps/proveedores/serializers.py

from rest_framework import serializers
from .models import Proveedor

class ProveedorSerializer(serializers.ModelSerializer):
    tipo_proveedor_display = serializers.CharField(
        source='get_tipo_proveedor_display',
        read_only=True
    )
    creado_por_nombre = serializers.CharField(
        source='creado_por.nombre_completo',
        read_only=True
    )
    creado_por_email = serializers.CharField(
        source='creado_por.email',
        read_only=True
    )
    
    class Meta:
        model = Proveedor
        fields = [
            'id',
            'razon_social',
            'ruc',
            'tipo_proveedor',
            'tipo_proveedor_display',
            'contacto_email',
            'contacto_telefono',
            'activo',
            'creado_por',
            'creado_por_nombre',
            'creado_por_email',
            'fecha_creacion',
            'fecha_actualizacion',
        ]
        read_only_fields = [
            'id',
            'creado_por',
            'fecha_creacion',
            'fecha_actualizacion'
        ]


class ProveedorCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = [
            'razon_social',
            'ruc',
            'tipo_proveedor',
            'contacto_email',
            'contacto_telefono',
        ]
    
    def create(self, validated_data):
        # Asignar usuario que está creando
        validated_data['creado_por'] = self.context['request'].user
        return super().create(validated_data)


class ProveedorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = [
            'razon_social',
            'ruc',
            'tipo_proveedor',
            'contacto_email',
            'contacto_telefono',
        ]