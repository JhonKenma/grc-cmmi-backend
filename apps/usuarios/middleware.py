# apps/usuarios/middleware.py
from django.utils import timezone
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication


class PlanExpirationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            # Excluir rutas de auth para no bloquear login/refresh
            rutas_libres = [
                '/api/auth/login/',
                '/api/auth/token/refresh/',
                '/api/auth/logout/',
            ]
            if not any(request.path.startswith(r) for r in rutas_libres):
                resultado = self._verificar_plan(request)
                if resultado:
                    return resultado

        return self.get_response(request)

    def _verificar_plan(self, request):
        """
        Verifica el plan usando el usuario ya autenticado por Django,
        en lugar de re-autenticar con JWT (más confiable).
        """
        try:
            # Usar el usuario que Django ya autenticó via JWT
            from rest_framework_simplejwt.authentication import JWTAuthentication
            from rest_framework.request import Request as DRFRequest
            from rest_framework.parsers import JSONParser

            # Crear request DRF para poder usar JWTAuthentication
            drf_request = DRFRequest(request, parsers=[JSONParser()])
            jwt_auth = JWTAuthentication()
            result = jwt_auth.authenticate(drf_request)

            if not result:
                return None  # No autenticado, dejar pasar (lo maneja IsAuthenticated)

            user, token = result

            # SuperAdmin nunca se bloquea
            if user.rol == 'superadmin':
                return None

            # Usuario sin empresa — no debería existir pero por si acaso
            if not user.empresa_id:
                return None

            # Obtener plan con select_related para evitar query extra
            from apps.empresas.models import PlanEmpresa
            try:
                plan = PlanEmpresa.objects.get(empresa_id=user.empresa_id)
            except PlanEmpresa.DoesNotExist:
                return JsonResponse({
                    'error': 'Tu empresa no tiene un plan activo. Contacta a ShieldGrid.',
                    'codigo': 'SIN_PLAN',
                }, status=403)

            if not plan.esta_activo:
                return JsonResponse({
                    'error': 'El plan de tu empresa ha expirado. Contacta a ShieldGrid para renovar.',
                    'codigo': 'PLAN_EXPIRADO',
                    'dias_restantes': 0,
                }, status=403)

            return None  # Todo OK, dejar pasar

        except Exception:
            return None