# apps/empresas/serializers.py
from rest_framework import serializers
from .models import Empresa

class EmpresaSerializer(serializers.ModelSerializer):
    total_usuarios = serializers.ReadOnlyField()
    total_encuestas = serializers.ReadOnlyField()
    pais_display = serializers.ReadOnlyField()
    tamanio_display = serializers.ReadOnlyField()
    sector_display = serializers.ReadOnlyField()
    
    class Meta:
        model = Empresa
        fields = [
            'id', 'nombre', 'razon_social', 'ruc', 
            'pais', 'pais_otro', 'pais_display',
            'tamanio', 'tamanio_otro', 'tamanio_display',
            'sector', 'sector_otro', 'sector_display',
            'direccion', 'telefono', 'email', 
            'timezone', 'logo', 'activo',
            'total_usuarios', 'total_encuestas',
            'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['fecha_creacion', 'fecha_actualizacion']
    
    def validate(self, data):
        """
        Validar que si seleccionan 'Otro', completen el campo correspondiente
        """
        # Validar país
        if data.get('pais') == 'OT' and not data.get('pais_otro'):
            raise serializers.ValidationError({
                'pais_otro': 'Debe especificar el país cuando selecciona "Otro"'
            })
        
        # Validar tamaño
        if data.get('tamanio') == 'otro' and not data.get('tamanio_otro'):
            raise serializers.ValidationError({
                'tamanio_otro': 'Debe especificar el tamaño cuando selecciona "Otro"'
            })
        
        # Validar sector
        if data.get('sector') == 'otro' and not data.get('sector_otro'):
            raise serializers.ValidationError({
                'sector_otro': 'Debe especificar el sector cuando selecciona "Otro"'
            })
        
        # Limpiar campos "otro" si no se seleccionó "otro"
        if data.get('pais') != 'OT':
            data['pais_otro'] = None
        
        if data.get('tamanio') != 'otro':
            data['tamanio_otro'] = None
        
        if data.get('sector') != 'otro':
            data['sector_otro'] = None
        
        return data

class EmpresaListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    total_usuarios = serializers.ReadOnlyField()
    pais_display = serializers.ReadOnlyField()
    sector_display = serializers.ReadOnlyField()
    
    class Meta:
        model = Empresa
        fields = [
            'id', 'nombre', 'ruc', 'pais', 'pais_display', 
            'sector', 'sector_display', 'total_usuarios', 'activo'
        ]

class EmpresaCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear empresa con validaciones"""
    
    class Meta:
        model = Empresa
        fields = [
            'nombre', 'razon_social', 'ruc', 
            'pais', 'pais_otro',
            'tamanio', 'tamanio_otro',
            'sector', 'sector_otro',
            'direccion', 'telefono', 'email', 'timezone'
        ]
    
    def validate(self, data):
        """Validaciones personalizadas"""
        # Validar país
        if data.get('pais') == 'OT' and not data.get('pais_otro'):
            raise serializers.ValidationError({
                'pais_otro': 'Debe especificar el país cuando selecciona "Otro"'
            })
        
        # Validar tamaño
        if data.get('tamanio') == 'otro' and not data.get('tamanio_otro'):
            raise serializers.ValidationError({
                'tamanio_otro': 'Debe especificar el tamaño cuando selecciona "Otro"'
            })
        
        # Validar sector
        if data.get('sector') == 'otro' and not data.get('sector_otro'):
            raise serializers.ValidationError({
                'sector_otro': 'Debe especificar el sector cuando selecciona "Otro"'
            })
        
        return data
    
    def validate_ruc(self, value):
        """Validar RUC según el país"""
        if not value:
            return value
        
        pais = self.initial_data.get('pais', 'PE')
        
        # Validaciones específicas por país
        if pais == 'PE':  # Perú - RUC 11 dígitos
            if not value.isdigit() or len(value) != 11:
                raise serializers.ValidationError(
                    'El RUC de Perú debe tener 11 dígitos'
                )
        elif pais == 'MX':  # México - RFC 12-13 caracteres
            if len(value) not in [12, 13]:
                raise serializers.ValidationError(
                    'El RFC de México debe tener 12 o 13 caracteres'
                )
        elif pais == 'CO':  # Colombia - NIT 9-10 dígitos
            if not value.replace('-', '').isdigit():
                raise serializers.ValidationError(
                    'El NIT de Colombia debe ser numérico'
                )
        # Si es "Otro" país, permitir formato libre
        
        return value