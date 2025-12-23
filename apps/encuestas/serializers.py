# apps/encuestas/serializers.py - VERSIÓN SIMPLIFICADA SOLO EDICIÓN

from rest_framework import serializers
from .models import (
    Encuesta, Dimension, Pregunta, 
    NivelReferencia, ConfigNivelDeseado
)
from apps.empresas.serializers import EmpresaSerializer


# =============================================================================
# SERIALIZERS PARA NIVELES DE REFERENCIA
# =============================================================================

class NivelReferenciaSerializer(serializers.ModelSerializer):
    """Serializer completo para niveles de referencia"""
    
    class Meta:
        model = NivelReferencia
        fields = [
            'id', 'pregunta', 'numero', 'descripcion', 'recomendaciones',
            'activo', 'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['id', 'pregunta', 'numero', 'fecha_creacion', 'fecha_actualizacion']
    
    def validate_descripcion(self, value):
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                'La descripción debe tener al menos 5 caracteres'
            )
        return value


# =============================================================================
# SERIALIZERS PARA PREGUNTAS
# =============================================================================

class PreguntaSerializer(serializers.ModelSerializer):
    """Serializer completo para preguntas con niveles"""
    niveles_referencia = NivelReferenciaSerializer(many=True, read_only=True)
    dimension_nombre = serializers.CharField(source='dimension.nombre', read_only=True)
    dimension_codigo = serializers.CharField(source='dimension.codigo', read_only=True)
    total_niveles = serializers.SerializerMethodField()
    
    class Meta:
        model = Pregunta
        fields = [
            'id', 'dimension', 'dimension_nombre', 'dimension_codigo',
            'codigo', 'titulo', 'texto', 'peso', 'obligatoria', 'orden', 
            'activo', 'total_niveles', 'niveles_referencia', 
            'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['id', 'dimension', 'fecha_creacion', 'fecha_actualizacion']
    
    def get_total_niveles(self, obj):
        """Retorna cantidad de niveles de referencia creados"""
        return obj.niveles_referencia.filter(activo=True).count()
    
    def validate_peso(self, value):
        """Validar que el peso sea positivo"""
        if value <= 0:
            raise serializers.ValidationError(
                'El peso debe ser mayor a 0'
            )
        return value
    
    def validate_titulo(self, value):
        """Validar que el título no esté vacío"""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                'El título debe tener al menos 5 caracteres'
            )
        return value
    
    def validate_texto(self, value):
        """Validar que el texto no esté vacío"""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError(
                'El texto de la pregunta debe tener al menos 10 caracteres'
            )
        return value
    
    def validate(self, attrs):
        """Validar que no exista duplicado código + dimensión"""
        codigo = attrs.get('codigo')
        
        # Solo validar si se está intentando cambiar el código
        if codigo and self.instance and codigo != self.instance.codigo:
            dimension = self.instance.dimension
            if Pregunta.objects.filter(dimension=dimension, codigo=codigo).exists():
                raise serializers.ValidationError({
                    'codigo': f'Ya existe una pregunta con código {codigo} en esta dimensión'
                })
        
        return attrs


class PreguntaListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de preguntas"""
    total_niveles = serializers.SerializerMethodField()
    
    class Meta:
        model = Pregunta
        fields = [
            'id', 'codigo', 'titulo', 'peso', 'obligatoria', 
            'orden', 'total_niveles', 'activo'
        ]
    
    def get_total_niveles(self, obj):
        return obj.niveles_referencia.filter(activo=True).count()

# ⭐ NUEVO: Serializer específico para preguntas en respuestas
class PreguntaParaRespuestasSerializer(serializers.ModelSerializer):
    """
    Serializer de pregunta para el módulo de respuestas
    Incluye TODOS los campos necesarios para mostrar la pregunta
    """
    dimension_nombre = serializers.CharField(source='dimension.nombre', read_only=True)
    dimension_codigo = serializers.CharField(source='dimension.codigo', read_only=True)
    
    class Meta:
        model = Pregunta
        fields = [
            'id', 'codigo', 'titulo', 'texto',  # ⭐ INCLUYE texto
            'dimension', 'dimension_nombre', 'dimension_codigo',
            'peso', 'obligatoria', 'orden', 'activo'
        ]
        read_only_fields = ['id']


# ⭐ NUEVO: Serializer para dimensión con preguntas incluidas
class DimensionConPreguntasSerializer(serializers.ModelSerializer):
    """Serializer de dimensión que incluye sus preguntas"""
    
    preguntas = PreguntaParaRespuestasSerializer(many=True, read_only=True)  # ⭐ USAR EL NUEVO
    encuesta_nombre = serializers.CharField(source='encuesta.nombre', read_only=True)
    total_preguntas = serializers.SerializerMethodField()
    
    class Meta:
        model = Dimension
        fields = [
            'id', 'codigo', 'nombre', 'descripcion',
            'encuesta', 'encuesta_nombre', 'orden',
            'total_preguntas', 'preguntas', 'activo'
        ]
    
    def get_total_preguntas(self, obj):
        return obj.preguntas.filter(activo=True).count()
# =============================================================================
# SERIALIZERS PARA DIMENSIONES
# =============================================================================

class DimensionSerializer(serializers.ModelSerializer):
    """Serializer completo para dimensiones con preguntas"""
    preguntas = PreguntaSerializer(many=True, read_only=True)  # ⭐ CAMBIAR A PreguntaSerializer completo
    encuesta_nombre = serializers.CharField(source='encuesta.nombre', read_only=True)
    total_preguntas = serializers.ReadOnlyField()
    
    class Meta:
        model = Dimension
        fields = [
            'id', 'encuesta', 'encuesta_nombre', 'codigo', 'nombre', 
            'descripcion', 'orden', 'total_preguntas', 'activo',
            'preguntas', 'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['id', 'encuesta', 'fecha_creacion', 'fecha_actualizacion']
    
    def validate_nombre(self, value):
        """Validar que el nombre no esté vacío"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                'El nombre debe tener al menos 3 caracteres'
            )
        return value
    
    def validate(self, attrs):
        """Validar que no exista duplicado código + encuesta"""
        codigo = attrs.get('codigo')
        
        # Solo validar si se está intentando cambiar el código
        if codigo and self.instance and codigo != self.instance.codigo:
            encuesta = self.instance.encuesta
            if Dimension.objects.filter(encuesta=encuesta, codigo=codigo).exists():
                raise serializers.ValidationError({
                    'codigo': f'Ya existe una dimensión con código {codigo} en esta encuesta'
                })
        
        return attrs


class DimensionListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de dimensiones"""
    total_preguntas = serializers.ReadOnlyField()
    
    class Meta:
        model = Dimension
        fields = [
            'id', 'codigo', 'nombre', 'orden', 
            'total_preguntas', 'activo'
        ]


# =============================================================================
# SERIALIZERS PARA ENCUESTAS
# =============================================================================

class EncuestaSerializer(serializers.ModelSerializer):
    """Serializer completo para encuestas con dimensiones"""
    dimensiones = DimensionSerializer(many=True, read_only=True)
    total_dimensiones = serializers.ReadOnlyField()
    total_preguntas = serializers.ReadOnlyField()
    
    class Meta:
        model = Encuesta
        fields = [
            'id', 'nombre', 'descripcion', 'version', 'es_plantilla',
            'total_dimensiones', 'total_preguntas', 'activo',
            'dimensiones', 'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'fecha_actualizacion', 'es_plantilla']
    
    def validate_nombre(self, value):
        """Validar que el nombre no esté vacío"""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                'El nombre debe tener al menos 5 caracteres'
            )
        return value


class EncuestaListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de encuestas"""
    total_dimensiones = serializers.ReadOnlyField()
    total_preguntas = serializers.ReadOnlyField()
    
    class Meta:
        model = Encuesta
        fields = [
            'id', 'nombre', 'version', 'es_plantilla',
            'total_dimensiones', 'total_preguntas', 'activo',
            'fecha_creacion', 'fecha_actualizacion'
        ]


# =============================================================================
# SERIALIZER PARA CARGA DE EXCEL (Ya existente, mantener)
# =============================================================================

class CargaExcelSerializer(serializers.Serializer):
    """Serializer para validar carga de Excel"""
    archivo = serializers.FileField(
        required=True,
        help_text='Archivo Excel con estructura de encuesta'
    )
    nombre_encuesta = serializers.CharField(
        required=True,
        max_length=300,
        help_text='Nombre de la encuesta'
    )
    version = serializers.CharField(
        required=False,
        default='1.0',
        max_length=20,
        help_text='Versión de la encuesta'
    )
    descripcion = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Descripción de la encuesta'
    )
    
    def validate_archivo(self, value):
        """Validar que sea un archivo Excel válido"""
        import os
        ext = os.path.splitext(value.name)[1].lower()
        
        if ext not in ['.xlsx', '.xls']:
            raise serializers.ValidationError(
                'El archivo debe ser formato Excel (.xlsx o .xls)'
            )
        
        # Validar tamaño (máximo 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                'El archivo no puede superar los 5MB'
            )
        
        return value


# =============================================================================
# SERIALIZER PARA CONFIGURACIÓN DE NIVELES DESEADOS (Ya existente, mantener)
# =============================================================================

