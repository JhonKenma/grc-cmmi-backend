# apps/proveedores/serializers.py

from rest_framework import serializers
from .models import Proveedor
from apps.empresas.models import Empresa  # ⭐ IMPORTAR Empresa

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
    # Información de la empresa
    empresa_nombre = serializers.CharField(
        source='empresa.nombre',
        read_only=True,
        allow_null=True
    )
    es_global = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Proveedor
        fields = [
            'id',
            'empresa',
            'empresa_nombre',
            'es_global',
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
            'empresa',
            'creado_por',
            'fecha_creacion',
            'fecha_actualizacion'
        ]


class ProveedorCreateSerializer(serializers.ModelSerializer):
    # ⭐ CORRECCIÓN: Usar read_only=True inicialmente
    empresa = serializers.PrimaryKeyRelatedField(
        read_only=True,  # ⭐ CAMBIO AQUÍ
        required=False,
        allow_null=True,
        help_text='Solo superadmin puede crear proveedores globales (sin empresa) o asignar a otra empresa'
    )
    
    class Meta:
        model = Proveedor
        fields = [
            'empresa',
            'razon_social',
            'ruc',
            'tipo_proveedor',
            'contacto_email',
            'contacto_telefono',
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        
        if request and request.user:
            # ⭐ CORRECCIÓN: Configurar el campo empresa dinámicamente
            if request.user.rol == 'superadmin':
                # Superadmin puede seleccionar cualquier empresa o dejar vacío
                self.fields['empresa'] = serializers.PrimaryKeyRelatedField(
                    queryset=Empresa.objects.filter(activo=True),
                    required=False,
                    allow_null=True
                )
            # Si no es superadmin, el campo se mantiene read_only
    
    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        
        if user:
            if user.rol == 'superadmin':
                # Superadmin puede crear proveedores globales o para empresas específicas
                # Si no envía empresa, queda como None (global)
                pass
            else:
                # Administradores y otros: DEBEN tener empresa
                if not user.empresa:
                    raise serializers.ValidationError({
                        'empresa': 'Debes tener una empresa asignada para crear proveedores'
                    })
                # Forzar que el proveedor sea de su empresa
                attrs['empresa'] = user.empresa
        
        return attrs
    
    def create(self, validated_data):
        # Asignar usuario que está creando
        validated_data['creado_por'] = self.context['request'].user
        validated_data['activo'] = False
        return super().create(validated_data)


class ProveedorUpdateSerializer(serializers.ModelSerializer):
    # empresa es read_only en actualización (no se puede cambiar)
    empresa = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Proveedor
        fields = [
            'empresa',
            'razon_social',
            'ruc',
            'tipo_proveedor',
            'contacto_email',
            'contacto_telefono',
        ]
    
    def validate_ruc(self, value):
        """
        Validar que el RUC sea único dentro de la misma empresa
        """
        instance = self.instance
        # Verificar si existe otro proveedor con el mismo RUC en la misma empresa
        qs = Proveedor.objects.filter(
            ruc=value,
            empresa=instance.empresa
        ).exclude(pk=instance.pk)
        
        if qs.exists():
            raise serializers.ValidationError(
                'Ya existe un proveedor con este RUC en tu empresa'
            )
        
        return value