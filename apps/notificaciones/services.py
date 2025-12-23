# apps/notificaciones/services.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Notificacion, PlantillaNotificacion
from apps.usuarios.models import Usuario
import logging

logger = logging.getLogger(__name__)


class NotificacionService:
    """
    Servicio centralizado para crear y enviar notificaciones
    Soporta notificaciones internas y emails
    """
    
    @staticmethod
    def crear_notificacion(
        usuario,
        tipo,
        titulo,
        mensaje,
        prioridad='normal',
        url_accion='',
        datos_adicionales=None,
        enviar_email=True
    ):
        """
        Crea una notificación interna y opcionalmente envía email
        
        Args:
            usuario: Usuario que recibe la notificación
            tipo: Tipo de notificación (ver Notificacion.TIPOS)
            titulo: Título de la notificación
            mensaje: Mensaje de la notificación
            prioridad: Prioridad (baja, normal, alta, urgente)
            url_accion: URL opcional para redirección
            datos_adicionales: Dict con metadata adicional
            enviar_email: Si debe enviar email
        
        Returns:
            Notificacion: Objeto notificación creado
        """
        try:
            # Crear notificación interna
            notificacion = Notificacion.objects.create(
                usuario=usuario,
                tipo=tipo,
                titulo=titulo,
                mensaje=mensaje,
                prioridad=prioridad,
                url_accion=url_accion,
                datos_adicionales=datos_adicionales or {},
                leida=False,
                email_enviado=False
            )
            
            logger.info(f"Notificación creada: {notificacion.id} para {usuario.email}")
            
            # Enviar email si está habilitado
            if enviar_email and usuario.email:
                NotificacionService.enviar_email(notificacion)
            
            return notificacion
            
        except Exception as e:
            logger.error(f"Error al crear notificación: {str(e)}")
            raise
    
    @staticmethod
    def crear_desde_plantilla(
        usuario,
        tipo_plantilla,
        contexto,
        prioridad=None,
        url_accion='',
        datos_adicionales=None
    ):
        """
        Crea notificación usando una plantilla predefinida
        
        Args:
            usuario: Usuario destinatario
            tipo_plantilla: Tipo de plantilla a usar
            contexto: Dict con variables para renderizar plantilla
            prioridad: Prioridad (si no se especifica, usa la de la plantilla)
            url_accion: URL de acción
            datos_adicionales: Metadata adicional
        
        Returns:
            Notificacion: Objeto notificación creado
        """
        try:
            # Buscar plantilla
            plantilla = PlantillaNotificacion.objects.get(tipo=tipo_plantilla, activo=True)
            
            # Renderizar plantilla
            contenido = plantilla.renderizar(contexto)
            
            # Crear notificación
            return NotificacionService.crear_notificacion(
                usuario=usuario,
                tipo=tipo_plantilla,
                titulo=contenido['titulo'],
                mensaje=contenido['mensaje'],
                prioridad=prioridad or plantilla.prioridad_default,
                url_accion=url_accion,
                datos_adicionales=datos_adicionales,
                enviar_email=plantilla.enviar_email
            )
            
        except PlantillaNotificacion.DoesNotExist:
            logger.error(f"Plantilla no encontrada: {tipo_plantilla}")
            raise ValueError(f"Plantilla '{tipo_plantilla}' no existe")
        except Exception as e:
            logger.error(f"Error al crear notificación desde plantilla: {str(e)}")
            raise
    
    @staticmethod
    def enviar_email(notificacion):
        """
        Envía email basado en la notificación
        
        Args:
            notificacion: Objeto Notificacion
        """
        try:
            usuario = notificacion.usuario
            
            if not usuario.email:
                logger.warning(f"Usuario {usuario.id} no tiene email configurado")
                return False
            
            # Contexto para el email
            contexto = {
                'usuario': usuario,
                'notificacion': notificacion,
                'titulo': notificacion.titulo,
                'mensaje': notificacion.mensaje,
                'url_accion': notificacion.url_accion,
                'prioridad': notificacion.get_prioridad_display(),
            }
            
            # Renderizar template HTML
            html_content = render_to_string('notificaciones/email_notificacion.html', contexto)
            
            # Crear email
            subject = f"[GRC] {notificacion.titulo}"
            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = [usuario.email]
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=notificacion.mensaje,  # Texto plano como fallback
                from_email=from_email,
                to=to_email
            )
            
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            
            # Marcar como enviado
            notificacion.marcar_email_enviado()
            
            logger.info(f"Email enviado a {usuario.email} para notificación {notificacion.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error al enviar email: {str(e)}")
            return False
    
    @staticmethod
    def marcar_todas_leidas(usuario):
        """
        Marca todas las notificaciones de un usuario como leídas
        
        Args:
            usuario: Usuario
        
        Returns:
            int: Cantidad de notificaciones marcadas
        """
        try:
            notificaciones = Notificacion.objects.filter(
                usuario=usuario,
                leida=False
            )
            
            count = notificaciones.count()
            
            from django.utils import timezone
            notificaciones.update(
                leida=True,
                fecha_leida=timezone.now()
            )
            
            logger.info(f"Marcadas {count} notificaciones como leídas para {usuario.email}")
            return count
            
        except Exception as e:
            logger.error(f"Error al marcar notificaciones como leídas: {str(e)}")
            return 0
    
    @staticmethod
    def obtener_no_leidas(usuario, limite=50):
        """
        Obtiene notificaciones no leídas de un usuario
        
        Args:
            usuario: Usuario
            limite: Cantidad máxima a retornar
        
        Returns:
            QuerySet: Notificaciones no leídas
        """
        return Notificacion.objects.filter(
            usuario=usuario,
            leida=False,
            activo=True
        ).order_by('-fecha_creacion')[:limite]
    
    @staticmethod
    def contar_no_leidas(usuario):
        """
        Cuenta notificaciones no leídas de un usuario
        
        Args:
            usuario: Usuario
        
        Returns:
            int: Cantidad de notificaciones no leídas
        """
        return Notificacion.objects.filter(
            usuario=usuario,
            leida=False,
            activo=True
        ).count()
    
    @staticmethod
    def eliminar_antiguas(dias=90):
        """
        Elimina notificaciones antiguas (soft delete)
        
        Args:
            dias: Días de antigüedad
        
        Returns:
            int: Cantidad de notificaciones eliminadas
        """
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            fecha_limite = timezone.now() - timedelta(days=dias)
            
            notificaciones = Notificacion.objects.filter(
                fecha_creacion__lt=fecha_limite,
                activo=True
            )
            
            count = notificaciones.count()
            notificaciones.update(activo=False)
            
            logger.info(f"Eliminadas {count} notificaciones antiguas")
            return count
            
        except Exception as e:
            logger.error(f"Error al eliminar notificaciones antiguas: {str(e)}")
            return 0


