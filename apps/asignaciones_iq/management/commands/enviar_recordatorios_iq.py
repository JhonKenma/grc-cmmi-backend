# apps/asignaciones_iq/management/commands/enviar_recordatorios_iq.py
"""
Comando para enviar recordatorios de asignaciones próximas a vencer

Uso:
python manage.py enviar_recordatorios_iq

Debe ejecutarse con cron diariamente:
0 9 * * * cd /path/to/project && python manage.py enviar_recordatorios_iq
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.asignaciones_iq.models import AsignacionEvaluacionIQ
from apps.asignaciones_iq.services import NotificacionAsignacionIQService


class Command(BaseCommand):
    help = 'Envía recordatorios de asignaciones próximas a vencer'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=3,
            help='Días de anticipación para enviar recordatorio (default: 3)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar envío incluso si ya se envió recordatorio'
        )
    
    def handle(self, *args, **options):
        dias = options['dias']
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🔔 Buscando asignaciones que vencen en {dias} días...'
            )
        )
        
        # Calcular fecha límite
        hoy = timezone.now().date()
        fecha_objetivo = hoy + timedelta(days=dias)
        
        # Buscar asignaciones
        filtro = {
            'fecha_limite': fecha_objetivo,
            'estado__in': ['pendiente', 'en_progreso'],
            'activo': True,
        }
        
        if not force:
            filtro['recordatorio_enviado'] = False
        
        asignaciones = AsignacionEvaluacionIQ.objects.filter(**filtro).select_related(
            'usuario_asignado',
            'evaluacion',
            'asignado_por'
        )
        
        total = asignaciones.count()
        
        if total == 0:
            self.stdout.write(
                self.style.WARNING('⚠️  No hay asignaciones para recordar')
            )
            return
        
        self.stdout.write(f'📧 Enviando {total} recordatorio(s)...\n')
        
        enviados = 0
        errores = 0
        
        for asignacion in asignaciones:
            try:
                NotificacionAsignacionIQService.notificar_recordatorio(asignacion)
                enviados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✅ {asignacion.usuario_asignado.email} - '
                        f'{asignacion.evaluacion.nombre}'
                    )
                )
            except Exception as e:
                errores += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ Error en {asignacion.usuario_asignado.email}: {str(e)}'
                    )
                )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Recordatorios enviados: {enviados}'
            )
        )
        if errores > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Errores: {errores}'
                )
            )