# apps/evaluaciones/serializers.py
"""
Serializers para Sistema de Evaluaciones Inteligentes
"""

from rest_framework import serializers
from .models import (
    Framework,
    PreguntaEvaluacion,
    EvidenciaRequerida,
    RelacionFramework,
    Evaluacion,
    EvaluacionPregunta,
    EmpresaFramework, 
    RespuestaEvaluacion,
    NotaEvidencia,
    ComentarioEvaluacion
)


# ============================================================================
# SERIALIZERS BASE - FRAMEWORKS Y PREGUNTAS
# ============================================================================

class FrameworkSerializer(serializers.ModelSerializer):
    """Serializer para Framework"""
    
    total_preguntas = serializers.SerializerMethodField()
    
    class Meta:
        model = Framework
        fields = [
            'id',
            'codigo',
            'nombre',
            'descripcion',
            'version',
            'activo',
            'fecha_creacion',
            'total_preguntas'
        ]
        read_only_fields = ['id', 'fecha_creacion']
    
    def get_total_preguntas(self, obj):
        """Calcula total de preguntas del framework"""
        return obj.preguntas.filter(activo=True).count()


class EvidenciaRequeridaSerializer(serializers.ModelSerializer):
    """Serializer para Evidencia Requerida"""
    
    class Meta:
        model = EvidenciaRequerida
        fields = [
            'id',
            'pregunta',
            'descripcion',
            'orden'
        ]
        read_only_fields = ['id']


class RelacionFrameworkSerializer(serializers.ModelSerializer):
    """Serializer para Relación entre Frameworks"""
    
    framework_destino_nombre = serializers.CharField(
        source='framework_destino.nombre',
        read_only=True
    )
    framework_destino_codigo = serializers.CharField(
        source='framework_destino.codigo',
        read_only=True
    )
    
    class Meta:
        model = RelacionFramework
        fields = [
            'id',
            'framework_destino',
            'framework_destino_codigo',
            'framework_destino_nombre',
            'referencia_textual',
            'codigo_control_referenciado',
            'porcentaje_cobertura'
        ]
        read_only_fields = ['id']


class PreguntaEvaluacionListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de preguntas"""
    
    framework_nombre = serializers.CharField(
        source='framework.nombre',
        read_only=True
    )
    framework_codigo = serializers.CharField(
        source='framework.codigo',
        read_only=True
    )
    nivel_madurez_display = serializers.CharField(
        source='get_nivel_madurez_display',
        read_only=True
    )
    
    class Meta:
        model = PreguntaEvaluacion
        fields = [
            'id',
            'correlativo',
            'framework',
            'framework_codigo',
            'framework_nombre',
            'codigo_control',
            'seccion_general',
            'nombre_control',
            'pregunta',
            'nivel_madurez',
            'nivel_madurez_display',
            'activo'
        ]
        read_only_fields = ['id']


class PreguntaEvaluacionDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para pregunta individual"""
    
    framework_nombre = serializers.CharField(
        source='framework.nombre',
        read_only=True
    )
    framework_codigo = serializers.CharField(
        source='framework.codigo',
        read_only=True
    )
    evidencias_requeridas = EvidenciaRequeridaSerializer(
        many=True,
        read_only=True
    )
    relaciones_frameworks = RelacionFrameworkSerializer(
        many=True,
        read_only=True
    )
    nivel_madurez_display = serializers.CharField(
        source='get_nivel_madurez_display',
        read_only=True
    )
    
    class Meta:
        model = PreguntaEvaluacion
        fields = [
            'id',
            'correlativo',
            'framework',
            'framework_codigo',
            'framework_nombre',
            'framework_base_nombre',
            'codigo_control',
            'seccion_general',
            'nombre_control',
            'tags',
            'frameworks_referenciales',
            'objetivo_evaluacion',
            'pregunta',
            'nivel_madurez',
            'nivel_madurez_display',
            'activo',
            'fecha_creacion',
            'evidencias_requeridas',
            'relaciones_frameworks'
        ]
        read_only_fields = ['id', 'fecha_creacion']


