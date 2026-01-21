# apps/respuestas/serializers.py

import os
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from .models import (
    TipoDocumento,
    Respuesta,
    HistorialRespuesta,
    Evidencia,
    CalculoNivel,
    #Iniciativa
)
from apps.encuestas.models import Pregunta, Dimension
from apps.asignaciones.models import Asignacion
from apps.usuarios.models import Usuario
from drf_spectacular.utils import extend_schema_field

# ============================================
# SERIALIZERS DE TIPOS DE DOCUMENTO
# ============================================

class TipoDocumentoSerializer(serializers.ModelSerializer):
    """Serializer para tipos de documento"""
    
    class Meta:
        model = TipoDocumento
        fields = [
            'id', 'empresa', 'nombre', 'descripcion', 
            'requiere_fecha', 'activo'
        ]
        read_only_fields = ['id']


class TipoDocumentoListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    
    class Meta:
        model = TipoDocumento
        fields = ['id', 'nombre', 'descripcion']


# ============================================
# SERIALIZERS DE EVIDENCIAS
# ============================================

class EvidenciaSerializer(serializers.ModelSerializer):
    """
    Serializer completo para evidencias
    Incluye URL firmada temporal de Supabase
    """
    
    subido_por_nombre = serializers.CharField(
        source='subido_por.nombre_completo', 
        read_only=True
    )
    url_archivo = serializers.SerializerMethodField()  # ⭐ URL firmada de Supabase
    tamanio_mb = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()
    tipo_documento_display = serializers.CharField(
        source='get_tipo_documento_enum_display',
        read_only=True
    )
    
    class Meta:
        model = Evidencia
        fields = [
            'id', 
            'respuesta',
            # Metadatos del documento
            'codigo_documento',
            'tipo_documento_enum', 
            'tipo_documento_display',
            'titulo_documento', 
            'objetivo_documento', 
            'fecha_ultima_actualizacion',
            # Datos del archivo
            'nombre_archivo_original',
            'archivo',  # ⭐ Ruta en Supabase (CharField)
            'url_archivo',  # ⭐ URL firmada temporal
            'extension',
            'tamanio_bytes', 
            'tamanio_mb',
            #'tipo_mime',  # ⭐ NUEVO
            # Auditoría
            'subido_por', 
            'subido_por_nombre',
            'fecha_creacion', 
            'activo'
        ]
        read_only_fields = [
            'id', 
            'nombre_archivo_original', 
            'tamanio_bytes',
            #'tipo_mime',
            'url_archivo', 
            'tamanio_mb',
            'extension',
            'fecha_creacion',
            'archivo'  # ⭐ No editable directamente
        ]
    
    def get_url_archivo(self, obj):
        """
        ⭐ OBTENER URL FIRMADA TEMPORAL DE SUPABASE
        Válida por 1 hora
        """
        return obj.url_archivo  # Usa la property del modelo
    
    def get_tamanio_mb(self, obj):
        """Retorna tamaño en MB"""
        return obj.tamanio_mb
    
    def get_extension(self, obj):
        """Retorna extensión del archivo"""
        return obj.extension_archivo
    
    def validate(self, attrs):
        """Validaciones"""
        respuesta = attrs.get('respuesta')
        
        # Validar máximo 3 evidencias
        if respuesta and not self.instance:
            if respuesta.evidencias.filter(activo=True).count() >= 3:
                raise serializers.ValidationError({
                    'respuesta': 'Solo se permiten máximo 3 archivos de evidencia por respuesta'
                })
        
        return attrs


