# apps/notificaciones/serializers.py
from rest_framework import serializers
from .models import Notificacion, PlantillaNotificacion
from apps.usuarios.models import Usuario
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

class UsuarioNotificacionSerializer(serializers.ModelSerializer):
    """Serializer simplificado de usuario para notificaciones"""
    
    # Usamos nombre_completo que ya tienes definido como @property en el modelo
    nombre_completo = serializers.ReadOnlyField() 
    
    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'apellido', 'nombre_completo', 'rol']
        read_only_fields = fields

    # Esto quita el Warning amarillo de la consola
    @extend_schema_field(OpenApiTypes.STR)
    def get_nombre_completo(self, obj):
        return obj.nombre_completo


class NotificacionDetalleSerializer(serializers.ModelSerializer):
    """
    Serializer COMPLETO para ver TODOS los detalles de una notificación
    Usado en: GET /api/notificaciones/{id}/
    """
    # Información del usuario
    usuario = UsuarioNotificacionSerializer(read_only=True)
    
    # Displays de choices
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    
    # Tiempo transcurrido
    tiempo_transcurrido = serializers.SerializerMethodField()
    
    # Información de la asignación relacionada (si existe)
    asignacion_info = serializers.SerializerMethodField()
    
    # Metadata adicional
    puede_marcar_leida = serializers.SerializerMethodField()
    dias_desde_creacion = serializers.SerializerMethodField()
    
    class Meta:
        model = Notificacion
        fields = [
            # IDs
            'id',
            
            # Usuario
            'usuario',
            
            # Tipo y contenido
            'tipo',
            'tipo_display',
            'titulo',
            'mensaje',
            
            # Prioridad
            'prioridad',
            'prioridad_display',
            
            # Estado
            'leida',
            'fecha_leida',
            'email_enviado',
            
            # Acción
            'url_accion',
            
            # Datos adicionales
            'datos_adicionales',
            'asignacion_info',
            
            # Timestamps
            'fecha_creacion',
            'fecha_actualizacion',
            'tiempo_transcurrido',
            'dias_desde_creacion',
            
            # Estado
            'activo',
            'puede_marcar_leida',
        ]
        read_only_fields = fields
    
    def get_tiempo_transcurrido(self, obj):
        """Calcula tiempo transcurrido desde la creación de forma legible"""
        from django.utils import timezone
        from datetime import timedelta
        
        delta = timezone.now() - obj.fecha_creacion
        
        if delta < timedelta(minutes=1):
            return "Hace un momento"
        elif delta < timedelta(hours=1):
            minutos = int(delta.total_seconds() / 60)
            return f"Hace {minutos} minuto{'s' if minutos > 1 else ''}"
        elif delta < timedelta(days=1):
            horas = int(delta.total_seconds() / 3600)
            return f"Hace {horas} hora{'s' if horas > 1 else ''}"
        elif delta < timedelta(days=7):
            dias = delta.days
            return f"Hace {dias} día{'s' if dias > 1 else ''}"
        elif delta < timedelta(days=30):
            semanas = delta.days // 7
            return f"Hace {semanas} semana{'s' if semanas > 1 else ''}"
        else:
            return obj.fecha_creacion.strftime('%d/%m/%Y %H:%M')
    
    def get_dias_desde_creacion(self, obj):
        """Retorna días exactos desde la creación"""
        from django.utils import timezone
        delta = timezone.now() - obj.fecha_creacion
        return delta.days
    
    def get_puede_marcar_leida(self, obj):
        """Indica si la notificación puede marcarse como leída"""
        return not obj.leida and obj.activo
    
    def get_asignacion_info(self, obj):
        """
        Obtiene información detallada de la asignación relacionada
        (si existe en datos_adicionales)
        """
        # 1. Validación inicial de seguridad
        if not obj or not obj.datos_adicionales:
            return None
        
        # 2. Extraer el ID
        asignacion_id = obj.datos_adicionales.get('asignacion_id')
        if not asignacion_id:
            return None
        
        try:
            from apps.asignaciones.models import Asignacion
            # 3. Consulta a la base de datos
            asignacion = Asignacion.objects.select_related(
                'encuesta',
                'dimension',
                'usuario_asignado',
                'asignado_por'
            ).filter(id=asignacion_id).first() # .first() es más seguro que .get() para evitar errores si no existe
            
            if not asignacion:
                return {'id': asignacion_id, 'error': 'Asignación no encontrada'}
            
            # Información básica de la asignación
            info = {
                'id': str(asignacion.id),
                'tipo': 'evaluacion_completa' if not asignacion.dimension else 'dimension',
                'estado': asignacion.estado,
                'fecha_limite': asignacion.fecha_limite.strftime('%Y-%m-%d'),
                'dias_restantes': asignacion.dias_restantes,
                'esta_vencido': asignacion.esta_vencido,
                'progreso': f"{asignacion.porcentaje_completado}%",
                
                # Encuesta
                'encuesta': {
                    'id': str(asignacion.encuesta.id),
                    'nombre': asignacion.encuesta.nombre,
                    'descripcion': asignacion.encuesta.descripcion,
                },
                
                # Usuario asignado
                'asignado_a': {
                    'id': str(asignacion.usuario_asignado.id),
                    'nombre': asignacion.usuario_asignado.nombre_completo,
                    'email': asignacion.usuario_asignado.email,
                },
                
                # Usuario que asignó
                'asignado_por': {
                    'id': str(asignacion.asignado_por.id),
                    'nombre': asignacion.asignado_por.nombre_completo,
                } if asignacion.asignado_por else None,
            }
            
            # Si es dimensión específica, agregar info de la dimensión
            if asignacion.dimension:
                info['dimension'] = {
                    'id': str(asignacion.dimension.id),
                    'nombre': asignacion.dimension.nombre,
                    'descripcion': asignacion.dimension.descripcion,
                    'total_preguntas': asignacion.dimension.total_preguntas,
                }
            else:
                # Si es evaluación completa, agregar total de dimensiones
                info['total_dimensiones'] = asignacion.encuesta.total_dimensiones
                info['total_preguntas'] = asignacion.total_preguntas
            
            return info
            
        except Exception as e:
            # Si hay error al obtener la asignación, retornar solo el ID
            return {
                'id': asignacion_id,
                'error': 'No se pudo obtener información de la asignación'
            }