# ============================================================================
# SERIALIZERS DE EVALUACIÓN
# ============================================================================

class EvaluacionListSerializer(serializers.ModelSerializer):
    """Serializer para listado de evaluaciones"""
    
    frameworks_nombres = serializers.SerializerMethodField()
    creado_por_nombre = serializers.CharField(
        source='creado_por.get_full_name',
        read_only=True
    )
    empresa_nombre = serializers.CharField(
        source='empresa.nombre',
        read_only=True
    )
    nivel_deseado_display = serializers.CharField(
        source='get_nivel_deseado_display',
        read_only=True
    )
    total_preguntas = serializers.IntegerField(read_only=True)
    puede_asignar = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Evaluacion
        fields = [
            'id',
            'empresa',
            'empresa_nombre',
            'nombre',
            'frameworks_nombres',
            'estado',
            'nivel_deseado',
            'nivel_deseado_display',
            'creado_por_nombre',
            'usar_todas_preguntas',
            'total_preguntas',
            'puede_asignar',
            'fecha_creacion'
        ]
        read_only_fields = ['id', 'empresa', 'fecha_creacion']
    
    def get_frameworks_nombres(self, obj):
        """Obtiene nombres de los frameworks concatenados"""
        return ", ".join([fw.codigo for fw in obj.frameworks.all()])


class EvaluacionDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para evaluación"""
    
    frameworks_detail = FrameworkSerializer(
        source='frameworks',
        many=True,
        read_only=True
    )
    creado_por_nombre = serializers.CharField(
        source='creado_por.get_full_name',
        read_only=True
    )
    empresa_nombre = serializers.CharField(
        source='empresa.nombre',
        read_only=True
    )
    nivel_deseado_display = serializers.CharField(
        source='get_nivel_deseado_display',
        read_only=True
    )
    total_preguntas = serializers.SerializerMethodField()
    puede_asignar = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Evaluacion
        fields = [
            'id',
            'empresa',
            'empresa_nombre',
            'frameworks',
            'frameworks_detail',
            'nombre',
            'descripcion',
            'estado',
            'nivel_deseado',
            'nivel_deseado_display',
            'creado_por',
            'creado_por_nombre',
            'usar_todas_preguntas',
            'usar_respuestas_compartidas',
            'fecha_creacion',
            'fecha_actualizacion',
            'total_preguntas',
            'puede_asignar',
        ]
        read_only_fields = ['id', 'empresa', 'fecha_creacion', 'fecha_actualizacion']
    
    def get_total_preguntas(self, obj):
        """Calcula el total de preguntas de la evaluación"""
        if obj.usar_todas_preguntas:
            # Si usa todas las preguntas, contar de los frameworks
            return obj.get_preguntas_a_responder().count()
        else:
            # Si usa selección manual, contar las seleccionadas
            return obj.preguntas_seleccionadas.count()


# ============================================================================
# SERIALIZERS DE EMPRESA FRAMEWORK
# ============================================================================

class EmpresaFrameworkSerializer(serializers.ModelSerializer):
    """
    Serializer para asignación de frameworks a empresas.
    Usado por el SuperAdmin para ver y gestionar qué frameworks
    tiene disponibles cada empresa.
    """

    framework_codigo = serializers.CharField(source='framework.codigo', read_only=True)
    framework_nombre = serializers.CharField(source='framework.nombre', read_only=True)
    framework_version = serializers.CharField(source='framework.version', read_only=True)
    framework_total_preguntas = serializers.SerializerMethodField()
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    asignado_por_nombre = serializers.CharField(
        source='asignado_por.get_full_name',
        read_only=True
    )

    class Meta:
        model = EmpresaFramework
        fields = [
            'id',
            'empresa',
            'empresa_nombre',
            'framework',
            'framework_codigo',
            'framework_nombre',
            'framework_version',
            'framework_total_preguntas',
            'asignado_por',
            'asignado_por_nombre',
            'fecha_asignacion',
            'activo',
            'notas',
        ]
        read_only_fields = [
            'id',
            'asignado_por',
            'fecha_asignacion',
        ]

    def get_framework_total_preguntas(self, obj):
        return obj.framework.preguntas.filter(activo=True).count()


class EmpresaFrameworkListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listar los frameworks de una empresa.
    Usado por el Admin de Empresa para ver sus frameworks disponibles.
    """

    codigo = serializers.CharField(source='framework.codigo', read_only=True)
    nombre = serializers.CharField(source='framework.nombre', read_only=True)
    descripcion = serializers.CharField(source='framework.descripcion', read_only=True)
    version = serializers.CharField(source='framework.version', read_only=True)
    total_preguntas = serializers.SerializerMethodField()
    framework_id = serializers.IntegerField(source='framework.id', read_only=True)

    class Meta:
        model = EmpresaFramework
        fields = [
            'id',
            'framework_id',
            'codigo',
            'nombre',
            'descripcion',
            'version',
            'total_preguntas',
            'fecha_asignacion',
            'notas',
        ]
        read_only_fields = ['id', 'fecha_asignacion']

    def get_total_preguntas(self, obj):
        return obj.framework.preguntas.filter(activo=True).count()


