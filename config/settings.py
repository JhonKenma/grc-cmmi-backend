# config/settings.py - VERSIÓN PARA RENDER

from pathlib import Path
from decouple import config
from datetime import timedelta
import os
import dj_database_url  # ⭐ AGREGAR
from supabase import create_client, Client

BASE_DIR = Path(__file__).resolve().parent.parent

# ═══════════════════════════════════════════════════════
# SEGURIDAD
# ═══════════════════════════════════════════════════════

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)

# ⭐ MEJORAR ALLOWED_HOSTS para Render
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS', 
    default='localhost,127.0.0.1'
).split(',')

# Agregar .onrender.com si estamos en Render
if not DEBUG:
    ALLOWED_HOSTS.append('.onrender.com')

# ═══════════════════════════════════════════════════════
# APLICACIONES
# ═══════════════════════════════════════════════════════

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    
    # Local apps
    'apps.core',
    'apps.empresas',
    'apps.usuarios',
    'apps.encuestas',
    'apps.asignaciones',
    'apps.respuestas',
    'apps.dashboard',
    'apps.reportes',
    'apps.notificaciones',
    'apps.proyectos_remediacion',
    'django_extensions',

    'drf_spectacular',
    'drf_spectacular_sidecar',
]

# ═══════════════════════════════════════════════════════
# MIDDLEWARE
# ═══════════════════════════════════════════════════════

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ⭐ AGREGAR para archivos estáticos
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ═══════════════════════════════════════════════════════
# BASE DE DATOS (⭐ CONFIGURACIÓN PARA RENDER)
# ═══════════════════════════════════════════════════════

# Si existe DATABASE_URL (Render/producción), usar esa
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Configuración local con decouple
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST'),
            'PORT': config('DB_PORT'),
        }
    }

# ═══════════════════════════════════════════════════════
# VALIDACIÓN DE CONTRASEÑAS
# ═══════════════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ═══════════════════════════════════════════════════════
# INTERNACIONALIZACIÓN
# ═══════════════════════════════════════════════════════

LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

# ═══════════════════════════════════════════════════════
# ARCHIVOS ESTÁTICOS (⭐ CONFIGURACIÓN PARA RENDER)
# ═══════════════════════════════════════════════════════

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Whitenoise - Compresión y caché para archivos estáticos
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ═══════════════════════════════════════════════════════
# ARCHIVOS MEDIA
# ═══════════════════════════════════════════════════════

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'usuarios.Usuario'

# ═══════════════════════════════════════════════════════
# REST FRAMEWORK
# ═══════════════════════════════════════════════════════

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ═══════════════════════════════════════════════════════
# JWT
# ═══════════════════════════════════════════════════════

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=config('JWT_ACCESS_TOKEN_LIFETIME_HOURS', default=8, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=1, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ═══════════════════════════════════════════════════════
# CORS (⭐ ACTUALIZAR PARA RENDER)
# ═══════════════════════════════════════════════════════

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # ⭐ Agregar tu frontend de Render después del deploy
    "https://grc-cmmi-frontend.onrender.com",
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_CREDENTIALS = True

# ⭐ CSRF para producción
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # ⭐ Agregar tu frontend de Render después del deploy
    "https://grc-cmmi-frontend.onrender.com",
]

# ═══════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        # Esto silencia los detalles excesivos de la conexión de red
        'httpx': {
            'handlers': ['console'],
            'level': 'WARNING', # Solo muestra advertencias o errores
        },
        'httpcore': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'supabase': {
            'handlers': ['console'],
            'level': 'INFO', # O WARNING si quieres aún menos texto
        },
    },
}
# ═══════════════════════════════════════════════════════
# EMAIL CONFIGURATION
# ═══════════════════════════════════════════════════════

EMAIL_BACKEND = config(
    'EMAIL_BACKEND', 
    default='django.core.mail.backends.smtp.EmailBackend'
)

EMAIL_HOST = config('EMAIL_HOST', default='sandbox.smtp.mailtrap.io')
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_PORT = config('EMAIL_PORT', default=2525, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)

DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL', 
    default='Sistema GRC <noreply@grc.com>'
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 10

# ═══════════════════════════════════════════════════════
# CELERY CONFIGURATION (⭐ OPCIONAL - Comentar si no usas Celery)
# ═══════════════════════════════════════════════════════

# CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
# CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
# CELERY_ACCEPT_CONTENT = ['json']
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_TIMEZONE = 'America/Lima'
# CELERY_TASK_TRACK_STARTED = True
# CELERY_TASK_TIME_LIMIT = 30 * 60
# CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ============================================
# SUPABASE STORAGE CONFIGURATION
# ============================================

# 1. Definir credenciales
SUPABASE_URL = config('SUPABASE_URL', default='')
SUPABASE_KEY = config('SUPABASE_KEY', default='')
SUPABASE_BUCKET = 'evidencias'

# 2. Inicializar la variable nula primero
supabase = None 

# 3. Intentar asignarle el cliente
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase inyectado en settings correctamente")
    except Exception as e:
        print(f"❌ Error crítico en settings: {e}")
        
        
# ═══════════════════════════════════════════════════════
# CONFIGURACIÓN DE SEGURIDAD PARA PRODUCCIÓN
# ═══════════════════════════════════════════════════════
SPECTACULAR_SETTINGS = {
    'TITLE': 'Tu API GRC',
    'DESCRIPTION': 'Documentación del sistema de gestión',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # ESTO ES LO QUE BUSCAS:
    'SCHEMA_PATH_PREFIX': r'/api/', # Limpia el prefijo común en la doc
    'SORT_OPERATION_PARAMETERS': True,
    'TAGS': [
        {'name': '1. Autenticación y Usuarios', 'description': 'Endpoints de usuarios'},
        {'name': '2. Gestión de Empresas', 'description': 'Gestión de empresas'},
        {'name': '3. Gestión de Evaluaciones(Encuestas-Excel)', 'description': 'Gestión de Evaluaciones(Encuestas-Excel'},
        
        # ... define aquí el orden exacto que quieres
    ],
}


if not DEBUG:
    # HTTPS
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Seguridad adicional
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True