# apps/usuarios/management/commands/crear_superadmin.py - REEMPLAZAR TODO

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

Usuario = get_user_model()

class Command(BaseCommand):
    help = 'Crear usuario SuperAdmin (desde variables de entorno o argumentos)'
    
    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email del superadmin')
        parser.add_argument('--password', type=str, help='Password del superadmin')
        parser.add_argument('--nombre', type=str, help='Nombre completo')
    
    def handle(self, *args, **options):
        # ⭐ PRIORIDAD: Variables de entorno → Argumentos → Input manual
        email = options.get('email') or os.environ.get('SUPERADMIN_EMAIL')
        password = options.get('password') or os.environ.get('SUPERADMIN_PASSWORD')
        nombre = options.get('nombre') or os.environ.get('SUPERADMIN_NOMBRE')
        
        # Si no hay email ni password en variables/argumentos, pedir manualmente
        if not email:
            email = input('Email: ')
        if not password:
            password = input('Password: ')
        if not nombre:
            nombre = input('Nombre completo: ') or 'Super Administrador'
        
        # Validar que se proporcionaron datos
        if not email or not password:
            self.stdout.write(
                self.style.ERROR('❌ Debes proporcionar email y password')
            )
            return
        
        # Verificar si ya existe
        if Usuario.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'⚠️  Ya existe un usuario con el email {email}')
            )
            return
        
        # Separar nombre en first_name y last_name
        nombres = nombre.split(' ', 1)
        first_name = nombres[0]
        last_name = nombres[1] if len(nombres) > 1 else ''
        
        # Crear superadmin
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