class ConfigNivelDeseadoSerializer(serializers.ModelSerializer):
    """Serializer para configuración de niveles deseados"""
    dimension_info = DimensionListSerializer(source='dimension', read_only=True)
    empresa_info = EmpresaSerializer(source='empresa', read_only=True)
    configurado_por_nombre = serializers.CharField(
        source='configurado_por.nombre_completo',
        read_only=True
    )
    
    class Meta:
        model = ConfigNivelDeseado
        fields = [
            'id', 'dimension', 'dimension_info', 'empresa', 'empresa_info',
            'nivel_deseado', 'configurado_por', 'configurado_por_nombre',
            'motivo_cambio', 'activo', 'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['fecha_creacion', 'fecha_actualizacion', 'configurado_por']
        # ⭐ AGREGAR ESTA SECCIÓN
        extra_kwargs = {
            'dimension': {'required': False},
            'empresa': {'required': False},
        }
    
    def validate(self, attrs):
        """Validar que el usuario solo configure para su empresa"""
        user = self.context['request'].user
        
        # ⭐ AGREGAR ESTA VALIDACIÓN AL INICIO
        if self.instance is None:  # Creación
            # En creación SÍ se requieren dimension y empresa
            if 'dimension' not in attrs:
                raise serializers.ValidationError({'dimension': 'Este campo es requerido al crear.'})
            if 'empresa' not in attrs:
                raise serializers.ValidationError({'empresa': 'Este campo es requerido al crear.'})
        else:  # Actualización
            # En actualización NO se permite modificar dimension ni empresa
            if 'dimension' in attrs:
                raise serializers.ValidationError({'dimension': 'No se puede modificar la dimensión.'})
            if 'empresa' in attrs:
                raise serializers.ValidationError({'empresa': 'No se puede modificar la empresa.'})
        
        # ⭐ CONTINUAR CON TU VALIDACIÓN EXISTENTE
        empresa = attrs.get('empresa', getattr(self.instance, 'empresa', None) if self.instance else None)
        
        # SuperAdmin puede configurar para cualquier empresa
        if user.rol == 'superadmin':
            return attrs
        
        # Administrador solo para su empresa
        if user.rol == 'administrador':
            if empresa != user.empresa:
                raise serializers.ValidationError({
                    'empresa': 'Solo puedes configurar niveles para tu propia empresa'
                })
        else:
            raise serializers.ValidationError(
                'No tienes permisos para configurar niveles deseados'
            )
        
        return attrs
    
    def create(self, validated_data):
        # Asignar usuario que configura
        validated_data['configurado_por'] = self.context['request'].user
        return super().create(validated_data)
    
    # ⭐ AGREGAR ESTE MÉTODO
    def update(self, instance, validated_data):
        # Actualizar usuario que configura
        validated_data['configurado_por'] = self.context['request'].user
        return super().update(instance, validated_data)
    
# =============================================================================
# SERIALIZERS PARA ADMINISTRADORES (SIN NIVELES NI RECOMENDACIONES)
# =============================================================================

class PreguntaAdminSerializer(serializers.ModelSerializer):
    """
    Serializer de pregunta PARA ADMINISTRADORES
    NO incluye niveles de referencia ni recomendaciones
    """
    dimension_nombre = serializers.CharField(source='dimension.nombre', read_only=True)
    dimension_codigo = serializers.CharField(source='dimension.codigo', read_only=True)
    
    class Meta:
        model = Pregunta
        fields = [
            'id', 'dimension', 'dimension_nombre', 'dimension_codigo',
            'codigo', 'titulo', 'texto', 'peso', 'obligatoria', 'orden', 
            'activo', 'fecha_creacion'
        ]


class DimensionAdminSerializer(serializers.ModelSerializer):
    """
    Serializer de dimensión PARA ADMINISTRADORES
    Incluye preguntas pero SIN niveles de referencia
    """
    preguntas = PreguntaAdminSerializer(many=True, read_only=True)
    encuesta_nombre = serializers.CharField(source='encuesta.nombre', read_only=True)
    total_preguntas = serializers.ReadOnlyField()
    
    class Meta:
        model = Dimension
        fields = [
            'id', 'encuesta', 'encuesta_nombre', 'codigo', 'nombre', 
            'descripcion', 'orden', 'total_preguntas', 'activo',
            'preguntas', 'fecha_creacion'
        ]


class EncuestaAdminSerializer(serializers.ModelSerializer):
    """
    Serializer de encuesta PARA ADMINISTRADORES
    Incluye dimensiones y preguntas pero SIN niveles ni recomendaciones
    """
    dimensiones = DimensionAdminSerializer(many=True, read_only=True)
    total_dimensiones = serializers.ReadOnlyField()
    total_preguntas = serializers.ReadOnlyField()
    
    class Meta:
        model = Encuesta
        fields = [
            'id', 'nombre', 'descripcion', 'version',
            'total_dimensiones', 'total_preguntas', 'activo',
            'dimensiones', 'fecha_creacion'
        ]
