# apps/usuarios/management/commands/crear_superadmin.py - MEJORAR

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os
import sys

Usuario = get_user_model()

class Command(BaseCommand):
    help = 'Crear usuario SuperAdmin (desde variables de entorno o argumentos)'
    
    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email del superadmin')
        parser.add_argument('--password', type=str, help='Password del superadmin')
        parser.add_argument('--nombre', type=str, help='Nombre completo')
        parser.add_argument('--no-input', action='store_true', help='No pedir input manual')
    
    def handle(self, *args, **options):
        # ⭐ PRIORIDAD: Variables de entorno → Argumentos → Input manual
        email = options.get('email') or os.environ.get('SUPERADMIN_EMAIL')
        password = options.get('password') or os.environ.get('SUPERADMIN_PASSWORD')
        nombre = options.get('nombre') or os.environ.get('SUPERADMIN_NOMBRE')
        no_input = options.get('no_input')
        
        # ⭐ Si estamos en producción (Render), no pedir input
        is_production = os.environ.get('RENDER') or no_input
        
        # Si no hay datos y NO estamos en producción, pedir manualmente
        if not is_production:
            if not email:
                email = input('Email: ')
            if not password:
                password = input('Password: ')
            if not nombre:
                nombre = input('Nombre completo: ') or 'Super Administrador'
        
        # Validar que se proporcionaron datos
        if not email or not password:
            if is_production:
                self.stdout.write(
                    self.style.WARNING('⚠️  No se proporcionaron credenciales de superadmin (SUPERADMIN_EMAIL/PASSWORD)')
                )
                self.stdout.write(
                    self.style.WARNING('⚠️  Saltando creación de superadmin...')
                )
                return
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Debes proporcionar email y password')
                )
                sys.exit(1)
        
        # Verificar si ya existe
        if Usuario.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'⚠️  Ya existe un usuario con el email {email}')
            )
            return
        
        # Separar nombre en first_name y last_name
        nombres = nombre.split(' ', 1) if nombre else ['Admin', 'Sistema']
        first_name = nombres[0]
        last_name = nombres[1] if len(nombres) > 1 else ''
        
        # Crear superadmin
        try:
            superadmin = Usuario.objects.create(
                email=email,
                username=email.split('@')[0],
                first_name=first_name,
                last_name=last_name,
                rol='superadmin',
                empresa=None,
                is_superuser=True,
                is_staff=True,
                activo=True
            )
            superadmin.set_password(password)
            superadmin.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ SuperAdmin creado exitosamente: {email}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error al crear superadmin: {str(e)}')
            )
            if not is_production:
                sys.exit(1)