class EvidenciaCreateSerializer(serializers.Serializer):
    """
    ⭐ SERIALIZER PARA CREAR EVIDENCIAS
    Maneja la subida de archivos a Supabase
    """
    
    # Campos requeridos
    respuesta_id = serializers.UUIDField(required=True)
    archivo = serializers.FileField(required=True)
    
    # Metadatos del documento
    codigo_documento = serializers.CharField(
        max_length=50,
        required=True,
        help_text='Código único del documento (ej: POL-SEG-001)'
    )
    tipo_documento_enum = serializers.ChoiceField(
        choices=Evidencia.TIPOS_DOCUMENTO_CHOICES,
        default='otro'
    )
    titulo_documento = serializers.CharField(
        max_length=60,
        default='Documento sin título'
    )
    objetivo_documento = serializers.CharField(
        max_length=180,
        default='Sin objetivo especificado'
    )
    
    def validate_codigo_documento(self, value):
        """Validar código de documento"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError('El código de documento es obligatorio')
        
        # Limpiar espacios y convertir a mayúsculas
        return value.strip().upper()
    
    def validate_archivo(self, value):
        """
        ⭐ VALIDAR ARCHIVO ANTES DE SUBIRLO
        """
        # Validar extensión
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in Evidencia.EXTENSIONES_PERMITIDAS:
            raise serializers.ValidationError(
                f'Extensión no permitida. Válidas: {", ".join(Evidencia.EXTENSIONES_PERMITIDAS)}'
            )
        
        # Validar tamaño (10MB)
        MAX_SIZE = 10 * 1024 * 1024
        if value.size > MAX_SIZE:
            raise serializers.ValidationError(
                f'El archivo no puede superar los 10MB. Tamaño actual: {round(value.size / (1024 * 1024), 2)}MB'
            )
        
        return value
    
    def validate(self, attrs):
        """Validaciones adicionales"""
        # Validar que titulo_documento no esté vacío
        titulo = attrs.get('titulo_documento', '').strip()
        if not titulo or titulo == 'Documento sin título':
            raise serializers.ValidationError({
                'titulo_documento': 'Debes proporcionar un título descriptivo para el documento'
            })
        
        return attrs

class VerificarCodigoDocumentoSerializer(serializers.Serializer):
    """
    Serializer para verificar si un código de documento existe
    """
    codigo_documento = serializers.CharField(
        max_length=50,
        required=True,
        help_text='Código del documento a verificar'
    )
    
    def validate_codigo_documento(self, value):
        """Limpiar y validar código"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError('El código de documento es obligatorio')
        
        return value.strip().upper()
# ============================================
# SERIALIZERS DE HISTORIAL
# ============================================

