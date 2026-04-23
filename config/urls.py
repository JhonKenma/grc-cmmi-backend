# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Swagger / OpenAPI
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

urlpatterns = [
    # ==============================
    # 🔹 Django Admin
    # ==============================
    path('admin/', admin.site.urls),

    # ==============================
    # 🔹 Endpoints de las aplicaciones
    # ==============================
    path('api/empresas/', include('apps.empresas.urls')),
    path('api/auth/', include('apps.usuarios.urls')),
    path('api/', include('apps.proveedores.urls')),
    path('api/encuestas/', include('apps.encuestas.urls')),
    # ⭐ NO BORRAR
    path('api/', include('apps.notificaciones.urls')),  # ← Quitar "notificaciones/"
    path('api/asignaciones/', include('apps.asignaciones.urls')),
    path('api/', include('apps.respuestas.urls')),
    path('api/', include('apps.reportes.urls')),
    path('api/', include('apps.proyectos_remediacion.urls')),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path('api/evaluaciones/', include('apps.evaluaciones.urls')),
    path('api/', include('apps.asignaciones_iq.urls')),
    path('api/documentos/', include('apps.documentos.urls')),
    path('api/riesgos/', include('apps.riesgos.urls')),
    # ==============================
    # 🔹 Documentación OpenAPI / Swagger / Redoc
    # ==============================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# ==============================
# 🔹 Archivos estáticos y media
# ==============================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
