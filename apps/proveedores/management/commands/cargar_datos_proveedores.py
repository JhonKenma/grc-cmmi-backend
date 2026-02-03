# apps/proveedores/management/commands/cargar_datos_proveedores.py

from django.core.management.base import BaseCommand
from apps.proveedores.models import TipoProveedor, ClasificacionProveedor


class Command(BaseCommand):
    help = 'Carga los tipos y clasificaciones de proveedores iniciales'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando carga de datos...'))
        
        # Cargar tipos de proveedores
        self.cargar_tipos_proveedor()
        
        # Cargar clasificaciones
        self.cargar_clasificaciones()
        
        self.stdout.write(self.style.SUCCESS('✅ Datos cargados exitosamente'))

    def cargar_tipos_proveedor(self):
        """Carga los 36 tipos de proveedores en orden alfabético"""
        
        tipos = [
            'Proveedores de almacenamiento y distribución',
            'Proveedores de auditoría externa',
            'Proveedores de capacitación y certificación',
            'Proveedores de certificación (ISO, SOC, etc.)',
            'Proveedores de ciberseguridad',
            'Proveedores de consultoría',
            'Proveedores de continuidad de negocio / DRP',
            'Proveedores de cumplimiento normativo (compliance)',
            'Proveedores de datos / data providers',
            'Proveedores de energía y servicios públicos',
            'Proveedores de facilities (limpieza, seguridad física, edificios)',
            'Proveedores de firma electrónica',
            'Proveedores de gestión de riesgos',
            'Proveedores de gestión documental',
            'Proveedores de hardware',
            'Proveedores de identidad digital (IAM)',
            'Proveedores de infraestructura',
            'Proveedores de investigación de mercado',
            'Proveedores de logística y transporte',
            'Proveedores de mantenimiento y soporte técnico',
            'Proveedores de manufactura / producción',
            'Proveedores de marketing y publicidad',
            'Proveedores de materias primas',
            'Proveedores de monitoreo y alertas',
            'Proveedores de nube (cloud)',
            'Proveedores de outsourcing / BPO',
            'Proveedores de pagos',
            'Proveedores de reclutamiento y selección',
            'Proveedores de recursos humanos',
            'Proveedores de seguros',
            'Proveedores de servicios gestionados (MSP/MSSP)',
            'Proveedores de software',
            'Proveedores de tecnología (TI)',
            'Proveedores de telecomunicaciones',
            'Proveedores financieros / bancarios',
            'Proveedores legales',
        ]
        
        creados = 0
        actualizados = 0
        
        for orden, nombre in enumerate(tipos, start=1):
            tipo, created = TipoProveedor.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'orden': orden,
                    'activo': True,
                }
            )
            
            if created:
                creados += 1
                self.stdout.write(f'  ✓ Creado: {nombre}')
            else:
                actualizados += 1
                self.stdout.write(f'  ↻ Actualizado: {nombre}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📋 Tipos de Proveedor: {creados} creados, {actualizados} actualizados'
            )
        )

    def cargar_clasificaciones(self):
        """Carga las 4 clasificaciones de proveedores"""
        
        clasificaciones = [
            {
                'codigo': 'estrategico',
                'nombre': 'Proveedor Estratégico',
                'descripcion': 'Proveedor clave para el negocio, con alto impacto en objetivos estratégicos',
                'color': '#EF4444',  # Rojo
            },
            {
                'codigo': 'critico',
                'nombre': 'Proveedor Crítico',
                'descripcion': 'Proveedor esencial para operaciones, su falla afecta significativamente',
                'color': '#F59E0B',  # Naranja
            },
            {
                'codigo': 'no_critico',
                'nombre': 'Proveedor No Crítico',
                'descripcion': 'Proveedor importante pero reemplazable sin afectar operaciones críticas',
                'color': '#10B981',  # Verde
            },
            {
                'codigo': 'temporal',
                'nombre': 'Proveedor Temporal',
                'descripcion': 'Proveedor contratado para proyecto específico o periodo limitado',
                'color': '#6B7280',  # Gris
            },
        ]
        
        creados = 0
        actualizados = 0
        
        for datos in clasificaciones:
            clasificacion, created = ClasificacionProveedor.objects.update_or_create(
                codigo=datos['codigo'],
                defaults={
                    'nombre': datos['nombre'],
                    'descripcion': datos['descripcion'],
                    'color': datos['color'],
                    'activo': True,
                }
            )
            
            if created:
                creados += 1
                self.stdout.write(f'  ✓ Creado: {datos["nombre"]}')
            else:
                actualizados += 1
                self.stdout.write(f'  ↻ Actualizado: {datos["nombre"]}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🏷️  Clasificaciones: {creados} creadas, {actualizados} actualizadas'
            )
        )