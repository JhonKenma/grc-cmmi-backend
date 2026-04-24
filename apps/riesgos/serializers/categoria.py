# apps/riesgos/serializers/categoria.py

from rest_framework import serializers
from ..models import CategoriaRiesgo


class CategoriaRiesgoSerializer(serializers.ModelSerializer):
    es_global = serializers.BooleanField(read_only=True)
    empresa_nombre = serializers.CharField(
        source='empresa.nombre', read_only=True
    )

    class Meta:
        model = CategoriaRiesgo
        fields = [
            'id', 'empresa', 'empresa_nombre', 'nombre', 'descripcion',
            'estandar', 'icono', 'color', 'orden', 'es_global', 'activo',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        request = self.context.get('request')
        user = request.user if request else None

        # Solo superadmin puede crear categorías globales
        empresa = data.get('empresa')
        if empresa is None and user and user.rol != 'superadmin':
            raise serializers.ValidationError({
                'empresa': 'Solo el SuperAdmin puede crear categorías globales.'
            })

        # Admin solo puede crear categorías para su propia empresa
        if user and user.rol == 'administrador':
            if empresa and empresa != user.empresa:
                raise serializers.ValidationError({
                    'empresa': 'Solo puedes crear categorías para tu empresa.'
                })
            if not empresa:
                data['empresa'] = user.empresa

        return data


class CategoriaRiesgoListSerializer(serializers.ModelSerializer):
    es_global = serializers.BooleanField(read_only=True)

    class Meta:
        model = CategoriaRiesgo
        fields = [
            'id', 'nombre', 'descripcion', 'estandar',
            'icono', 'color', 'orden', 'es_global',
        ]