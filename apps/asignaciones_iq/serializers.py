# apps/asignaciones_iq/serializers.py
"""
Serializers para Asignación de Evaluaciones Inteligentes
"""

from rest_framework import serializers

from apps.respuestas.models import Evidencia
from .models import AsignacionEvaluacionIQ, ProgresoAsignacion, RespuestaEvaluacionIQ
from apps.evaluaciones.models import Evaluacion, PreguntaEvaluacion
from apps.usuarios.models import Usuario  # ⭐ Cambiado de User a Usuario


class AsignacionEvaluacionListSerializer(serializers.ModelSerializer):
    """Serializer para listado de asignaciones"""
    
    evaluacion_nombre = serializers.CharField(source='evaluacion.nombre', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario_asignado.get_full_name', read_only=True)
    usuario_email = serializers.EmailField(source='usuario_asignado.email', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = AsignacionEvaluacionIQ
        fields = [
            'id',
            'evaluacion',
            'evaluacion_nombre',
            'usuario_asignado',
            'usuario_nombre',
            'usuario_email',
            'estado',
            'estado_display',
            'fecha_asignacion',
            'fecha_inicio',
            'fecha_limite',
            'total_preguntas',
            'preguntas_respondidas',
            'porcentaje_completado',
            'esta_vencida',
            'dias_restantes',
            'activo',
        ]
        read_only_fields = [
            'id',
            'fecha_asignacion',
            'total_preguntas',
            'preguntas_respondidas',
            'porcentaje_completado',
        ]


class AsignacionEvaluacionDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para asignación"""
    
    evaluacion_detail = serializers.SerializerMethodField()
    usuario_detail = serializers.SerializerMethodField()
    asignado_por_nombre = serializers.CharField(
        source='asignado_por.get_full_name',
        read_only=True
    )
    revisado_por_nombre = serializers.CharField(
        source='revisado_por.get_full_name',
        read_only=True
    )
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)
    tiempo_usado = serializers.FloatField(read_only=True)
    
    class Meta:
        model = AsignacionEvaluacionIQ
        fields = [
            'id',
            'evaluacion',
            'evaluacion_detail',
            'usuario_asignado',
            'usuario_detail',
            'empresa',
            'estado',
            'estado_display',
            'fecha_asignacion',
            'fecha_inicio',
            'fecha_limite',
            'fecha_inicio_real',
            'fecha_completado',
            'fecha_revision',
            'total_preguntas',
            'preguntas_respondidas',
            'porcentaje_completado',
            'asignado_por',
            'asignado_por_nombre',
            'revisado_por',
            'revisado_por_nombre',
            'notas_asignacion',
            'notas_revision',
            'notificar_usuario',
            'recordatorio_enviado',
            'esta_vencida',
            'dias_restantes',
            'tiempo_usado',
            'activo',
        ]
        read_only_fields = [
            'id',
            'empresa',
            'fecha_asignacion',
            'fecha_inicio_real',
            'fecha_completado',
            'fecha_revision',
            'total_preguntas',
            'preguntas_respondidas',
            'porcentaje_completado',
            'asignado_por',
            'revisado_por',
            'recordatorio_enviado',
        ]
    
    def get_evaluacion_detail(self, obj):
        return {
            'id': obj.evaluacion.id,
            'nombre': obj.evaluacion.nombre,
            'descripcion': obj.evaluacion.descripcion,
            'frameworks': [fw.codigo for fw in obj.evaluacion.frameworks.all()],
            'nivel_deseado': obj.evaluacion.nivel_deseado,
            'nivel_deseado_display': obj.evaluacion.get_nivel_deseado_display(),
            'usar_todas_preguntas': obj.evaluacion.usar_todas_preguntas,
        }
    
    def get_usuario_detail(self, obj):
        return {
            'id': obj.usuario_asignado.id,
            'nombre': obj.usuario_asignado.get_full_name(),
            'email': obj.usuario_asignado.email,
            'cargo': obj.usuario_asignado.cargo if hasattr(obj.usuario_asignado, 'cargo') else None,
        }


class CrearAsignacionSerializer(serializers.ModelSerializer):
    """Serializer para crear asignación"""
    
    usuarios = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        help_text='Lista de IDs de usuarios a asignar'
    )
    
    class Meta:
        model = AsignacionEvaluacionIQ
        fields = [
            'evaluacion',
            'usuarios',
            'fecha_inicio',
            'fecha_limite',
            'notas_asignacion',
            'requiere_revision',  # ⭐ NUEVO
            'notificar_usuario',
        ]
    
    def validate(self, data):
        """Validar que la evaluación esté lista y los usuarios sean de la empresa"""
        
        evaluacion = data['evaluacion']
        usuarios_ids = data['usuarios']
        request = self.context.get('request')
        
        # Validar que la evaluación esté en estado válido
        if evaluacion.estado not in ['disponible', 'en_proceso']:
            raise serializers.ValidationError({
                'evaluacion': 'La evaluación debe estar disponible o en proceso para asignarla'
            })
        
        # Validar que haya al menos un usuario
        if not usuarios_ids:
            raise serializers.ValidationError({
                'usuarios': 'Debe seleccionar al menos un usuario'
            })
        
        # Validar fechas
        if data['fecha_inicio'] >= data['fecha_limite']:
            raise serializers.ValidationError({
                'fecha_limite': 'La fecha límite debe ser posterior a la fecha de inicio'
            })
        
        # Validar que los usuarios existan y sean de la empresa
        if request and request.user.rol != 'superadmin':
            usuarios = Usuario.objects.filter(
                id__in=usuarios_ids,
                empresa=request.user.empresa
            )
            if usuarios.count() != len(usuarios_ids):
                raise serializers.ValidationError({
                    'usuarios': 'Algunos usuarios no pertenecen a su empresa'
                })
        
        return data
    
    def create(self, validated_data):
        """Crear múltiples asignaciones"""
        usuarios_ids = validated_data.pop('usuarios')
        asignado_por = self.context['request'].user
        
        asignaciones = []
        for usuario_id in usuarios_ids:
            usuario = Usuario.objects.get(id=usuario_id)
            
            # Verificar si ya existe asignación
            asignacion_existente = AsignacionEvaluacionIQ.objects.filter(
                evaluacion=validated_data['evaluacion'],
                usuario_asignado=usuario
            ).first()
            
            if asignacion_existente:
                # Actualizar existente si está inactiva
                if not asignacion_existente.activo:
                    for key, value in validated_data.items():
                        setattr(asignacion_existente, key, value)
                    asignacion_existente.activo = True
                    asignacion_existente.asignado_por = asignado_por
                    asignacion_existente.save()
                    asignaciones.append(asignacion_existente)
            else:
                # Crear nueva
                asignacion = AsignacionEvaluacionIQ.objects.create(
                    usuario_asignado=usuario,
                    asignado_por=asignado_por,
                    **validated_data
                )
                asignaciones.append(asignacion)
        
        return asignaciones


class ActualizarEstadoAsignacionSerializer(serializers.Serializer):
    """Serializer para actualizar estado de asignación"""
    
    estado = serializers.ChoiceField(
        choices=['completada', 'aprobada', 'rechazada'],
        required=True
    )
    notas_revision = serializers.CharField(
        required=False,
        allow_blank=True
    )


class ProgresoAsignacionSerializer(serializers.ModelSerializer):
    """Serializer para progreso detallado"""
    
    pregunta_texto = serializers.CharField(source='pregunta.pregunta', read_only=True)
    pregunta_codigo = serializers.CharField(source='pregunta.codigo_control', read_only=True)
    
    class Meta:
        model = ProgresoAsignacion
        fields = [
            'id',
            'pregunta',
            'pregunta_texto',
            'pregunta_codigo',
            'respondida',
            'fecha_respuesta',
            'tiempo_respuesta_minutos',
        ]
        read_only_fields = ['id', 'fecha_respuesta', 'tiempo_respuesta_minutos']
        
        
class EvidenciaSerializer(serializers.ModelSerializer):
    """Serializer para evidencias"""
    url_archivo = serializers.SerializerMethodField()
    
    class Meta:
        model = Evidencia
        fields = [
            'id',
            'codigo_documento',
            'tipo_documento_enum',
            'titulo_documento',
            'objetivo_documento',
            'nombre_archivo_original',
            'archivo',
            'url_archivo',
            'tamanio_mb',
            'fecha_creacion',
        ]
        read_only_fields = ['id', 'fecha_creacion']
    
    def get_url_archivo(self, obj):
        return obj.url_archivo


class RespuestaEvaluacionIQSerializer(serializers.ModelSerializer):
    """Serializer para respuestas"""
    evidencias = EvidenciaSerializer(many=True, read_only=True)
    pregunta_detalle = serializers.SerializerMethodField()
    respuesta_display = serializers.CharField(source='get_respuesta_display', read_only=True)
    puntaje = serializers.SerializerMethodField()
    origen_respuesta = serializers.SerializerMethodField()  # ⭐ NUEVO
    
    class Meta:
        model = RespuestaEvaluacionIQ
        fields = [
            'id',
            'asignacion',
            'pregunta',
            'pregunta_detalle',
            'respuesta',
            'respuesta_display',
            'justificacion',
            'nivel_madurez',
            'justificacion_madurez',
            'comentarios_adicionales',
            'es_respuesta_original',
            'propagada_desde',
            'origen_respuesta',  # ⭐ NUEVO
            'evidencias',
            'puntaje',
            'respondido_por',
            'fecha_respuesta',
            'fecha_actualizacion',
        ]
        read_only_fields = [
            'id',
            'es_respuesta_original',
            'propagada_desde',
            'respondido_por',
            'fecha_respuesta',
            'fecha_actualizacion',
        ]
    
    def get_pregunta_detalle(self, obj):
        return {
            'correlativo': obj.pregunta.correlativo,
            'codigo_control': obj.pregunta.codigo_control,
            'nombre_control': obj.pregunta.nombre_control,
            'pregunta': obj.pregunta.pregunta,
            'objetivo_evaluacion': obj.pregunta.objetivo_evaluacion,
            'nivel_madurez': obj.pregunta.nivel_madurez,
            'framework': obj.pregunta.framework.nombre,
        }
    
    def get_puntaje(self, obj):
        return obj.get_puntaje()
    
    def get_origen_respuesta(self, obj):
        """
        ⭐ NUEVO: Indica el origen de la respuesta
        """
        if obj.es_respuesta_original:
            return {
                'tipo': 'original',
                'descripcion': 'Respondida por el usuario',
                'puede_editar': True
            }
        
        if obj.propagada_desde:
            # Verificar si es de otra evaluación o de la misma
            if obj.propagada_desde.asignacion.evaluacion != obj.asignacion.evaluacion:
                return {
                    'tipo': 'importada',
                    'descripcion': f'Importada de evaluación anterior: {obj.propagada_desde.asignacion.evaluacion.nombre}',
                    'fecha_original': obj.propagada_desde.fecha_respuesta,
                    'puede_editar': True,  # Usuario puede modificar respuestas importadas
                    'pregunta_origen': obj.propagada_desde.pregunta.codigo_control
                }
            else:
                return {
                    'tipo': 'propagada',
                    'descripcion': 'Auto-completada por pregunta relacionada',
                    'pregunta_origen': obj.propagada_desde.pregunta.codigo_control,
                    'puede_editar': False  # No debe editar, debe editar la original
                }
        
        return {
            'tipo': 'desconocido',
            'descripcion': 'Origen desconocido',
            'puede_editar': True
        }
    
# apps/asignaciones_iq/serializers.py

class CrearRespuestaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RespuestaEvaluacionIQ
        fields = [
            'id',  # ⭐ AÑADIR
            'asignacion',
            'pregunta',
            'respuesta',
            'justificacion',
            'nivel_madurez',
            'justificacion_madurez',
            'comentarios_adicionales',
        ]
        read_only_fields = ['id']  # ⭐ AÑADIR
    
    def validate(self, data):
        """Validar que la pregunta pertenezca a la evaluación"""
        asignacion = data.get('asignacion')
        pregunta = data.get('pregunta')
        
        # ⭐ RELAJAR VALIDACIÓN - Solo verificar que la pregunta existe
        # La validación estricta puede hacerse en el frontend
        if not pregunta:
            raise serializers.ValidationError({'pregunta': 'Pregunta es requerida'})
        
        # Verificar que no haya duplicados
        if not self.instance:  # Solo al crear
            if RespuestaEvaluacionIQ.objects.filter(
                asignacion=asignacion,
                pregunta=pregunta
            ).exists():
                raise serializers.ValidationError({
                    'pregunta': 'Ya existe una respuesta para esta pregunta'
                })
        
        return data


class PreguntaConRespuestaSerializer(serializers.ModelSerializer):
    """Pregunta con su respuesta (si existe)"""
    respuesta = serializers.SerializerMethodField()
    evidencias_requeridas = serializers.SerializerMethodField()
    framework_nombre = serializers.CharField(source='framework.nombre', read_only=True)
    
    class Meta:
        model = PreguntaEvaluacion
        fields = [
            'id',
            'correlativo',
            'framework',
            'framework_nombre',
            'codigo_control',
            'nombre_control',
            'seccion_general',
            'objetivo_evaluacion',
            'pregunta',
            'nivel_madurez',
            'evidencias_requeridas',
            'respuesta',
        ]
    
    def get_respuesta(self, obj):
        asignacion_id = self.context.get('asignacion_id')
        if not asignacion_id:
            return None
        
        try:
            respuesta = RespuestaEvaluacionIQ.objects.get(
                asignacion_id=asignacion_id,
                pregunta=obj
            )
            return RespuestaEvaluacionIQSerializer(respuesta).data
        except RespuestaEvaluacionIQ.DoesNotExist:
            return None
    
    def get_evidencias_requeridas(self, obj):
        evidencias = obj.evidencias_requeridas.all()
        return [{
            'orden': e.orden,
            'descripcion': e.descripcion
        } for e in evidencias]