# ============================================================================
# OTROS SERIALIZERS
# ============================================================================

class EvaluacionPreguntaSerializer(serializers.ModelSerializer):
    """Serializer para preguntas seleccionadas en evaluación"""
    
    pregunta_detalle = PreguntaEvaluacionListSerializer(
        source='pregunta',
        read_only=True
    )
    
    class Meta:
        model = EvaluacionPregunta
        fields = [
            'id',
            'evaluacion',
            'pregunta',
            'pregunta_detalle',
            'orden',
            'fecha_agregada'
        ]
        read_only_fields = ['id', 'fecha_agregada']


class NotaEvidenciaSerializer(serializers.ModelSerializer):
    """Serializer para Nota de Evidencia"""
    
    evidencia_descripcion = serializers.CharField(
        source='evidencia_requerida.descripcion',
        read_only=True
    )
    creado_por_nombre = serializers.CharField(
        source='creado_por.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = NotaEvidencia
        fields = [
            'id',
            'respuesta',
            'evidencia_requerida',
            'evidencia_descripcion',
            'nota',
            'referencia_documento',
            'fecha_creacion',
            'creado_por',
            'creado_por_nombre'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'creado_por']


class RespuestaEvaluacionSerializer(serializers.ModelSerializer):
    """Serializer para Respuesta de Evaluación"""
    
    pregunta_texto = serializers.CharField(
        source='pregunta.pregunta',
        read_only=True
    )
    pregunta_codigo = serializers.CharField(
        source='pregunta.codigo_control',
        read_only=True
    )
    notas_evidencias = NotaEvidenciaSerializer(
        many=True,
        read_only=True
    )
    respondido_por_nombre = serializers.CharField(
        source='respondido_por.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = RespuestaEvaluacion
        fields = [
            'id',
            'evaluacion',
            'pregunta',
            'pregunta_texto',
            'pregunta_codigo',
            'respuesta',
            'observaciones',
            'es_respuesta_original',
            'heredada_de',
            'fecha_respuesta',
            'respondido_por',
            'respondido_por_nombre',
            'notas_evidencias'
        ]
        read_only_fields = ['id', 'fecha_respuesta', 'respondido_por']


class ComentarioEvaluacionSerializer(serializers.ModelSerializer):
    """Serializer para Comentario de Evaluación"""
    
    creado_por_nombre = serializers.CharField(
        source='creado_por.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = ComentarioEvaluacion
        fields = [
            'id',
            'evaluacion',
            'respuesta',
            'comentario',
            'es_interno',
            'fecha_creacion',
            'creado_por',
            'creado_por_nombre'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'creado_por']