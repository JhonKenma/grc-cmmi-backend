# apps/proveedores/serializers.py

from rest_framework import serializers
from .models import Proveedor, TipoProveedor, ClasificacionProveedor
from apps.empresas.models import Empresa


# ============================================================
# SERIALIZERS PARA CATÁLOGOS
# ============================================================

class TipoProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoProveedor
        fields = ['id', 'nombre', 'descripcion', 'orden', 'activo']


class ClasificacionProveedorSerializer(serializers.ModelSerializer):
    codigo_display = serializers.CharField(
        source='get_codigo_display',
        read_only=True
    )
    
    class Meta:
        model = ClasificacionProveedor
        fields = ['id', 'codigo', 'codigo_display', 'nombre', 'descripcion', 'color', 'activo']


# ============================================================
# SERIALIZERS PARA PROVEEDOR
# ============================================================

class ProveedorSerializer(serializers.ModelSerializer):
    # Información de relaciones
    tipo_proveedor_nombre = serializers.CharField(
        source='tipo_proveedor.nombre',
        read_only=True
    )
    clasificacion_nombre = serializers.CharField(
        source='clasificacion.nombre',
        read_only=True,
        allow_null=True
    )
    clasificacion_color = serializers.CharField(
        source='clasificacion.color',
        read_only=True,
        allow_null=True
    )
    empresa_nombre = serializers.CharField(
        source='empresa.nombre',
        read_only=True,
        allow_null=True
    )
    creado_por_nombre = serializers.CharField(
        source='creado_por.nombre_completo',
        read_only=True
    )
    
    # Campos calculados
    es_global = serializers.BooleanField(read_only=True)
    nivel_criticidad = serializers.CharField(read_only=True)
    contrato_vigente = serializers.BooleanField(read_only=True, allow_null=True)
    
    # Displays para choices
    nivel_riesgo_display = serializers.CharField(
        source='get_nivel_riesgo_display',
        read_only=True
    )
    estado_proveedor_display = serializers.CharField(
        source='get_estado_proveedor_display',
        read_only=True
    )
    tipo_contrato_display = serializers.CharField(
        source='get_tipo_contrato_display',
        read_only=True
    )
    
    class Meta:
        model = Proveedor
        fields = [
            # IDs
            'id',
            'empresa',
            'tipo_proveedor',
            'clasificacion',
            'creado_por',
            
            # Información básica
            'razon_social',
            'nombre_comercial',
            
            # Legal y fiscal
            'pais',
            'tipo_documento_fiscal',
            'numero_documento_fiscal',
            'direccion_legal',
            
            # Contacto
            'nombre_contacto_principal',
            'cargo_contacto',
            'email_contacto',
            'telefono_contacto',
            
            # Contractual
            'numero_contrato',
            'fecha_inicio_contrato',
            'fecha_fin_contrato',
            'tipo_contrato',
            'tipo_contrato_display',
            'sla_aplica',
            
            # Estado y clasificación GRC
            'nivel_riesgo',
            'nivel_riesgo_display',
            'proveedor_estrategico',
            'estado_proveedor',
            'estado_proveedor_display',
            'fecha_alta',
            'fecha_baja',
            
            # Cumplimiento
            'requiere_certificaciones',
            'certificaciones',
            'cumple_compliance',
            'ultima_evaluacion_riesgo',
            'proxima_evaluacion_riesgo',
            
            # Observaciones
            'observaciones',
            
            # Campos base
            'activo',
            'fecha_creacion',
            'fecha_actualizacion',
            
            # Campos calculados y relacionados
            'tipo_proveedor_nombre',
            'clasificacion_nombre',
            'clasificacion_color',
            'empresa_nombre',
            'creado_por_nombre',
            'es_global',
            'nivel_criticidad',
            'contrato_vigente',
        ]
        read_only_fields = [
            'id',
            'empresa',
            'creado_por',
            'fecha_alta',
            'fecha_creacion',
            'fecha_actualizacion',
        ]


class ProveedorCreateSerializer(serializers.ModelSerializer):
    empresa = serializers.PrimaryKeyRelatedField(
        read_only=True,
        required=False,
        allow_null=True,
        help_text='Solo superadmin puede crear proveedores globales (sin empresa) o asignar a otra empresa'
    )
    
    class Meta:
        model = Proveedor
        fields = [
            'empresa',
            'tipo_proveedor',
            'clasificacion',
            
            # Información básica
            'razon_social',
            'nombre_comercial',
            
            # Legal y fiscal
            'pais',
            'tipo_documento_fiscal',
            'numero_documento_fiscal',
            'direccion_legal',
            
            # Contacto
            'nombre_contacto_principal',
            'cargo_contacto',
            'email_contacto',
            'telefono_contacto',
            
            # Contractual
            'numero_contrato',
            'fecha_inicio_contrato',
            'fecha_fin_contrato',
            'tipo_contrato',
            'sla_aplica',
            
            # Estado y clasificación GRC
            'nivel_riesgo',
            'proveedor_estrategico',
            
            # Cumplimiento
            'requiere_certificaciones',
            'certificaciones',
            'cumple_compliance',
            
            # Observaciones
            'observaciones',
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        
        if request and request.user:
            if request.user.rol == 'superadmin':
                self.fields['empresa'] = serializers.PrimaryKeyRelatedField(
                    queryset=Empresa.objects.filter(activo=True),
                    required=False,
                    allow_null=True
                )
    
    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        
        if user:
            if user.rol == 'superadmin':
                pass
            else:
                if not user.empresa:
                    raise serializers.ValidationError({
                        'empresa': 'Debes tener una empresa asignada para crear proveedores'
                    })
                attrs['empresa'] = user.empresa
        
        return attrs
    
    def create(self, validated_data):
        validated_data['creado_por'] = self.context['request'].user
        validated_data['estado_proveedor'] = 'activo'
        validated_data['activo'] = False  # Inicia desactivado para aprobación
        return super().create(validated_data)


class ProveedorUpdateSerializer(serializers.ModelSerializer):
    empresa = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Proveedor
        fields = [
            'empresa',
            'tipo_proveedor',
            'clasificacion',
            
            # Información básica
            'razon_social',
            'nombre_comercial',
            
            # Legal y fiscal
            'pais',
            'tipo_documento_fiscal',
            'numero_documento_fiscal',
            'direccion_legal',
            
            # Contacto
            'nombre_contacto_principal',
            'cargo_contacto',
            'email_contacto',
            'telefono_contacto',
            
            # Contractual
            'numero_contrato',
            'fecha_inicio_contrato',
            'fecha_fin_contrato',
            'tipo_contrato',
            'sla_aplica',
            
            # Estado y clasificación GRC
            'nivel_riesgo',
            'proveedor_estrategico',
            'estado_proveedor',
            'fecha_baja',
            
            # Cumplimiento
            'requiere_certificaciones',
            'certificaciones',
            'cumple_compliance',
            'ultima_evaluacion_riesgo',
            'proxima_evaluacion_riesgo',
            
            # Observaciones
            'observaciones',
        ]
    
    def validate_numero_documento_fiscal(self, value):
        """Validar que el documento fiscal sea único dentro de la misma empresa"""
        instance = self.instance
        qs = Proveedor.objects.filter(
            numero_documento_fiscal=value,
            empresa=instance.empresa
        ).exclude(pk=instance.pk)
        
        if qs.exists():
            raise serializers.ValidationError(
                'Ya existe un proveedor con este documento fiscal en tu empresa'
            )
        
        return value