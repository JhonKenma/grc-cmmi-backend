# apps/core/mixins.py
from rest_framework.response import Response
from rest_framework import status

class EmpresaQueryMixin:
    """
    Mixin para filtrar automáticamente por empresa del usuario
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superuser ve todo
        if user.is_superuser:
            return queryset
        
        # Filtrar por empresa del usuario
        if hasattr(queryset.model, 'empresa'):
            return queryset.filter(empresa=user.empresa)
        
        return queryset

class ResponseMixin:
    """
    Mixin para respuestas estandarizadas
    """
    def success_response(self, data=None, message='Operación exitosa', status_code=status.HTTP_200_OK):
        return Response({
            'success': True,
            'message': message,
            'data': data
        }, status=status_code)
    
    def error_response(self, message='Error en la operación', errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        return Response({
            'success': False,
            'message': message,
            'errors': errors
        }, status=status_code)