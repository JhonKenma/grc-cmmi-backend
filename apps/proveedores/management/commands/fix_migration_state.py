from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Sincroniza el estado de las migraciones de proveedores'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            self.stdout.write('🔍 Verificando estado de migraciones...')
            
            # Verificar si la migración ya está registrada
            cursor.execute("""
                SELECT COUNT(*) FROM django_migrations 
                WHERE app = 'proveedores' AND name = '0001_initial';
            """)
            
            count = cursor.fetchone()[0]
            
            if count == 0:
                self.stdout.write('📝 Registrando migración 0001_initial...')
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('proveedores', '0001_initial', NOW());
                """)
                self.stdout.write(self.style.SUCCESS('✅ Migración registrada exitosamente'))
            else:
                self.stdout.write(self.style.SUCCESS('✅ La migración ya está registrada'))