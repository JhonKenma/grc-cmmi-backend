# apps/empresas/serializers.py
from rest_framework import serializers
from .models import Empresa, PlanEmpresa


# ─────────────────────────────────────────────
# PlanEmpresaSerializer — debe ir PRIMERO
# porque EmpresaSerializer lo referencia
# ─────────────────────────────────────────────

class PlanEmpresaSerializer(serializers.ModelSerializer):
    esta_activo    = serializers.ReadOnlyField()
    dias_restantes = serializers.ReadOnlyField()
    tipo_display   = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model  = PlanEmpresa
        fields = [
            'id', 'tipo', 'tipo_display',
            'fecha_inicio', 'fecha_expiracion',
            'max_usuarios', 'max_administradores', 'max_auditores',
            'esta_activo', 'dias_restantes',
        ]


# ─────────────────────────────────────────────
# EmpresaSerializer — detalle completo
# ─────────────────────────────────────────────

class EmpresaSerializer(serializers.ModelSerializer):
    total_usuarios  = serializers.ReadOnlyField()
    total_encuestas = serializers.ReadOnlyField()
    pais_display    = serializers.ReadOnlyField()
    tamanio_display = serializers.ReadOnlyField()
    sector_display  = serializers.ReadOnlyField()
    plan            = PlanEmpresaSerializer(read_only=True)

    class Meta:
        model  = Empresa
        fields = [
            'id', 'nombre', 'razon_social', 'ruc',
            'pais', 'pais_otro', 'pais_display',
            'tamanio', 'tamanio_otro', 'tamanio_display',
            'sector', 'sector_otro', 'sector_display',
            'direccion', 'telefono', 'email',
            'timezone', 'logo', 'activo',
            'total_usuarios', 'total_encuestas',
            'plan',
            'fecha_creacion', 'fecha_actualizacion',
        ]
        read_only_fields = ['fecha_creacion', 'fecha_actualizacion']

    def validate(self, data):
        if data.get('pais') == 'OT' and not data.get('pais_otro'):
            raise serializers.ValidationError({'pais_otro': 'Especifica el país'})
        if data.get('tamanio') == 'otro' and not data.get('tamanio_otro'):
            raise serializers.ValidationError({'tamanio_otro': 'Especifica el tamaño'})
        if data.get('sector') == 'otro' and not data.get('sector_otro'):
            raise serializers.ValidationError({'sector_otro': 'Especifica el sector'})
        if data.get('pais') != 'OT':
            data['pais_otro'] = None
        if data.get('tamanio') != 'otro':
            data['tamanio_otro'] = None
        if data.get('sector') != 'otro':
            data['sector_otro'] = None
        return data


# ─────────────────────────────────────────────
# EmpresaListSerializer — para listados
# ─────────────────────────────────────────────

class EmpresaListSerializer(serializers.ModelSerializer):
    total_usuarios = serializers.ReadOnlyField()
    pais_display   = serializers.ReadOnlyField()
    sector_display = serializers.ReadOnlyField()
    plan           = PlanEmpresaSerializer(read_only=True)  # objeto completo

    class Meta:
        model  = Empresa
        fields = [
            'id', 'nombre', 'ruc', 'pais', 'pais_display',
            'sector', 'sector_display', 'total_usuarios', 'activo',
            'plan',
        ]


# ─────────────────────────────────────────────
# EmpresaCreateSerializer — solo para crear
# ─────────────────────────────────────────────

class EmpresaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Empresa
        fields = [
            'nombre', 'razon_social', 'ruc',
            'pais', 'pais_otro',
            'tamanio', 'tamanio_otro',
            'sector', 'sector_otro',
            'direccion', 'telefono', 'email', 'timezone',
        ]

    def validate(self, data):
        if data.get('pais') == 'OT' and not data.get('pais_otro'):
            raise serializers.ValidationError({'pais_otro': 'Especifica el país'})
        if data.get('tamanio') == 'otro' and not data.get('tamanio_otro'):
            raise serializers.ValidationError({'tamanio_otro': 'Especifica el tamaño'})
        if data.get('sector') == 'otro' and not data.get('sector_otro'):
            raise serializers.ValidationError({'sector_otro': 'Especifica el sector'})
        return data

    def validate_ruc(self, value):
        if not value:
            return value
        pais = self.initial_data.get('pais', 'PE')
        if pais == 'PE' and (not value.isdigit() or len(value) != 11):
            raise serializers.ValidationError('El RUC de Perú debe tener 11 dígitos')
        if pais == 'MX' and len(value) not in [12, 13]:
            raise serializers.ValidationError('El RFC de México debe tener 12 o 13 caracteres')
        if pais == 'CO' and not value.replace('-', '').isdigit():
            raise serializers.ValidationError('El NIT de Colombia debe ser numérico')
        return value