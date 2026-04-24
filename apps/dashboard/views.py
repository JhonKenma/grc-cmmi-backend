# apps/dashboard/views.py
"""
Vista única del dashboard.
El serializer y los datos cambian según el rol del usuario autenticado.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .services.superadmin import SuperAdminDashboardService
from .services.admin import AdminDashboardService
from .services.auditor import AuditorDashboardService
from .services.usuario import UsuarioDashboardService

from .serializers.superadmin import SuperAdminDashboardSerializer
from .serializers.admin import AdminDashboardSerializer
from .serializers.auditor import AuditorDashboardSerializer
from .serializers.usuario import UsuarioDashboardSerializer


# Mapa rol → (service_class, serializer_class)
_ROL_MAP = {
    "superadmin":      (SuperAdminDashboardService, SuperAdminDashboardSerializer),
    "administrador":   (AdminDashboardService,      AdminDashboardSerializer),
    "auditor":         (AuditorDashboardService,    AuditorDashboardSerializer),
    "usuario":         (UsuarioDashboardService,    UsuarioDashboardSerializer),
    "analista_riesgos":(UsuarioDashboardService,    UsuarioDashboardSerializer),
}


class DashboardSummaryView(APIView):
    """
    GET /api/v1/dashboard/summary/

    Retorna el resumen del dashboard adaptado al rol del usuario autenticado.

    Estructura de respuesta común:
    {
        "rol": "<rol>",
        "kpis": { ... },
        "alertas": [ ... ],
        "charts": { ... }
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        rol = user.rol

        entry = _ROL_MAP.get(rol)
        if not entry:
            return Response(
                {"detail": f"Rol '{rol}' no tiene dashboard configurado."},
                status=400,
            )

        ServiceClass, SerializerClass = entry

        # SuperAdmin no necesita empresa; el resto sí
        if rol == "superadmin":
            service = ServiceClass()
        else:
            if not user.empresa:
                return Response(
                    {"detail": "El usuario no tiene empresa asignada."},
                    status=400,
                )
            service = ServiceClass(user)

        data = service.get_summary()
        serializer = SerializerClass(data)
        return Response({"rol": rol, **serializer.data})