# apps/proyectos_remediacion/signals.py

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from .models import ItemProyecto, ProyectoCierreBrecha
from apps.notificaciones.models import Notificacion


@receiver(pre_save, sender=ItemProyecto)
def detectar_exceso_presupuesto(sender, instance, **kwargs):
    """
    Signal que detecta cuando un ítem excede su presupuesto límite (110%)
    y marca una bandera para notificar después del guardado.
    """
    # Solo procesar si el ítem ya existe (actualización)
    if not instance.pk:
        return
    
    try:
        # Obtener el ítem anterior de la BD
        item_anterior = ItemProyecto.objects.get(pk=instance.pk)
        
        # Verificar si el presupuesto ejecutado cambió
        if item_anterior.presupuesto_ejecutado != instance.presupuesto_ejecutado:
            # Calcular límite
            limite = instance.presupuesto_limite
            
            # Si excede el límite y antes NO excedía, marcar para notificar
            if instance.presupuesto_ejecutado > limite and item_anterior.presupuesto_ejecutado <= limite:
                # Guardar bandera temporal para post_save
                instance._presupuesto_excedido = True
                instance._monto_excedido = instance.presupuesto_ejecutado - limite
    
    except ItemProyecto.DoesNotExist:
        pass


@receiver(post_save, sender=ItemProyecto)
def notificar_exceso_presupuesto(sender, instance, created, **kwargs):
    """
    Crea notificación al dueño del proyecto cuando un ítem excede su presupuesto límite.
    """
    # Solo notificar si se marcó la bandera en pre_save
    if not hasattr(instance, '_presupuesto_excedido'):
        return
    
    if not instance._presupuesto_excedido:
        return
    
    # Obtener el proyecto
    proyecto = instance.proyecto
    
    # Verificar que tenga dueño
    if not proyecto.dueno_proyecto:
        return
    
    # Crear notificación
    try:
        with transaction.atomic():
            Notificacion.objects.create(
                usuario=proyecto.dueno_proyecto,
                tipo='presupuesto_excedido',
                titulo=f'⚠️ Presupuesto excedido en ítem #{instance.numero_item}',
                mensaje=(
                    f'El ítem "{instance.nombre_item}" del proyecto '
                    f'{proyecto.codigo_proyecto} ha excedido su límite de presupuesto.\n\n'
                    f'• Presupuesto planificado: {instance.proyecto.moneda} {instance.presupuesto_planificado:,.2f}\n'
                    f'• Límite máximo (110%): {instance.proyecto.moneda} {instance.presupuesto_limite:,.2f}\n'
                    f'• Presupuesto ejecutado: {instance.proyecto.moneda} {instance.presupuesto_ejecutado:,.2f}\n'
                    f'• Monto excedido: {instance.proyecto.moneda} {instance._monto_excedido:,.2f}\n\n'
                    f'Responsable: {instance.responsable_ejecucion.nombre_completo if instance.responsable_ejecucion else "No asignado"}'
                ),
                url=f'/proyectos-remediacion/{proyecto.id}',
                metadata={
                    'proyecto_id': str(proyecto.id),
                    'item_id': str(instance.id),
                    'presupuesto_planificado': float(instance.presupuesto_planificado),
                    'presupuesto_limite': float(instance.presupuesto_limite),
                    'presupuesto_ejecutado': float(instance.presupuesto_ejecutado),
                    'monto_excedido': float(instance._monto_excedido),
                }
            )
            
            print(f"✅ Notificación creada: Presupuesto excedido en ítem #{instance.numero_item}")
    
    except Exception as e:
        print(f"❌ Error al crear notificación de presupuesto excedido: {e}")


# ═══════════════════════════════════════════════════════════════
# SIGNAL PARA SOLICITUD DE APROBACIÓN DE CIERRE GAP
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=ProyectoCierreBrecha)
def notificar_proyecto_en_validacion(sender, instance, created, update_fields, **kwargs):
    """
    Notifica al validador cuando un proyecto pasa a estado 'en_validacion'.
    """
    # Solo procesar actualizaciones
    if created:
        return
    
    # Verificar si cambió a estado en_validacion
    if update_fields and 'estado' not in update_fields:
        return
    
    if instance.estado != 'en_validacion':
        return
    
    # Determinar quién debe validar (prioridad: validador_interno > dueño evaluación)
    validador = instance.validador_interno
    
    # Si no hay validador interno, intentar obtener dueño de la evaluación
    if not validador and instance.calculo_nivel:
        try:
            # Obtener la asignación relacionada
            if hasattr(instance.calculo_nivel, 'asignacion') and instance.calculo_nivel.asignacion:
                asignacion = instance.calculo_nivel.asignacion
                # El creador de la asignación es típicamente el dueño de la evaluación
                validador = asignacion.creado_por
        except Exception as e:
            print(f"Error obteniendo validador de evaluación: {e}")
    
    if not validador:
        print(f"⚠️ No se encontró validador para el proyecto {instance.codigo_proyecto}")
        return
    
    # Crear notificación
    try:
        with transaction.atomic():
            Notificacion.objects.create(
                usuario=validador,
                tipo='proyecto_en_validacion',
                titulo=f'📋 Proyecto listo para validación',
                mensaje=(
                    f'El proyecto {instance.codigo_proyecto} - "{instance.nombre_proyecto}" '
                    f'está listo para validación y cierre de GAP.\n\n'
                    f'• Dimensión: {instance.calculo_nivel.dimension.nombre if instance.calculo_nivel else "N/A"}\n'
                    f'• GAP Original: {instance.gap_original}\n'
                    f'• Responsable: {instance.responsable_implementacion.nombre_completo if instance.responsable_implementacion else "N/A"}\n\n'
                    f'Por favor, revisa el proyecto y aprueba o rechaza el cierre del GAP.'
                ),
                url=f'/proyectos-remediacion/{instance.id}/validar',
                metadata={
                    'proyecto_id': str(instance.id),
                    'tipo_accion': 'validacion_gap',
                    'gap_original': float(instance.gap_original),
                },
                requiere_accion=True  # Marca que requiere una acción del usuario
            )
            
            print(f"✅ Notificación de validación enviada a {validador.email}")
    
    except Exception as e:
        print(f"❌ Error al crear notificación de validación: {e}")