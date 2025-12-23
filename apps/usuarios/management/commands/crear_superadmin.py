# apps/usuarios/management/commands/crear_superadmin.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

Usuario = get_user_model()

class Command(BaseCommand):
    help = 'Crear usuario SuperAdmin'
    
    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email del superadmin')
        parser.add_argument('--password', type=str, help='Password del superadmin')
        parser.add_argument('--nombre', type=str, help='Nombre completo')
    
    def handle(self, *args, **options):
        email = options.get('email') or input('Email: ')
        password = options.get('password') or input('Password: ')
        nombre = options.get('nombre') or input('Nombre completo: ')
        
        if Usuario.objects.filter(email=email).exists():
            self.stdout.write(self.style.ERROR(f'Ya existe un usuario con el email {email}'))
            return
        
        nombres = nombre.split(' ', 1)
        first_name = nombres[0]
        last_name = nombres[1] if len(nombres) > 1 else ''
        
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
        
        self.stdout.write(self.style.SUCCESS(f'SuperAdmin creado exitosamente: {email}'))