# apps/asignaciones_iq/serializers.py
"""
Serializers para Asignación de Evaluaciones Inteligentes
"""
from rest_framework import serializers
from django.utils import timezone

from .models import AsignacionEvaluacionIQ, RespuestaEvaluacionIQ, CalculoNivelIQ
from apps.evaluaciones.models import PreguntaEvaluacion
from apps.usuarios.models import Usuario
from apps.respuestas.models import Evidencia


# ─────────────────────────────────────────────────────────────────────────────
# EVIDENCIA
# ─────────────────────────────────────────────────────────────────────────────

class EvidenciaIQSerializer(serializers.ModelSerializer):
    url_archivo = serializers.SerializerMethodField()

    class Meta:
        model = Evidencia
        fields = [
            'id', 'codigo_documento', 'tipo_documento_enum',
            'titulo_documento', 'objetivo_documento',
            'nombre_archivo_original', 'archivo', 'url_archivo',
            'tamanio_mb', 'fecha_creacion',
        ]
        read_only_fields = ['id', 'fecha_creacion']

    def get_url_archivo(self, obj):
        return obj.url_archivo


# ─────────────────────────────────────────────────────────────────────────────
# RESPUESTA IQ — LECTURA COMPLETA
# ─────────────────────────────────────────────────────────────────────────────

class RespuestaIQDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para leer una respuesta (incluye calificación del auditor)."""

    evidencias          = EvidenciaIQSerializer(many=True, read_only=True)
    estado_display      = serializers.CharField(source='get_estado_display', read_only=True)
    respondido_por_nombre = serializers.CharField(
        source='respondido_por.get_full_name', read_only=True
    )
    auditado_por_nombre = serializers.CharField(
        source='auditado_por.get_full_name', read_only=True
    )
    calificacion_display = serializers.CharField(
        source='get_calificacion_auditor_display', read_only=True
    )
    puntaje = serializers.SerializerMethodField()
    total_evidencias = serializers.SerializerMethodField()

    class Meta:
        model = RespuestaEvaluacionIQ
        fields = [
            'id', 'asignacion', 'pregunta',
            # Usuario
            'respuesta', 'justificacion', 'comentarios_adicionales',
            # Auditor
            'calificacion_auditor', 'calificacion_display',
            'comentarios_auditor', 'recomendaciones_auditor',
            'fecha_auditoria', 'auditado_por', 'auditado_por_nombre',
            'nivel_madurez',
            # Estado
            'estado', 'estado_display',
            # Propagación
            'es_respuesta_original', 'propagada_desde',
            # Auditoría
            'respondido_por', 'respondido_por_nombre', 'respondido_at',
            'modificado_por', 'modificado_at', 'version',
            # Relaciones
            'evidencias', 'total_evidencias', 'puntaje',
        ]
        read_only_fields = [
            'id', 'estado', 'es_respuesta_original', 'propagada_desde',
            'respondido_por', 'respondido_at', 'modificado_por', 'modificado_at',
            'calificacion_auditor', 'comentarios_auditor', 'recomendaciones_auditor',
            'fecha_auditoria', 'auditado_por', 'nivel_madurez', 'version',
        ]

    def get_puntaje(self, obj):
        return obj.get_puntaje()

    def get_total_evidencias(self, obj):
        return obj.evidencias.filter(activo=True).count()


# ─────────────────────────────────────────────────────────────────────────────
# RESPUESTA IQ — CREAR / ACTUALIZAR (usuario)
# ─────────────────────────────────────────────────────────────────────────────

class CrearRespuestaIQSerializer(serializers.ModelSerializer):
    """
    El usuario crea/actualiza una respuesta.
    Solo puede enviar: null (subirá evidencias) / 'NO_CUMPLE' / 'NO_APLICA'
    """
    respuesta = serializers.ChoiceField(
        choices=[('NO_CUMPLE', 'No Cumple'), ('NO_APLICA', 'No Aplica')],
        required=False, allow_null=True,
    )

    class Meta:
        model = RespuestaEvaluacionIQ
        fields = [
            'id', 'asignacion', 'pregunta',
            'respuesta', 'justificacion', 'comentarios_adicionales',
        ]
        read_only_fields = ['id']

    def validate_respuesta(self, value):
        if value is not None and value not in ['NO_APLICA', 'NO_CUMPLE']:
            raise serializers.ValidationError(
                'Solo puedes marcar "No Aplica" o "No Cumple". '
                'SI_CUMPLE y CUMPLE_PARCIAL los asigna el Auditor.'
            )
        return value

    def validate(self, data):
        asignacion = data.get('asignacion') or (self.instance.asignacion if self.instance else None)
        pregunta   = data.get('pregunta')   or (self.instance.pregunta   if self.instance else None)
        justificacion = data.get('justificacion', getattr(self.instance, 'justificacion', ''))

        # Justificación obligatoria
        if len(justificacion.strip()) < 10:
            raise serializers.ValidationError(
                {'justificacion': 'Mínimo 10 caracteres'}
            )

        # No duplicar al crear
        if not self.instance and pregunta and asignacion:
            if RespuestaEvaluacionIQ.objects.filter(
                asignacion=asignacion, pregunta=pregunta
            ).exists():
                raise serializers.ValidationError(
                    {'pregunta': 'Ya existe una respuesta para esta pregunta'}
                )

        return data

    def create(self, validated_data):
        validated_data['estado']   = 'borrador'
        validated_data['version']  = 1
        return RespuestaEvaluacionIQ.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if instance.estado != 'borrador':
            raise serializers.ValidationError(
                'Solo se puede editar una respuesta en borrador'
            )
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.estado = 'borrador'
        instance.version += 1
        instance.modificado_at = timezone.now()
        instance.save()
        return instance


# ─────────────────────────────────────────────────────────────────────────────
# ENVIAR RESPUESTA (borrador → enviado)
# ─────────────────────────────────────────────────────────────────────────────

class EnviarRespuestaIQSerializer(serializers.Serializer):
    """Valida que la respuesta esté lista para enviarse."""

    def validate(self, attrs):
        respuesta = self.instance

        if respuesta.estado != 'borrador':
            raise serializers.ValidationError(
                {'estado': 'Solo se puede enviar desde borrador'}
            )

        tiene_evidencias = respuesta.evidencias.filter(activo=True).exists()

        # "Sí" (respuesta=null) → requiere evidencias
        if respuesta.respuesta is None and not tiene_evidencias:
            raise serializers.ValidationError({
                'evidencias': 'Para enviar con respuesta vacía debes subir al menos una evidencia.'
            })

        return attrs

    def save(self):
        respuesta = self.instance
        respuesta.estado = 'enviado'
        respuesta.save()
        # Actualizar progreso de la asignación (puede disparar _completar())
        respuesta.asignacion.actualizar_progreso()
        return respuesta


# ─────────────────────────────────────────────────────────────────────────────
# CALIFICAR RESPUESTA (auditor)
# ─────────────────────────────────────────────────────────────────────────────

class CalificarRespuestaIQSerializer(serializers.Serializer):
    """El auditor califica una respuesta enviada."""

    calificacion_auditor = serializers.ChoiceField(
        choices=['SI_CUMPLE', 'CUMPLE_PARCIAL', 'NO_CUMPLE']
    )
    nivel_madurez = serializers.DecimalField(
        max_digits=2, decimal_places=1,
        min_value=0, max_value=5
    )
    comentarios_auditor     = serializers.CharField(required=False, allow_blank=True)
    recomendaciones_auditor = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        calificacion  = data.get('calificacion_auditor')
        nivel_madurez = float(data.get('nivel_madurez', 0))

        if calificacion == 'NO_CUMPLE' and nivel_madurez != 0:
            raise serializers.ValidationError(
                {'nivel_madurez': 'Debe ser 0 para NO_CUMPLE'}
            )
        if calificacion in ['SI_CUMPLE', 'CUMPLE_PARCIAL'] and nivel_madurez == 0:
            raise serializers.ValidationError(
                {'nivel_madurez': 'Debe ser mayor a 0 para SI_CUMPLE / CUMPLE_PARCIAL'}
            )
        if (nivel_madurez * 2) % 1 != 0:
            raise serializers.ValidationError(
                {'nivel_madurez': 'Debe ser múltiplo de 0.5'}
            )
        return data

    def save(self):
        auditor = self.context['request'].user
        self.instance.calificar(
            auditor=auditor,
            calificacion=self.validated_data['calificacion_auditor'],
            nivel_madurez=self.validated_data['nivel_madurez'],
            comentarios=self.validated_data.get('comentarios_auditor', ''),
            recomendaciones=self.validated_data.get('recomendaciones_auditor', ''),
        )
        return self.instance


# ─────────────────────────────────────────────────────────────────────────────
# PREGUNTA CON RESPUESTA (para el formulario del usuario)
# ─────────────────────────────────────────────────────────────────────────────

class PreguntaConRespuestaIQSerializer(serializers.ModelSerializer):
    respuesta          = serializers.SerializerMethodField()
    evidencias_requeridas = serializers.SerializerMethodField()
    framework_nombre   = serializers.CharField(source='framework.nombre', read_only=True)
    nivel_madurez_display = serializers.CharField(
        source='get_nivel_madurez_display', read_only=True
    )

    class Meta:
        model = PreguntaEvaluacion
        fields = [
            'id', 'correlativo', 'framework', 'framework_nombre',
            'codigo_control', 'nombre_control', 'seccion_general',
            'objetivo_evaluacion', 'pregunta', 'nivel_madurez',
            'nivel_madurez_display', 'evidencias_requeridas', 'respuesta',
        ]

    def get_respuesta(self, obj):
        asignacion_id = self.context.get('asignacion_id')
        if not asignacion_id:
            return None
        try:
            r = RespuestaEvaluacionIQ.objects.get(
                asignacion_id=asignacion_id, pregunta=obj
            )
            return RespuestaIQDetailSerializer(r).data
        except RespuestaEvaluacionIQ.DoesNotExist:
            return None

    def get_evidencias_requeridas(self, obj):
        return [
            {'orden': e.orden, 'descripcion': e.descripcion}
            for e in obj.evidencias_requeridas.all()
        ]


# ─────────────────────────────────────────────────────────────────────────────
# ASIGNACIÓN — LISTADO
# ─────────────────────────────────────────────────────────────────────────────

class AsignacionIQListSerializer(serializers.ModelSerializer):
    evaluacion_nombre  = serializers.CharField(source='evaluacion.nombre',                read_only=True)
    usuario_nombre     = serializers.CharField(source='usuario_asignado.get_full_name',   read_only=True)
    usuario_email      = serializers.EmailField(source='usuario_asignado.email',          read_only=True)
    estado_display     = serializers.CharField(source='get_estado_display',               read_only=True)
    esta_vencida       = serializers.BooleanField(read_only=True)
    dias_restantes     = serializers.IntegerField(read_only=True)

    class Meta:
        model = AsignacionEvaluacionIQ
        fields = [
            'id', 'evaluacion', 'evaluacion_nombre',
            'usuario_asignado', 'usuario_nombre', 'usuario_email',
            'estado', 'estado_display',
            'fecha_asignacion', 'fecha_inicio', 'fecha_limite',
            'total_preguntas', 'preguntas_respondidas', 'porcentaje_completado',
            'esta_vencida', 'dias_restantes', 'activo',
        ]
        read_only_fields = [
            'id', 'fecha_asignacion', 'total_preguntas',
            'preguntas_respondidas', 'porcentaje_completado',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# ASIGNACIÓN — DETALLE
# ─────────────────────────────────────────────────────────────────────────────

class AsignacionIQDetailSerializer(serializers.ModelSerializer):
    evaluacion_detail  = serializers.SerializerMethodField()
    usuario_detail     = serializers.SerializerMethodField()
    asignado_por_nombre = serializers.CharField(
        source='asignado_por.get_full_name', read_only=True
    )
    auditado_por_nombre = serializers.CharField(
        source='auditado_por.get_full_name', read_only=True
    )
    estado_display     = serializers.CharField(source='get_estado_display', read_only=True)
    esta_vencida       = serializers.BooleanField(read_only=True)
    dias_restantes     = serializers.IntegerField(read_only=True)

    class Meta:
        model = AsignacionEvaluacionIQ
        fields = [
            'id', 'evaluacion', 'evaluacion_detail',
            'usuario_asignado', 'usuario_detail', 'empresa',
            'estado', 'estado_display',
            'fecha_asignacion', 'fecha_inicio', 'fecha_limite',
            'fecha_inicio_real', 'fecha_completado', 'fecha_auditada',
            'total_preguntas', 'preguntas_respondidas', 'porcentaje_completado',
            'asignado_por', 'asignado_por_nombre',
            'auditado_por', 'auditado_por_nombre',
            'notas_asignacion', 'notas_revision', 'notas_auditoria',
            'requiere_revision', 'notificar_usuario',
            'esta_vencida', 'dias_restantes', 'activo',
        ]
        read_only_fields = [
            'id', 'empresa', 'fecha_asignacion', 'fecha_inicio_real',
            'fecha_completado', 'fecha_auditada',
            'total_preguntas', 'preguntas_respondidas', 'porcentaje_completado',
            'asignado_por', 'auditado_por',
        ]

    def get_evaluacion_detail(self, obj):
        return {
            'id': obj.evaluacion.id,
            'nombre': obj.evaluacion.nombre,
            'descripcion': obj.evaluacion.descripcion,
            'frameworks': [fw.codigo for fw in obj.evaluacion.frameworks.all()],
            'nivel_deseado': obj.evaluacion.nivel_deseado,
            'nivel_deseado_display': obj.evaluacion.get_nivel_deseado_display(),
        }

    def get_usuario_detail(self, obj):
        return {
            'id': obj.usuario_asignado.id,
            'nombre': obj.usuario_asignado.get_full_name(),
            'email': obj.usuario_asignado.email,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CREAR ASIGNACIÓN
# ─────────────────────────────────────────────────────────────────────────────

class CrearAsignacionIQSerializer(serializers.ModelSerializer):
    usuarios = serializers.ListField(
        child=serializers.IntegerField(), write_only=True,
        help_text='Lista de IDs de usuarios'
    )

    class Meta:
        model = AsignacionEvaluacionIQ
        fields = [
            'evaluacion', 'usuarios', 'fecha_inicio', 'fecha_limite',
            'notas_asignacion', 'requiere_revision', 'notificar_usuario',
        ]

    def validate(self, data):
        evaluacion   = data['evaluacion']
        usuarios_ids = data['usuarios']
        request      = self.context.get('request')

        if evaluacion.estado not in ['disponible', 'en_proceso']:
            raise serializers.ValidationError({
                'evaluacion': 'La evaluación debe estar disponible o en proceso'
            })
        if not usuarios_ids:
            raise serializers.ValidationError(
                {'usuarios': 'Debe seleccionar al menos un usuario'}
            )
        if data['fecha_inicio'] >= data['fecha_limite']:
            raise serializers.ValidationError(
                {'fecha_limite': 'Debe ser posterior a la fecha de inicio'}
            )
        if request and request.user.rol != 'superadmin':
            count = Usuario.objects.filter(
                id__in=usuarios_ids, empresa=request.user.empresa
            ).count()
            if count != len(usuarios_ids):
                raise serializers.ValidationError(
                    {'usuarios': 'Algunos usuarios no pertenecen a su empresa'}
                )
        return data

    def create(self, validated_data):
        usuarios_ids  = validated_data.pop('usuarios')
        asignado_por  = self.context['request'].user
        asignaciones  = []

        for usuario_id in usuarios_ids:
            usuario = Usuario.objects.get(id=usuario_id)
            existente = AsignacionEvaluacionIQ.objects.filter(
                evaluacion=validated_data['evaluacion'],
                usuario_asignado=usuario
            ).first()

            if existente:
                if not existente.activo:
                    for k, v in validated_data.items():
                        setattr(existente, k, v)
                    existente.activo = True
                    existente.asignado_por = asignado_por
                    existente.save()
                    asignaciones.append(existente)
            else:
                a = AsignacionEvaluacionIQ.objects.create(
                    usuario_asignado=usuario,
                    asignado_por=asignado_por,
                    **validated_data
                )
                asignaciones.append(a)

        return asignaciones


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO DE NIVEL IQ
# ─────────────────────────────────────────────────────────────────────────────

class CalculoNivelIQSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalculoNivelIQ
        fields = [
            'id', 'asignacion', 'empresa', 'usuario',
            'framework_id', 'framework_nombre', 'seccion',
            'nivel_deseado', 'nivel_actual', 'gap', 'clasificacion_gap',
            'total_preguntas', 'respuestas_si_cumple', 'respuestas_cumple_parcial',
            'respuestas_no_cumple', 'respuestas_no_aplica', 'porcentaje_cumplimiento',
            'calculado_at',
        ]
        read_only_fields = ['id', 'gap', 'clasificacion_gap', 'calculado_at']