class NotificacionAsignacionService:
    """
    Servicio específico para notificaciones de asignaciones
    """
    
    @staticmethod
    def notificar_asignacion_evaluacion(asignacion):
        """
        Notifica al administrador que se le asignó una evaluación completa
        
        Args:
            asignacion: Objeto Asignacion (evaluación completa)
        """
        usuario = asignacion.usuario_asignado
        encuesta = asignacion.encuesta
        asignado_por = asignacion.asignado_por
        
        titulo = f"Nueva evaluación asignada: {encuesta.nombre}"
        mensaje = (
            f"Se te ha asignado la evaluación '{encuesta.nombre}' por {asignado_por.nombre_completo}. "
            f"Fecha límite: {asignacion.fecha_limite.strftime('%d/%m/%Y')}. "
            f"Total de dimensiones: {encuesta.total_dimensiones}."
        )
        
        url_accion = f"/evaluaciones/{asignacion.id}"
        
        datos_adicionales = {
            'asignacion_id': str(asignacion.id),
            'encuesta_id': str(encuesta.id),
            'tipo_asignacion': 'evaluacion_completa'
        }
        
        NotificacionService.crear_notificacion(
            usuario=usuario,
            tipo='asignacion_evaluacion',
            titulo=titulo,
            mensaje=mensaje,
            prioridad='alta',
            url_accion=url_accion,
            datos_adicionales=datos_adicionales,
            enviar_email=True
        )
    
    @staticmethod
    def notificar_asignacion_dimension(asignacion):
        """
        Notifica al usuario que se le asignó una dimensión específica
        
        Args:
            asignacion: Objeto Asignacion (dimensión específica)
        """
        usuario = asignacion.usuario_asignado
        dimension = asignacion.dimension
        encuesta = asignacion.encuesta
        asignado_por = asignacion.asignado_por
        
        titulo = f"Nueva dimensión asignada: {dimension.nombre}"
        mensaje = (
            f"Se te ha asignado la dimensión '{dimension.nombre}' de la evaluación '{encuesta.nombre}' "
            f"por {asignado_por.nombre_completo}. "
            f"Fecha límite: {asignacion.fecha_limite.strftime('%d/%m/%Y')}. "
            f"Total de preguntas: {dimension.total_preguntas}."
        )
        
        url_accion = f"/mis-asignaciones/{asignacion.id}"
        
        datos_adicionales = {
            'asignacion_id': str(asignacion.id),
            'dimension_id': str(dimension.id),
            'encuesta_id': str(encuesta.id),
            'tipo_asignacion': 'dimension'
        }
        
        NotificacionService.crear_notificacion(
            usuario=usuario,
            tipo='asignacion_dimension',
            titulo=titulo,
            mensaje=mensaje,
            prioridad='normal',
            url_accion=url_accion,
            datos_adicionales=datos_adicionales,
            enviar_email=True
        )
        
    @staticmethod
    def notificar_revision_aprobada(asignacion):
        """Notifica al usuario que su asignación fue aprobada"""
        Notificacion.objects.create(
            usuario=asignacion.usuario_asignado,
            tipo='asignacion_aprobada',
            titulo='Asignación Aprobada ✅',
            mensaje=f'Tu asignación de "{asignacion.dimension.nombre}" ha sido aprobada por {asignacion.revisado_por.nombre_completo}.',
            datos_adicionales={
                'asignacion_id': str(asignacion.id),
                'dimension': asignacion.dimension.nombre,
                'revisado_por': asignacion.revisado_por.nombre_completo,
                'comentarios': asignacion.comentarios_revision
            }
        )
    
    @staticmethod
    def notificar_revision_rechazada(asignacion):
        """Notifica al usuario que su asignación fue rechazada"""
        Notificacion.objects.create(
            usuario=asignacion.usuario_asignado,
            tipo='asignacion_rechazada',
            titulo='Asignación Rechazada ❌',
            mensaje=f'Tu asignación de "{asignacion.dimension.nombre}" requiere correcciones. Comentarios: {asignacion.comentarios_revision}',
            datos_adicionales={
                'asignacion_id': str(asignacion.id),
                'dimension': asignacion.dimension.nombre,
                'revisado_por': asignacion.revisado_por.nombre_completo,
                'comentarios': asignacion.comentarios_revision
            },
            prioridad='alta'
        )