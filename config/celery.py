# config/celery.py
import os
from celery import Celery

# Configurar Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('grc_backend')

# Configuración desde Django settings con prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tasks en todas las apps
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')