class HistorialRespuestaSerializer(serializers.ModelSerializer):
    """Serializer para historial de cambios"""
    
    usuario_nombre = serializers.CharField(
        source='usuario.nombre_completo',
        read_only=True
    )
    tipo_cambio_display = serializers.CharField(
        source='get_tipo_cambio_display',
        read_only=True
    )
    
    class Meta:
        model = HistorialRespuesta
        fields = [
            'id', 'respuesta', 'tipo_cambio', 'tipo_cambio_display',
            'usuario', 'usuario_nombre',
            'valor_anterior_respuesta', 'valor_anterior_justificacion',
            'valor_anterior_comentarios',
            'valor_nuevo_respuesta', 'valor_nuevo_justificacion',
            'valor_nuevo_comentarios',
            'motivo', 'ip_address', 'user_agent', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


# ============================================
# SERIALIZERS DE RESPUESTAS
# ============================================

class RespuestaListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    
    pregunta_codigo = serializers.CharField(source='pregunta.codigo', read_only=True)
    pregunta_texto = serializers.CharField(source='pregunta.texto', read_only=True)
    respuesta_display = serializers.CharField(
        source='get_respuesta_display',
        read_only=True
    )
    estado_display = serializers.CharField(
        source='get_estado_display',
        read_only=True
    )
    respondido_por_nombre = serializers.CharField(
        source='respondido_por.nombre_completo',
        read_only=True
    )
    # ⭐ NUEVOS CAMPOS
    nivel_madurez_display = serializers.CharField(
        source='get_nivel_madurez_display_verbose',
        read_only=True
    )
    total_evidencias = serializers.SerializerMethodField()
    
    class Meta:
        model = Respuesta
        fields = [
            'id', 'asignacion', 'pregunta', 'pregunta_codigo', 'pregunta_texto',
            'respuesta', 'respuesta_display', 'justificacion',
            # ⭐ NUEVOS CAMPOS
            'nivel_madurez', 'nivel_madurez_display',
            'estado', 'estado_display', 'respondido_por', 'respondido_por_nombre',
            'respondido_at', 'total_evidencias', 'version'
        ]
    
    def get_total_evidencias(self, obj):
        """Total de evidencias"""
        return obj.evidencias.filter(activo=True).count()


class RespuestaDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado con evidencias e historial"""
    
    pregunta_codigo = serializers.CharField(source='pregunta.codigo', read_only=True)
    pregunta_texto = serializers.CharField(source='pregunta.texto', read_only=True)
    pregunta_objetivo = serializers.CharField(source='pregunta.objetivo', read_only=True)
    respuesta_display = serializers.CharField(source='get_respuesta_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    respondido_por_nombre = serializers.CharField(
        source='respondido_por.nombre_completo',
        read_only=True
    )
    modificado_por_nombre = serializers.CharField(
        source='modificado_por.nombre_completo',
        read_only=True
    )
    # ⭐ NUEVOS CAMPOS
    nivel_madurez_display = serializers.CharField(
        source='get_nivel_madurez_display_verbose',
        read_only=True
    )
    
    evidencias = EvidenciaSerializer(many=True, read_only=True)
    historial = HistorialRespuestaSerializer(many=True, read_only=True)
    
    class Meta:
        model = Respuesta
        fields = [
            'id', 'asignacion', 'pregunta', 'pregunta_codigo', 'pregunta_texto',
            'pregunta_objetivo', 'respuesta', 'respuesta_display',
            'justificacion', 'comentarios_adicionales',
            # ⭐ NUEVOS CAMPOS
            'nivel_madurez', 'nivel_madurez_display',
            'estado', 'estado_display',
            'respondido_por', 'respondido_por_nombre', 'respondido_at',
            'modificado_por', 'modificado_por_nombre', 'modificado_at',
            'version', 'evidencias', 'historial'
        ]



class RespuestaCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear respuestas"""
    
    class Meta:
        model = Respuesta
        fields = [
            'asignacion', 'pregunta', 'respuesta', 
            'justificacion', 'comentarios_adicionales',
            # ⭐ CAMPOS DE NIVEL DE MADUREZ
            'nivel_madurez'
        ]
    
    def validate(self, attrs):
        """Validaciones"""
        asignacion = attrs.get('asignacion')
        pregunta = attrs.get('pregunta')
        respuesta = attrs.get('respuesta')
        justificacion = attrs.get('justificacion', '')
        nivel_madurez = attrs.get('nivel_madurez', 0)
        # justificacion_madurez = attrs.get('justificacion_madurez', '')  # ❌ YA NO SE USA
        
        # Validar que la pregunta pertenezca a la dimensión
        if pregunta.dimension != asignacion.dimension:
            raise serializers.ValidationError({
                'pregunta': 'La pregunta no pertenece a la dimensión de esta asignación'
            })
        
        # Validar que no exista ya una respuesta
        if Respuesta.objects.filter(
            asignacion=asignacion,
            pregunta=pregunta
        ).exists():
            raise serializers.ValidationError({
                'pregunta': 'Ya existe una respuesta para esta pregunta'
            })
        
        # Validar justificación según respuesta
        if respuesta == 'SI_CUMPLE' and len(justificacion.strip()) < 10:
            raise serializers.ValidationError({
                'justificacion': 'Para respuestas "Sí Cumple", la justificación debe tener al menos 10 caracteres'
            })
        
        if len(justificacion.strip()) < 10:
            raise serializers.ValidationError({
                'justificacion': 'La justificación debe tener al menos 10 caracteres'
            })
        
        # ⭐ VALIDACIONES DE NIVEL DE MADUREZ (SIMPLIFICADAS)
        
        # 1. Si NO_CUMPLE o NO_APLICA → nivel debe ser 0
        if respuesta in ['NO_CUMPLE', 'NO_APLICA']:
            if nivel_madurez != 0:
                raise serializers.ValidationError({
                    'nivel_madurez': 'El nivel de madurez debe ser 0 para "No Cumple" o "No Aplica"'
                })

        # 2. Nivel debe ser múltiplo de 0.5
        if (nivel_madurez * 2) % 1 != 0:
            raise serializers.ValidationError({
                'nivel_madurez': 'El nivel de madurez debe ser en incrementos de 0.5 (ej: 1.0, 1.5, 2.0, etc.)'
            })
        
        return attrs
    
    def create(self, validated_data):
        """Crear respuesta con auditoría"""
        request = self.context.get('request')
        
        with transaction.atomic():
            if request and request.user:
                validated_data['respondido_por'] = request.user
            
            validated_data['estado'] = 'borrador'
            validated_data['version'] = 1
            
            respuesta = Respuesta.objects.create(**validated_data)
            
            HistorialRespuesta.objects.create(
                respuesta=respuesta,
                tipo_cambio='creacion',
                usuario=request.user if request else None,
                valor_nuevo_respuesta=respuesta.respuesta,
                valor_nuevo_justificacion=respuesta.justificacion,
                motivo='Creación inicial de respuesta',
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request)
            )
            
            return respuesta
    
    def _get_client_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _get_user_agent(self, request):
        if not request:
            return ''
        return request.META.get('HTTP_USER_AGENT', '')[:255]


class RespuestaUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar respuestas (Usuario)"""
    
    class Meta:
        model = Respuesta
        fields = [
            'respuesta', 'justificacion', 'comentarios_adicionales',
            # ⭐ CAMPOS DE NIVEL DE MADUREZ
            'nivel_madurez'
        ]

    def validate(self, attrs):
        """Validaciones"""
        if self.instance.estado != 'borrador':
            raise serializers.ValidationError({
                'estado': 'Solo se pueden editar respuestas en estado borrador'
            })
        
        respuesta = attrs.get('respuesta', self.instance.respuesta)
        justificacion = attrs.get('justificacion', self.instance.justificacion)
        nivel_madurez = attrs.get('nivel_madurez', self.instance.nivel_madurez)
        # justificacion_madurez = attrs.get('justificacion_madurez', self.instance.justificacion_madurez)  # ❌ YA NO SE USA
        
        # Validar justificación
        if respuesta == 'SI_CUMPLE' and len(justificacion.strip()) < 10:
            raise serializers.ValidationError({
                'justificacion': 'Para respuestas "Sí Cumple", la justificación debe tener al menos 10 caracteres'
            })
        
        if len(justificacion.strip()) < 10:
            raise serializers.ValidationError({
                'justificacion': 'La justificación debe tener al menos 10 caracteres'
            })
        
        # ⭐ VALIDACIONES DE NIVEL DE MADUREZ (SIMPLIFICADAS)
        
        # 1. Si NO_CUMPLE o NO_APLICA → nivel debe ser 0
        if respuesta in ['NO_CUMPLE', 'NO_APLICA']:
            if nivel_madurez != 0:
                raise serializers.ValidationError({
                    'nivel_madurez': 'El nivel de madurez debe ser 0 para "No Cumple" o "No Aplica"'
                })
        
        # 2. Nivel debe ser múltiplo de 0.5
        if (nivel_madurez * 2) % 1 != 0:
            raise serializers.ValidationError({
                'nivel_madurez': 'El nivel de madurez debe ser en incrementos de 0.5'
            })
        
        return attrs
    
    def update(self, instance, validated_data):
        """Actualizar con auditoría"""
        request = self.context.get('request')
        
        with transaction.atomic():
            valor_anterior_respuesta = instance.respuesta
            valor_anterior_justificacion = instance.justificacion
            valor_anterior_comentarios = instance.comentarios_adicionales
            
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            
            HistorialRespuesta.objects.create(
                respuesta=instance,
                tipo_cambio='modificacion_respuesta',
                usuario=request.user if request else None,
                valor_anterior_respuesta=valor_anterior_respuesta,
                valor_anterior_justificacion=valor_anterior_justificacion,
                valor_anterior_comentarios=valor_anterior_comentarios,
                valor_nuevo_respuesta=instance.respuesta,
                valor_nuevo_justificacion=instance.justificacion,
                valor_nuevo_comentarios=instance.comentarios_adicionales,
                motivo='Actualización por el usuario',
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request)
            )
            
            return instance
    
    def _get_client_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _get_user_agent(self, request):
        if not request:
            return ''
        return request.META.get('HTTP_USER_AGENT', '')[:255]


class RespuestaEnviarSerializer(serializers.Serializer):
    """Serializer para enviar respuesta (marcar como enviada)"""
    
    def validate(self, attrs):
        """Validaciones antes de enviar"""
        respuesta = self.instance
        
        if respuesta.estado != 'borrador':
            raise serializers.ValidationError({
                'estado': 'Solo se pueden enviar respuestas en estado borrador'
            })
        
        # ⭐ ACTUALIZADO: Validar evidencias para SI_CUMPLE y CUMPLE_PARCIAL
        if respuesta.respuesta in ['SI_CUMPLE', 'CUMPLE_PARCIAL']:
            if not respuesta.evidencias.filter(activo=True).exists():
                raise serializers.ValidationError({
                    'evidencias': f'Las respuestas "{respuesta.get_respuesta_display()}" requieren al menos una evidencia'
                })
        
        # ⭐ NUEVO: Validar nivel de madurez
        if respuesta.respuesta in ['SI_CUMPLE', 'CUMPLE_PARCIAL']:
            if respuesta.nivel_madurez == 0:
                raise serializers.ValidationError({
                    'nivel_madurez': 'Debes indicar un nivel de madurez mayor a 0 si cumples total o parcialmente'
                })
        
        return attrs
    
    def save(self):
        """Enviar respuesta"""
        respuesta = self.instance
        request = self.context.get('request')
        
        with transaction.atomic():
            respuesta.estado = 'enviado'
            respuesta.save()
            
            HistorialRespuesta.objects.create(
                respuesta=respuesta,
                tipo_cambio='modificacion_respuesta',
                usuario=request.user if request else None,
                valor_anterior_respuesta='borrador',
                valor_nuevo_respuesta='enviado',
                motivo='Respuesta enviada por el usuario',
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request)
            )
            
            return respuesta
    
    def _get_client_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _get_user_agent(self, request):
        if not request:
            return ''
        return request.META.get('HTTP_USER_AGENT', '')[:255]



class RespuestaModificarAdminSerializer(serializers.ModelSerializer):
    """Serializer para que el Administrador modifique respuestas del usuario"""
    
    motivo_modificacion = serializers.CharField(
        write_only=True,
        required=True,
        min_length=10,
        help_text='Motivo de la modificación (mínimo 10 caracteres)'
    )
    
    class Meta:
        model = Respuesta
        fields = [
            'respuesta', 'justificacion', 'comentarios_adicionales',
            # ⭐ CAMPOS DE NIVEL DE MADUREZ
            'nivel_madurez', 'justificacion_madurez',
            'motivo_modificacion'
        ]
        extra_kwargs = {
            'justificacion_madurez': {
                'required': False,  # ⭐ OPCIONAL
                'allow_blank': True  # ⭐ PUEDE ESTAR VACÍO
            }
        }
    
    def validate(self, attrs):
        """Validaciones para admin"""
        request = self.context.get('request')
        
        if not request or request.user.rol not in ['administrador', 'superadmin']:
            raise serializers.ValidationError({
                'permiso': 'Solo administradores pueden modificar respuestas'
            })
        
        if self.instance.estado not in ['enviado', 'modificado_admin']:
            raise serializers.ValidationError({
                'estado': 'Solo se pueden modificar respuestas enviadas'
            })
        
        # ⭐ SIN VALIDACIONES DE justificacion_madurez
        # El admin puede modificar el nivel sin necesidad de justificarlo
        
        return attrs
    
    def update(self, instance, validated_data):
        """Modificar respuesta con auditoría completa"""
        request = self.context.get('request')
        motivo = validated_data.pop('motivo_modificacion')
        
        with transaction.atomic():
            valor_anterior_respuesta = instance.respuesta
            valor_anterior_justificacion = instance.justificacion
            valor_anterior_comentarios = instance.comentarios_adicionales
            
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.estado = 'modificado_admin'
            instance.modificado_por = request.user
            instance.modificado_at = timezone.now()
            instance.version += 1
            instance.save()
            
            HistorialRespuesta.objects.create(
                respuesta=instance,
                tipo_cambio='modificacion_respuesta',
                usuario=request.user,
                valor_anterior_respuesta=valor_anterior_respuesta,
                valor_anterior_justificacion=valor_anterior_justificacion,
                valor_anterior_comentarios=valor_anterior_comentarios,
                valor_nuevo_respuesta=instance.respuesta,
                valor_nuevo_justificacion=instance.justificacion,
                valor_nuevo_comentarios=instance.comentarios_adicionales,
                motivo=f'Modificación por administrador: {motivo}',
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request)
            )
            
            return instance
    
    def _get_client_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _get_user_agent(self, request):
        if not request:
            return ''
        return request.META.get('HTTP_USER_AGENT', '')[:255]


# ============================================
# SERIALIZERS DE CÁLCULO DE NIVEL
# ============================================

class CalculoNivelSerializer(serializers.ModelSerializer):
    """Serializer para cálculos de nivel de madurez"""
    asignacion_id = serializers.UUIDField(source='asignacion.id', read_only=True)
    dimension_id = serializers.UUIDField(source='dimension.id', read_only=True)
    
    dimension_nombre = serializers.CharField(source='dimension.nombre', read_only=True)
    dimension_codigo = serializers.CharField(source='dimension.codigo', read_only=True)
    clasificacion_gap_display = serializers.CharField(
        source='get_clasificacion_gap_display',
        read_only=True
    )
    
    class Meta:
        model = CalculoNivel
        fields = [
            'id', 
            'asignacion_id', 
            'dimension_id', 
            'dimension_nombre', 
            'dimension_codigo',
            'nivel_actual', 
            'nivel_deseado', 
            'gap',
            'total_preguntas', 
            'respuestas_si_cumple', 
            'respuestas_cumple_parcial', 
            'respuestas_no_cumple', 
            'respuestas_no_aplica',
            'respuestas_yes', 
            'respuestas_no', 
            'respuestas_na',
            'porcentaje_cumplimiento', 
            'clasificacion_gap', 
            'clasificacion_gap_display',
            'calculado_at'
        ]
        read_only_fields = ['id', 'calculado_at']
        depth = 0