class NotificacionSerializer(serializers.ModelSerializer):
    """Serializer completo para notificaciones (ORIGINAL)"""
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    tiempo_transcurrido = serializers.SerializerMethodField()
    
    class Meta:
        model = Notificacion
        fields = [
            'id', 'tipo', 'tipo_display', 'titulo', 'mensaje',
            'prioridad', 'prioridad_display', 'leida', 'fecha_leida',
            'email_enviado', 'url_accion', 'datos_adicionales',
            'tiempo_transcurrido', 'fecha_creacion'
        ]
        read_only_fields = [
            'id', 'tipo', 'titulo', 'mensaje', 'prioridad',
            'email_enviado', 'fecha_creacion'
        ]
    
    def get_tiempo_transcurrido(self, obj):
        """Calcula tiempo transcurrido desde la creación"""
        from django.utils import timezone
        from datetime import timedelta
        
        delta = timezone.now() - obj.fecha_creacion
        
        if delta < timedelta(minutes=1):
            return "Hace un momento"
        elif delta < timedelta(hours=1):
            minutos = int(delta.total_seconds() / 60)
            return f"Hace {minutos} minuto{'s' if minutos > 1 else ''}"
        elif delta < timedelta(days=1):
            horas = int(delta.total_seconds() / 3600)
            return f"Hace {horas} hora{'s' if horas > 1 else ''}"
        elif delta < timedelta(days=7):
            dias = delta.days
            return f"Hace {dias} día{'s' if dias > 1 else ''}"
        else:
            return obj.fecha_creacion.strftime('%d/%m/%Y')


class NotificacionListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado"""
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    tiempo_transcurrido = serializers.SerializerMethodField()
    
    class Meta:
        model = Notificacion
        fields = [
            'id', 'tipo', 'tipo_display', 'titulo', 'prioridad',
            'leida', 'url_accion', 'tiempo_transcurrido', 'fecha_creacion'
        ]
    
    def get_tiempo_transcurrido(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        
        delta = timezone.now() - obj.fecha_creacion
        
        if delta < timedelta(minutes=1):
            return "Hace un momento"
        elif delta < timedelta(hours=1):
            minutos = int(delta.total_seconds() / 60)
            return f"Hace {minutos}m"
        elif delta < timedelta(days=1):
            horas = int(delta.total_seconds() / 3600)
            return f"Hace {horas}h"
        elif delta < timedelta(days=7):
            return f"Hace {delta.days}d"
        else:
            return obj.fecha_creacion.strftime('%d/%m/%Y')


class MarcarLeidaSerializer(serializers.Serializer):
    """Serializer para marcar notificaciones como leídas"""
    notificacion_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text='Lista de IDs de notificaciones a marcar como leídas (vacío = todas)'
    )


class PlantillaNotificacionSerializer(serializers.ModelSerializer):
    """Serializer para plantillas de notificaciones"""
    
    class Meta:
        model = PlantillaNotificacion
        fields = [
            'id', 'tipo', 'nombre', 'titulo_plantilla', 'mensaje_plantilla',
            'asunto_email', 'cuerpo_email', 'enviar_email',
            'prioridad_default', 'activo', 'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['id', 'fecha_creacion', 'fecha_actualizacion']
        
# ═══════════════════════════════════════════════════════════════
# SERIALIZERS PARA ENVÍO DE NOTIFICACIONES PERSONALIZADAS ⭐
# ═══════════════════════════════════════════════════════════════

class EnviarNotificacionSerializer(serializers.Serializer):
    """
    Serializer para enviar notificaciones personalizadas
    
    SuperAdmin puede enviar a:
    - Un usuario específico
    - Todos los usuarios de una empresa
    - Todos los administradores
    - Todos los usuarios
    
    Administrador puede enviar a:
    - Usuarios de su propia empresa
    """
    
    # Destinatarios (al menos uno requerido)
    usuario_id = serializers.IntegerField(
        required=False,
        help_text='ID del usuario destinatario (individual)'
    )
    empresa_id = serializers.IntegerField(
        required=False,
        help_text='ID de la empresa (todos los usuarios de esa empresa)'
    )
    enviar_a_todos_admins = serializers.BooleanField(
        default=False,
        help_text='Enviar a todos los administradores del sistema'
    )
    enviar_a_todos = serializers.BooleanField(
        default=False,
        help_text='Enviar a todos los usuarios (solo SuperAdmin)'
    )
    
    # Contenido
    tipo = serializers.ChoiceField(
        choices=[
            ('mensaje_personalizado', 'Mensaje Personalizado'),
            ('anuncio', 'Anuncio'),
            ('sistema', 'Sistema'),
        ],
        default='mensaje_personalizado'
    )
    titulo = serializers.CharField(
        max_length=255,
        help_text='Título de la notificación'
    )
    mensaje = serializers.CharField(
        help_text='Mensaje completo de la notificación'
    )
    
    # Opcionales
    prioridad = serializers.ChoiceField(
        choices=Notificacion.PRIORIDADES,
        default='normal'
    )
    url_accion = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text='URL a la que redirigir (puede ser deep link para móvil)'
    )
    enviar_email = serializers.BooleanField(
        default=True,
        help_text='Si debe enviar email además de notificación interna'
    )
    
    def validate(self, data):
        """Validar que al menos un destinatario esté especificado"""
        tiene_destinatario = any([
            data.get('usuario_id'),
            data.get('empresa_id'),
            data.get('enviar_a_todos_admins'),
            data.get('enviar_a_todos')
        ])
        
        if not tiene_destinatario:
            raise serializers.ValidationError(
                'Debe especificar al menos un destinatario: '
                'usuario_id, empresa_id, enviar_a_todos_admins o enviar_a_todos'
            )
        
        return data


class HistorialNotificacionesSerializer(serializers.Serializer):
    """
    Serializer para obtener historial de notificaciones
    """
    periodo = serializers.ChoiceField(
        choices=[
            ('nuevas', 'Nuevas (no leídas)'),
            ('semana', 'Última semana'),
            ('mes', 'Último mes'),
            ('todas', 'Todas'),
        ],
        default='nuevas'
    )
    limite = serializers.IntegerField(
        default=50,
        min_value=1,
        max_value=200
    )