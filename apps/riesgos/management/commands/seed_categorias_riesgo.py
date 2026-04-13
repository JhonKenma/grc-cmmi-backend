# apps/riesgos/management/commands/seed_categorias_riesgo.py

from django.core.management.base import BaseCommand
from apps.riesgos.models import CategoriaRiesgo


CATEGORIAS = [
    # ── COSO ERM (8 categorías estándar) ──────────────────────────────────────
    {
        'nombre':      'Operacional',
        'descripcion': 'Riesgos derivados de fallas en procesos internos, personas o sistemas.',
        'estandar':    'coso',
        'color':       '#F97316',
        'icono':       'settings',
        'orden':       1,
    },
    {
        'nombre':      'Financiero',
        'descripcion': 'Riesgos relacionados con pérdidas económicas, liquidez o crédito.',
        'estandar':    'coso',
        'color':       '#EF4444',
        'icono':       'dollar-sign',
        'orden':       2,
    },
    {
        'nombre':      'Legal / Cumplimiento',
        'descripcion': 'Riesgos por incumplimiento de leyes, regulaciones o contratos.',
        'estandar':    'coso',
        'color':       '#8B5CF6',
        'icono':       'shield',
        'orden':       3,
    },
    {
        'nombre':      'Tecnología / TI',
        'descripcion': 'Riesgos relacionados con sistemas, ciberseguridad e infraestructura tecnológica.',
        'estandar':    'coso',
        'color':       '#3B82F6',
        'icono':       'monitor',
        'orden':       4,
    },
    {
        'nombre':      'Estratégico',
        'descripcion': 'Riesgos que afectan los objetivos estratégicos y la posición competitiva.',
        'estandar':    'coso',
        'color':       '#6366F1',
        'icono':       'target',
        'orden':       5,
    },
    {
        'nombre':      'Reputacional',
        'descripcion': 'Riesgos que afectan la imagen, marca o reputación de la organización.',
        'estandar':    'coso',
        'color':       '#EC4899',
        'icono':       'star',
        'orden':       6,
    },
    {
        'nombre':      'RRHH / Personas',
        'descripcion': 'Riesgos relacionados con el capital humano, cultura y gestión de personas.',
        'estandar':    'coso',
        'color':       '#14B8A6',
        'icono':       'users',
        'orden':       7,
    },
    {
        'nombre':      'Ambiental',
        'descripcion': 'Riesgos relacionados con el impacto ambiental y sostenibilidad.',
        'estandar':    'coso',
        'color':       '#22C55E',
        'icono':       'leaf',
        'orden':       8,
    },

    # ── ISO 31000 (categorías adicionales) ────────────────────────────────────
    {
        'nombre':      'Externo / Contexto',
        'descripcion': 'Riesgos provenientes del entorno externo: mercado, economía, política.',
        'estandar':    'iso31000',
        'color':       '#F59E0B',
        'icono':       'globe',
        'orden':       9,
    },
    {
        'nombre':      'Cadena de Suministro',
        'descripcion': 'Riesgos asociados a proveedores, terceros y cadena de valor.',
        'estandar':    'iso31000',
        'color':       '#0EA5E9',
        'icono':       'truck',
        'orden':       10,
    },
]


class Command(BaseCommand):
    help = (
        'Carga las categorías globales de riesgo estándar (COSO ERM + ISO 31000). '
        'Seguro de correr múltiples veces — usa get_or_create.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina y recrea todas las categorías globales (empresa=None).',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n📋 Cargando categorías globales de riesgo...\n'
        ))

        if options['reset']:
            eliminadas, _ = CategoriaRiesgo.objects.filter(empresa=None).delete()
            self.stdout.write(self.style.WARNING(
                f'  ⚠️  {eliminadas} categorías globales eliminadas.\n'
            ))

        creadas = 0
        existentes = 0

        for cat in CATEGORIAS:
            obj, created = CategoriaRiesgo.objects.get_or_create(
                empresa=None,
                nombre=cat['nombre'],
                defaults={
                    'descripcion': cat['descripcion'],
                    'estandar':    cat['estandar'],
                    'color':       cat['color'],
                    'icono':       cat['icono'],
                    'orden':       cat['orden'],
                    'activo':      True,
                }
            )

            if created:
                creadas += 1
                self.stdout.write(
                    f'  ✅ Creada:     {obj.nombre} ({obj.get_estandar_display()})'
                )
            else:
                existentes += 1
                self.stdout.write(
                    f'  ⚠️  Ya existe: {obj.nombre}'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n✔ Proceso completado: {creadas} creadas, {existentes} ya existían.\n'
        ))