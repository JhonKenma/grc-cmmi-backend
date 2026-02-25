# apps/asignaciones_iq/services.py
"""
Servicios para notificaciones de Asignaciones de Evaluaciones IQ
"""

from apps.notificaciones.services import NotificacionService
import logging

logger = logging.getLogger(__name__)


class NotificacionAsignacionIQService:
    """
    Servicio para enviar notificaciones relacionadas con asignaciones IQ
    """
    
    @staticmethod
    def notificar_asignacion(asignacion):
        """
        Notifica al usuario cuando se le asigna una evaluación IQ
        
        Args:
            asignacion: Objeto AsignacionEvaluacionIQ
        """
        try:
            usuario = asignacion.usuario_asignado
            evaluacion = asignacion.evaluacion
            asignado_por = asignacion.asignado_por
            
            # Título
            titulo = f"📋 Nueva Evaluación: {evaluacion.nombre}"
            
            # Mensaje detallado
            frameworks_nombres = ", ".join([fw.codigo for fw in evaluacion.frameworks.all()])
            
            mensaje = (
                f"Se te ha asignado la evaluación '{evaluacion.nombre}' "
                f"por {asignado_por.get_full_name()}.\n\n"
                f"📊 Frameworks: {frameworks_nombres}\n"
                f"📅 Fecha de inicio: {asignacion.fecha_inicio.strftime('%d/%m/%Y')}\n"
                f"⏰ Fecha límite: {asignacion.fecha_limite.strftime('%d/%m/%Y')}\n"
                f"❓ Total de preguntas: {asignacion.total_preguntas}\n\n"
            )
            
            if asignacion.notas_asignacion:
                mensaje += f"💬 Notas: {asignacion.notas_asignacion}\n\n"
            
            mensaje += f"Tienes {asignacion.dias_restantes} días para completarla."
            
            # URL de acción
            url_accion = f"/evaluaciones-iq/mis-asignaciones/{asignacion.id}"
            
            # Datos adicionales
            datos_adicionales = {
                'asignacion_id': str(asignacion.id),
                'evaluacion_id': str(evaluacion.id),
                'fecha_limite': asignacion.fecha_limite.isoformat(),
                'total_preguntas': asignacion.total_preguntas,
                'frameworks': [fw.codigo for fw in evaluacion.frameworks.all()],
                'nivel_deseado': evaluacion.nivel_deseado,
                'nivel_deseado_display': evaluacion.get_nivel_deseado_display(),
            }
            
            # Crear notificación
            notificacion = NotificacionService.crear_notificacion(
                usuario=usuario,
                tipo='asignacion_evaluacion',
                titulo=titulo,
                mensaje=mensaje,
                prioridad='alta',
                url_accion=url_accion,
                datos_adicionales=datos_adicionales,
                enviar_email=asignacion.notificar_usuario
            )
            
            logger.info(f"✅ Notificación enviada: Asignación {asignacion.id} a {usuario.email}")
            return notificacion
            
        except Exception as e:
            logger.error(f"❌ Error al notificar asignación {asignacion.id}: {str(e)}")
            return None
    
    @staticmethod
    def notificar_recordatorio(asignacion):
        """
        Envía recordatorio cuando quedan pocos días para completar
        
        Args:
            asignacion: Objeto AsignacionEvaluacionIQ
        """
        try:
            dias_restantes = asignacion.dias_restantes
            
            if dias_restantes <= 0:
                return None
            
            titulo = f"⏰ Recordatorio: {asignacion.evaluacion.nombre}"
            
            if dias_restantes == 1:
                mensaje = f"⚠️ Te queda 1 día para completar la evaluación '{asignacion.evaluacion.nombre}'."
            else:
                mensaje = f"⚠️ Te quedan {dias_restantes} días para completar la evaluación '{asignacion.evaluacion.nombre}'."
            
            mensaje += f"\n\n📊 Progreso actual: {asignacion.porcentaje_completado}%"
            mensaje += f"\n❓ Preguntas respondidas: {asignacion.preguntas_respondidas}/{asignacion.total_preguntas}"
            
            url_accion = f"/evaluaciones-iq/mis-asignaciones/{asignacion.id}"
            
            datos_adicionales = {
                'asignacion_id': str(asignacion.id),
                'tipo_notificacion': 'recordatorio',
                'dias_restantes': dias_restantes,
                'porcentaje_completado': float(asignacion.porcentaje_completado),
            }
            
            # Prioridad según días restantes
            if dias_restantes <= 1:
                prioridad = 'urgente'
            elif dias_restantes <= 3:
                prioridad = 'alta'
            else:
                prioridad = 'normal'
            
            notificacion = NotificacionService.crear_notificacion(
                usuario=asignacion.usuario_asignado,
                tipo='recordatorio_plazo',
                titulo=titulo,
                mensaje=mensaje,
                prioridad=prioridad,
                url_accion=url_accion,
                datos_adicionales=datos_adicionales,
                enviar_email=True
            )
            
            # Marcar que se envió recordatorio
            asignacion.recordatorio_enviado = True
            asignacion.save(update_fields=['recordatorio_enviado'])
            
            logger.info(f"✅ Recordatorio enviado: Asignación {asignacion.id}")
            return notificacion
            
        except Exception as e:
            logger.error(f"❌ Error al enviar recordatorio {asignacion.id}: {str(e)}")
            return None
    
    @staticmethod
    def notificar_completada(asignacion):
        """
        Notifica al Admin cuando un usuario completa su asignación
        
        Args:
            asignacion: Objeto AsignacionEvaluacionIQ
        """
        try:
            # Notificar al Admin que asignó
            if not asignacion.asignado_por:
                return None
            
            usuario = asignacion.usuario_asignado
            evaluacion = asignacion.evaluacion
            
            titulo = f"✅ Evaluación Completada: {evaluacion.nombre}"
            mensaje = (
                f"{usuario.get_full_name()} ha completado la evaluación '{evaluacion.nombre}'.\n\n"
                f"📊 Total de preguntas respondidas: {asignacion.preguntas_respondidas}\n"
                f"⏱️ Tiempo usado: {asignacion.tiempo_usado:.1f} horas\n"
                f"📅 Fecha de completado: {asignacion.fecha_completado.strftime('%d/%m/%Y %H:%M')}\n\n"
                f"Ya puedes revisar y aprobar esta evaluación."
            )
            
            url_accion = f"/evaluaciones-iq/asignaciones/{asignacion.id}/revisar"
            
            datos_adicionales = {
                'asignacion_id': str(asignacion.id),
                'evaluacion_id': str(evaluacion.id),
                'usuario_id': str(usuario.id),
                'tipo_notificacion': 'completada',
            }
            
            notificacion = NotificacionService.crear_notificacion(
                usuario=asignacion.asignado_por,
                tipo='evaluacion_completada',
                titulo=titulo,
                mensaje=mensaje,
                prioridad='normal',
                url_accion=url_accion,
                datos_adicionales=datos_adicionales,
                enviar_email=True
            )
            
            logger.info(f"✅ Notificación de completado enviada al Admin")
            return notificacion
            
        except Exception as e:
            logger.error(f"❌ Error al notificar completado: {str(e)}")
            return None
    
    @staticmethod
    def notificar_aprobada(asignacion):
        """
        Notifica al usuario que su evaluación fue aprobada
        
        Args:
            asignacion: Objeto AsignacionEvaluacionIQ
        """
        try:
            titulo = f"✅ Evaluación Aprobada: {asignacion.evaluacion.nombre}"
            mensaje = (
                f"¡Felicitaciones! Tu evaluación '{asignacion.evaluacion.nombre}' ha sido aprobada "
                f"por {asignacion.revisado_por.get_full_name()}.\n\n"
            )
            
            if asignacion.notas_revision:
                mensaje += f"💬 Comentarios: {asignacion.notas_revision}"
            
            url_accion = f"/evaluaciones-iq/mis-asignaciones/{asignacion.id}"
            
            datos_adicionales = {
                'asignacion_id': str(asignacion.id),
                'tipo_notificacion': 'aprobada',
            }
            
            notificacion = NotificacionService.crear_notificacion(
                usuario=asignacion.usuario_asignado,
                tipo='aprobacion',
                titulo=titulo,
                mensaje=mensaje,
                prioridad='normal',
                url_accion=url_accion,
                datos_adicionales=datos_adicionales,
                enviar_email=True
            )
            
            logger.info(f"✅ Notificación de aprobación enviada")
            return notificacion
            
        except Exception as e:
            logger.error(f"❌ Error al notificar aprobación: {str(e)}")
            return None
    
    @staticmethod
    def notificar_rechazada(asignacion):
        """
        Notifica al usuario que su evaluación fue rechazada
        
        Args:
            asignacion: Objeto AsignacionEvaluacionIQ
        """
        try:
            titulo = f"⚠️ Evaluación Requiere Correcciones: {asignacion.evaluacion.nombre}"
            mensaje = (
                f"Tu evaluación '{asignacion.evaluacion.nombre}' requiere correcciones.\n\n"
                f"👤 Revisado por: {asignacion.revisado_por.get_full_name()}\n"
            )
            
            if asignacion.notas_revision:
                mensaje += f"\n💬 Comentarios:\n{asignacion.notas_revision}\n\n"
            
            mensaje += "Por favor, revisa los comentarios y realiza las correcciones necesarias."
            
            url_accion = f"/evaluaciones-iq/mis-asignaciones/{asignacion.id}"
            
            datos_adicionales = {
                'asignacion_id': str(asignacion.id),
                'tipo_notificacion': 'rechazada',
            }
            
            notificacion = NotificacionService.crear_notificacion(
                usuario=asignacion.usuario_asignado,
                tipo='sistema',
                titulo=titulo,
                mensaje=mensaje,
                prioridad='alta',
                url_accion=url_accion,
                datos_adicionales=datos_adicionales,
                enviar_email=True
            )
            
            logger.info(f"✅ Notificación de rechazo enviada")
            return notificacion
            
        except Exception as e:
            logger.error(f"❌ Error al notificar rechazo: {str(e)}")
            return None
    
    @staticmethod
    def notificar_vencida(asignacion):
        """
        Notifica cuando una asignación se vence sin completar
        
        Args:
            asignacion: Objeto AsignacionEvaluacionIQ
        """
        try:
            # Notificar al usuario
            titulo_usuario = f"⏰ Evaluación Vencida: {asignacion.evaluacion.nombre}"
            mensaje_usuario = (
                f"La fecha límite para completar la evaluación '{asignacion.evaluacion.nombre}' ha vencido.\n\n"
                f"📅 Fecha límite: {asignacion.fecha_limite.strftime('%d/%m/%Y')}\n"
                f"📊 Progreso alcanzado: {asignacion.porcentaje_completado}%\n\n"
                f"Contacta a tu administrador para solicitar una extensión."
            )
            
            NotificacionService.crear_notificacion(
                usuario=asignacion.usuario_asignado,
                tipo='evaluacion_vencida',
                titulo=titulo_usuario,
                mensaje=mensaje_usuario,
                prioridad='alta',
                url_accion=f"/evaluaciones-iq/mis-asignaciones/{asignacion.id}",
                datos_adicionales={'asignacion_id': str(asignacion.id)},
                enviar_email=True
            )
            
            # Notificar al Admin
            if asignacion.asignado_por:
                titulo_admin = f"⚠️ Evaluación Vencida: {asignacion.evaluacion.nombre}"
                mensaje_admin = (
                    f"La evaluación '{asignacion.evaluacion.nombre}' asignada a "
                    f"{asignacion.usuario_asignado.get_full_name()} ha vencido sin completarse.\n\n"
                    f"📊 Progreso alcanzado: {asignacion.porcentaje_completado}%\n"
                    f"❓ Preguntas respondidas: {asignacion.preguntas_respondidas}/{asignacion.total_preguntas}"
                )
                
                NotificacionService.crear_notificacion(
                    usuario=asignacion.asignado_por,
                    tipo='evaluacion_vencida',
                    titulo=titulo_admin,
                    mensaje=mensaje_admin,
                    prioridad='normal',
                    url_accion=f"/evaluaciones-iq/asignaciones/{asignacion.id}",
                    datos_adicionales={'asignacion_id': str(asignacion.id)},
                    enviar_email=True
                )
            
            logger.info(f"✅ Notificaciones de vencimiento enviadas")
            
        except Exception as e:
            logger.error(f"❌ Error al notificar vencimiento: {str(e)}")