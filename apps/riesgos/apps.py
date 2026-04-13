# apps/riesgos/apps.py

from django.apps import AppConfig


class RiesgosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.riesgos'
    verbose_name = 'Gestión de Riesgos'

    def ready(self):
        pass  # Aquí se importarán signals cuando sean necesarios