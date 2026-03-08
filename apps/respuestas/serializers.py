# apps/respuestas/serializers.py

import os
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from .models import (
    Respuesta,
    HistorialRespuesta,
    Evidencia,
    CalculoNivel,
)
# Importamos TipoDocumento desde documentos para asegurar consistencia
from apps.documentos.models import TipoDocumento
from apps.documentos.serializers import DocumentoSerializer 
from apps.encuestas.models import Pregunta, Dimension
from apps.asignaciones.models import Asignacion
from apps.usuarios.models import Usuario


# ============================================
# UTILITY FUNCTIONS
# ============================================

def _get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request):
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:255]



# ============================================
# UTILITY FUNCTIONS
# ============================================

def _get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request):
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:255]


# ============================================
# SERIALIZERS DE TIPOS DE DOCUMENTO
# ============================================

class TipoDocumentoSerializer(serializers.ModelSerializer):
    """Serializer para tipos de documento"""
    
    class Meta:
        model = TipoDocumento
        fields = [
            'id', 'empresa', 'nombre', 'descripcion', 
            'requiere_fecha', 'activo',
            # Campos nuevos del módulo
            'abreviatura', 'nivel_jerarquico', 'categoria', 
            'requiere_word_y_pdf'
            # 'configuracion_campos' <- ELIMINADO porque no existe en el modelo actual
        ]
        read_only_fields = ['id']


class TipoDocumentoListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    
    class Meta:
        model = TipoDocumento
        fields = ['id', 'nombre', 'descripcion', 'abreviatura']


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

    documento_oficial_detalle = DocumentoSerializer(
        source='documento_oficial', 
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
            # Auditoría
            'subido_por', 
            'subido_por_nombre',
            'fecha_creacion', 
            'activo',
            'documento_oficial',          # Para enviar el ID desde el front
            'documento_oficial_detalle', # Para ver los datos del doc en el front
        ]
        read_only_fields = [
            'id', 
            'nombre_archivo_original', 
            'tamanio_bytes',
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
    Maneja la subida de archivos a Supabase O la vinculación
    """
    
    # Campos requeridos
    respuesta_id = serializers.UUIDField(required=True)
    
    # Opcional: Archivo físico
    archivo = serializers.FileField(required=False)

    # Opcional: ID del documento maestro (Vinculación)
    documento_id = serializers.UUIDField(required=False, allow_null=True)
    
    # Metadatos del documento
    # ⭐ CORRECCIÓN: required=False para permitir que vengan vacíos si se está vinculando
    codigo_documento = serializers.CharField(
        max_length=50,
        required=False, 
        help_text='Código único del documento (ej: POL-SEG-001)'
    )
    tipo_documento_enum = serializers.ChoiceField(
        choices=Evidencia.TIPOS_DOCUMENTO_CHOICES,
        default='otro'
    )
    titulo_documento = serializers.CharField(
        max_length=60,
        required=False,
        default='Documento sin título'
    )
    objetivo_documento = serializers.CharField(
        max_length=180,
        required=False,
        default='Sin objetivo especificado'
    )
    
    def validate_codigo_documento(self, value):
        """Validar código de documento si viene"""
        if value:
            return value.strip().upper()
        return value
    
    def validate_archivo(self, value):
        """
        ⭐ VALIDAR ARCHIVO ANTES DE SUBIRLO
        """
        if not value:
            return value

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
        """Validaciones adicionales lógicas"""
        archivo = attrs.get('archivo')
        documento_id = attrs.get('documento_id')
        codigo_documento = attrs.get('codigo_documento')
        titulo_documento = attrs.get('titulo_documento')

        # CASO 1: Si NO hay archivo Y NO hay documento_id -> Error
        if not archivo and not documento_id:
            raise serializers.ValidationError({
                'archivo': 'Debe subir un archivo nuevo o seleccionar un documento existente del Maestro de Documentos.'
            })
        
        # CASO 2: Si es subida manual (NO hay documento_id), validamos campos de texto
        if not documento_id:
            if not codigo_documento:
                raise serializers.ValidationError({'codigo_documento': 'El código de documento es obligatorio para subidas manuales.'})
            
            # Validar título si es subida manual
            if not titulo_documento or titulo_documento.strip() == 'Documento sin título':
                 # Si el usuario no mandó título, podríamos dejarlo pasar o exigir
                 pass 
        
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
    
    ip_address = serializers.CharField(read_only=True)
    
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
    pregunta_codigo       = serializers.CharField(source='pregunta.codigo',  read_only=True)
    pregunta_texto        = serializers.CharField(source='pregunta.texto',   read_only=True)
    estado_display        = serializers.CharField(source='get_estado_display', read_only=True)
    respondido_por_nombre = serializers.CharField(source='respondido_por.nombre_completo', read_only=True)
    auditado_por_nombre   = serializers.CharField(source='auditado_por.nombre_completo',   read_only=True)
    total_evidencias      = serializers.SerializerMethodField()

    # El usuario ya no tiene "respuesta_display" con SI/NO, sino calificacion_auditor
    calificacion_display  = serializers.CharField(
        source='get_calificacion_auditor_display', read_only=True
    )

    class Meta:
        model = Respuesta
        fields = [
            'id', 'asignacion', 'pregunta', 'pregunta_codigo', 'pregunta_texto',
            # Respuesta del usuario
            'respuesta', 'justificacion',
            # Calificación del auditor
            'calificacion_auditor', 'calificacion_display',
            'comentarios_auditor', 'recomendaciones_auditor', 'fecha_auditoria',
            'auditado_por', 'auditado_por_nombre',
            # Nivel
            'nivel_madurez',
            # Estado y auditoría
            'estado', 'estado_display',
            'respondido_por', 'respondido_por_nombre', 'respondido_at',
            'total_evidencias', 'version'
        ]

    def get_total_evidencias(self, obj):
        return obj.evidencias.filter(activo=True).count()


class RespuestaDetailSerializer(serializers.ModelSerializer):
    from .serializers import EvidenciaSerializer, HistorialRespuestaSerializer  # evitar circular

    pregunta_codigo       = serializers.CharField(source='pregunta.codigo', read_only=True)
    pregunta_texto        = serializers.CharField(source='pregunta.texto',  read_only=True)
    estado_display        = serializers.CharField(source='get_estado_display', read_only=True)
    respondido_por_nombre = serializers.CharField(source='respondido_por.nombre_completo', read_only=True)
    modificado_por_nombre = serializers.CharField(source='modificado_por.nombre_completo', read_only=True)
    auditado_por_nombre   = serializers.CharField(source='auditado_por.nombre_completo',   read_only=True)
    calificacion_display  = serializers.CharField(
        source='get_calificacion_auditor_display', read_only=True
    )

    # Relaciones anidadas — se importan inline para evitar circulares
    evidencias = serializers.SerializerMethodField()
    historial  = serializers.SerializerMethodField()

    class Meta:
        model = Respuesta
        fields = [
            'id', 'asignacion', 'pregunta', 'pregunta_codigo', 'pregunta_texto',
            'respuesta', 'justificacion', 'comentarios_adicionales',
            'calificacion_auditor', 'calificacion_display',
            'comentarios_auditor', 'recomendaciones_auditor',
            'fecha_auditoria', 'auditado_por', 'auditado_por_nombre',
            'nivel_madurez',
            'estado', 'estado_display',
            'respondido_por', 'respondido_por_nombre', 'respondido_at',
            'modificado_por', 'modificado_por_nombre', 'modificado_at',
            'version', 'evidencias', 'historial'
        ]

    def get_evidencias(self, obj):
        from .serializers import EvidenciaSerializer
        return EvidenciaSerializer(obj.evidencias.filter(activo=True), many=True).data

    def get_historial(self, obj):
        from .serializers import HistorialRespuestaSerializer
        return HistorialRespuestaSerializer(obj.historial.all(), many=True).data




class RespuestaCreateSerializer(serializers.ModelSerializer):
    """
    El usuario crea una respuesta.
    Solo puede marcar NO_APLICA (con justificación) o dejar respuesta=null
    y subir evidencias. Las evidencias son siempre obligatorias excepto
    cuando marca NO_APLICA.
    """

    respuesta = serializers.ChoiceField(
        choices=Respuesta.OPCIONES_RESPUESTA,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Respuesta
        fields = [
            'asignacion', 'pregunta',
            'respuesta',           # null o 'NO_APLICA'
            'justificacion',       # obligatorio siempre ≥10 chars
            'comentarios_adicionales',
        ]

    def validate_respuesta(self, value):
        # ⭐ Ahora el usuario puede marcar NO_APLICA o NO_CUMPLE (respuesta "No")
        if value is not None and value not in ['NO_APLICA', 'NO_CUMPLE']:
            raise serializers.ValidationError(
                'Solo puedes marcar "No Aplica" o "No". '
                'SI_CUMPLE y CUMPLE_PARCIAL los asigna el Auditor.'
            )
        return value

    def validate(self, attrs):
        asignacion = attrs.get('asignacion')
        pregunta   = attrs.get('pregunta')
        respuesta  = attrs.get('respuesta')
        justificacion = attrs.get('justificacion', '')
        estado = 'borrador'

        # Pregunta debe pertenecer a la dimensión de la asignación
        if pregunta.dimension != asignacion.dimension:
            raise serializers.ValidationError({
                'pregunta': 'La pregunta no pertenece a la dimensión de esta asignación'
            })

        # No duplicar respuesta
        if Respuesta.objects.filter(asignacion=asignacion, pregunta=pregunta).exists():
            raise serializers.ValidationError({
                'pregunta': 'Ya existe una respuesta para esta pregunta'
            })

        # Justificación siempre requerida
        if len(justificacion.strip()) < 10:
            raise serializers.ValidationError({
                'justificacion': 'La justificación debe tener al menos 10 caracteres'
            })

        # Solo en estados finales se exige respuesta no nula.
        if estado != 'borrador' and respuesta is None:
            raise serializers.ValidationError({
                'respuesta': 'La respuesta es obligatoria cuando no está en borrador.'
            })

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        with transaction.atomic():
            validated_data['respondido_por'] = request.user if request else None
            validated_data['estado']  = 'borrador'
            validated_data['version'] = 1

            respuesta = Respuesta.objects.create(**validated_data)

            HistorialRespuesta.objects.create(
                respuesta=respuesta,
                tipo_cambio='creacion',
                usuario=request.user if request else None,
                valor_nuevo_justificacion=respuesta.justificacion,
                motivo='Creación inicial de respuesta',
                ip_address=_get_client_ip(request),
                user_agent=_get_user_agent(request),
            )
            return respuesta



class RespuestaUpdateSerializer(serializers.ModelSerializer):
    """Solo se puede editar en estado borrador."""

    respuesta = serializers.ChoiceField(
        choices=Respuesta.OPCIONES_RESPUESTA,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Respuesta
        fields = ['respuesta', 'justificacion', 'comentarios_adicionales']

    def validate_respuesta(self, value):
        if value is not None and value not in ['NO_APLICA', 'NO_CUMPLE']:
            raise serializers.ValidationError(
                'Solo puedes marcar "No Aplica" o "No".'
            )
        return value

    def validate(self, attrs):
        # En guardado parcial desde frontend siempre se fuerza borrador.
        estado = 'borrador'
        respuesta = attrs.get('respuesta', self.instance.respuesta)
        justificacion = attrs.get('justificacion', self.instance.justificacion)

        if estado != 'borrador' and respuesta is None:
            raise serializers.ValidationError({
                'respuesta': 'La respuesta es obligatoria cuando no está en borrador.'
            })

        if len(justificacion.strip()) < 10:
            raise serializers.ValidationError({
                'justificacion': 'La justificación debe tener al menos 10 caracteres'
            })
        return attrs

    def update(self, instance, validated_data):
        request = self.context.get('request')
        with transaction.atomic():
            valor_anterior_justificacion = instance.justificacion
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            # Guardado parcial: siempre vuelve a borrador.
            instance.estado = 'borrador'
            instance.save()

            HistorialRespuesta.objects.create(
                respuesta=instance,
                tipo_cambio='modificacion_respuesta',
                usuario=request.user if request else None,
                valor_anterior_justificacion=valor_anterior_justificacion,
                valor_nuevo_justificacion=instance.justificacion,
                motivo='Actualización por el usuario',
                ip_address=_get_client_ip(request),
                user_agent=_get_user_agent(request),
            )
            return instance


class RespuestaEnviarSerializer(serializers.Serializer):
    """
    Marcar respuesta como enviada.
    Validación: si respuesta != NO_APLICA, debe tener al menos 1 evidencia.
    """

    def validate(self, attrs):
        respuesta = self.instance

        if respuesta.estado != 'borrador':
            raise serializers.ValidationError({
                'estado': 'Solo se pueden enviar respuestas en estado borrador'
            })

        tiene_evidencias = respuesta.evidencias.filter(activo=True).exists()

        # Flujo SI: respuesta puede ser null, pero debe tener evidencias.
        if respuesta.respuesta is None and not tiene_evidencias:
            raise serializers.ValidationError({
                'evidencias': 'Para enviar con respuesta vacía (flujo SI), debes subir al menos una evidencia.'
            })

        # Para respuestas distintas de NO_APLICA/NO_CUMPLE también exigimos evidencia.
        if respuesta.respuesta not in [None, 'NO_APLICA', 'NO_CUMPLE'] and not tiene_evidencias:
            raise serializers.ValidationError({
                'evidencias': 'Debes subir al menos una evidencia antes de enviar'
            })

        return attrs

    def save(self):
        respuesta = self.instance
        request   = self.context.get('request')
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
                ip_address=_get_client_ip(request),
                user_agent=_get_user_agent(request),
            )
            return respuesta
    
        
class AuditorCalificarSerializer(serializers.ModelSerializer):
    """
    El Auditor califica UNA respuesta individual.
    Solo puede hacerlo si la asignación está en 'pendiente_auditoria'.
    """

    class Meta:
        model = Respuesta
        fields = [
            'calificacion_auditor',   # SI_CUMPLE / CUMPLE_PARCIAL / NO_CUMPLE
            'comentarios_auditor',
            'recomendaciones_auditor',
            'nivel_madurez',
        ]

    def validate_calificacion_auditor(self, value):
        opciones = [c[0] for c in Respuesta.CALIFICACIONES_AUDITOR]
        if value not in opciones:
            raise serializers.ValidationError(
                f'Calificación inválida. Opciones: {", ".join(opciones)}'
            )
        return value

    def validate(self, attrs):
        request       = self.context.get('request')
        calificacion  = attrs.get('calificacion_auditor', self.instance.calificacion_auditor)
        nivel_madurez = attrs.get('nivel_madurez', self.instance.nivel_madurez)

        # Solo auditores de la misma empresa
        if not request or request.user.rol != 'auditor':
            raise serializers.ValidationError(
                'Solo el Auditor puede calificar respuestas'
            )

        if self.instance.asignacion.empresa != request.user.empresa:
            raise serializers.ValidationError(
                'No puedes calificar respuestas de otra empresa'
            )

        # La asignación debe estar en pendiente_auditoria     
        # Agregar 'auditado' a estados permitidos
        if self.instance.asignacion.estado not in ['completado', 'pendiente_auditoria', 'auditado']:
            raise serializers.ValidationError(
                'La asignación no está disponible para auditoría'
            )

        # ⭐ No calificar NO_APLICA (también está en el view pero doble seguro)
        if self.instance.respuesta == 'NO_APLICA':
            raise serializers.ValidationError(
                'Las respuestas No Aplica no pueden ser calificadas'
            )

        # Nivel de madurez: NO_CUMPLE → 0
        if calificacion == 'NO_CUMPLE' and nivel_madurez != 0:
            raise serializers.ValidationError({
                'nivel_madurez': 'Para NO_CUMPLE el nivel de madurez debe ser 0'
            })

        # Nivel múltiplo de 0.5
        if (nivel_madurez * 2) % 1 != 0:
            raise serializers.ValidationError({
                'nivel_madurez': 'El nivel de madurez debe ser múltiplo de 0.5'
            })

        return attrs

    def update(self, instance, validated_data):
        request = self.context.get('request')
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.auditado_por   = request.user
            instance.fecha_auditoria = timezone.now()
            instance.estado         = 'auditado'
            # Evitar full_clean al guardar directamente
            super(Respuesta, instance).save()

            HistorialRespuesta.objects.create(
                respuesta=instance,
                tipo_cambio='modificacion_respuesta',
                usuario=request.user,
                valor_nuevo_respuesta=instance.calificacion_auditor,
                motivo=f'Calificado por auditor: {instance.calificacion_auditor}',
                ip_address=_get_client_ip(request),
                user_agent=_get_user_agent(request),
            )
            return instance
        

class AuditorCerrarRevisionSerializer(serializers.Serializer):
    """
    El Auditor cierra la revisión de una asignación completa.

    Lógica al cerrar:
    1. Todas las respuestas que quedaron sin calificar → NO_CUMPLE automático.
    2. Estado de la asignación → 'completado'.
    3. Se calcula el GAP automáticamente.
    4. Se notifica al administrador / usuario.
    """
    comentario_cierre = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Comentario general del auditor al cerrar la revisión'
    )

    def validate(self, attrs):
        request    = self.context.get('request')
        asignacion = self.context.get('asignacion')

        if not request or request.user.rol != 'auditor':
            raise serializers.ValidationError(
                'Solo el Auditor puede cerrar revisiones'
            )
        if asignacion.empresa != request.user.empresa:
            raise serializers.ValidationError(
                'No puedes cerrar revisiones de otra empresa'
            )
        if asignacion.estado not in ['completado', 'pendiente_auditoria']:
            raise serializers.ValidationError(
                'La asignación no está disponible para cerrar revisión'
            )
        return attrs

    def save(self):
        request           = self.context.get('request')
        asignacion        = self.context.get('asignacion')
        comentario_cierre = self.validated_data.get('comentario_cierre', '')

        with transaction.atomic():
            # 1. Marcar sin calificar → NO_CUMPLE automático
            respuestas_pendientes = asignacion.respuestas.filter(
                estado__in=['enviado', 'pendiente_auditoria'],
                calificacion_auditor__isnull=True,
                activo=True
            ).exclude(respuesta__in=['NO_APLICA', 'NO_CUMPLE'])

            # ⭐ Marcar NO_CUMPLE del usuario como auditadas automáticamente
            respuestas_no_cumple_usuario = asignacion.respuestas.filter(
                estado__in=['enviado', 'pendiente_auditoria'],
                respuesta='NO_CUMPLE',
                calificacion_auditor__isnull=True,
                activo=True
            )
            for resp in respuestas_no_cumple_usuario:
                resp.calificacion_auditor = 'NO_CUMPLE'
                resp.nivel_madurez = 0.0
                resp.comentarios_auditor = 'Usuario respondió No — confirmado automáticamente.'
                resp.estado = 'auditado'
                resp.fecha_auditoria = timezone.now()
                super(Respuesta, resp).save()
    
            pendientes_count = respuestas_pendientes.count()

            for resp in respuestas_pendientes:
                resp.marcar_no_cumple_automatico()

            # 2. Actualizar estado de la asignación
            asignacion.estado           = 'auditado'
            asignacion.fecha_completado = timezone.now()
            if comentario_cierre:
                asignacion.observaciones += f'\n[AUDITOR] {comentario_cierre}'
            asignacion.save()

            # 3. Calcular GAP
            gap_info = None
            try:
                from apps.respuestas.services import CalculoNivelService
                calculo  = CalculoNivelService.calcular_gap_asignacion(asignacion)
                gap_info = {
                    'nivel_deseado':           float(calculo.nivel_deseado),
                    'nivel_actual':            float(calculo.nivel_actual),
                    'gap':                     float(calculo.gap),
                    'clasificacion':           calculo.get_clasificacion_gap_display(),
                    'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
                }
            except Exception as e:
                print(f'⚠️  Error al calcular GAP: {e}')

            # 4. Actualizar progreso de la evaluación
            if asignacion.evaluacion_empresa_id:
                try:
                    asignacion.evaluacion_empresa.actualizar_progreso()
                except Exception as e:
                    print(f'⚠️  Error al actualizar progreso: {e}')

            # 5. Notificar al administrador y al usuario
            try:
                from apps.notificaciones.services import NotificacionAsignacionService
                NotificacionAsignacionService.notificar_revision_completada(
                    asignacion=asignacion,
                    auditado_por=request.user,
                    gap_info=gap_info,
                )
            except Exception as e:
                print(f'⚠️  Error al enviar notificación de cierre: {e}')

            return {
                'asignacion_id':      str(asignacion.id),
                'estado':             asignacion.estado,
                'gap_info':           gap_info,
                'pendientes_auto_nc': pendientes_count,
            }


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
            'porcentaje_cumplimiento', 
            'clasificacion_gap', 
            'clasificacion_gap_display',
            'calculado_at'
        ]
        read_only_fields = ['id', 'calculado_at']
        depth = 0