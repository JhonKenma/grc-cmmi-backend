# apps/reportes/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import EsAdminOSuperAdmin
from .services import ReporteGAPService
from .serializers import ReporteGAPEmpresaSerializer, TopBrechasSerializer


class ReporteViewSet(viewsets.ViewSet):
    """
    ViewSet para generar reportes de análisis GAP
    """
    permission_classes = [IsAuthenticated, EsAdminOSuperAdmin]
    
    def error_response(self, message, status_code=400, errors=None):
        """Helper para respuestas de error"""
        return Response({
            'success': False,
            'message': message,
            'errors': errors
        }, status=status_code)
    
    def success_response(self, data=None, message='OK', status_code=200):
        """Helper para respuestas exitosas"""
        return Response({
            'success': True,
            'message': message,
            'data': data
        }, status=status_code)
    
    @action(detail=False, methods=['get'])
    def gap_empresa(self, request):
        """
        Genera reporte completo de GAP para una empresa
        GET /api/reportes/gap_empresa/?empresa_id={uuid}&dimension_id={uuid}
        
        Query params:
        - empresa_id (required): UUID de la empresa
        - dimension_id (optional): UUID de dimensión para filtrar
        """
        serializer = ReporteGAPEmpresaSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        empresa_id = serializer.validated_data['empresa_id']
        dimension_id = serializer.validated_data.get('dimension_id')
        
        # Validar permisos: Admin solo puede ver su empresa
        if request.user.rol == 'administrador':
            if str(request.user.empresa.id) != str(empresa_id):
                return self.error_response(
                    message='No tienes permisos para ver reportes de esta empresa',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        try:
            reporte = ReporteGAPService.obtener_reporte_empresa(
                empresa_id=empresa_id,
                dimension_id=dimension_id
            )
            
            return self.success_response(
                data=reporte,
                message='Reporte generado exitosamente'
            )
        
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.error_response(
                message='Error al generar el reporte',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def top_brechas(self, request):
        """
        Obtiene las mayores brechas (GAP) de una empresa
        GET /api/reportes/top_brechas/?empresa_id={uuid}&limite=10
        """
        serializer = TopBrechasSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        empresa_id = serializer.validated_data['empresa_id']
        limite = serializer.validated_data.get('limite', 10)
        
        # Validar permisos
        if request.user.rol == 'administrador':
            if str(request.user.empresa.id) != str(empresa_id):
                return self.error_response(
                    message='No tienes permisos para ver esta información',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        try:
            brechas = ReporteGAPService.obtener_top_brechas(
                empresa_id=empresa_id,
                limite=limite
            )
            
            return self.success_response(
                data={'brechas': brechas},
                message=f'Top {len(brechas)} brechas obtenidas'
            )
        
        except Exception as e:
            return self.error_response(
                message='Error al obtener brechas',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def tendencia_empresa(self, request):
        """
        Obtiene la tendencia de mejora de una empresa
        GET /api/reportes/tendencia_empresa/?empresa_id={uuid}
        """
        empresa_id = request.query_params.get('empresa_id')
        
        if not empresa_id:
            return self.error_response(
                message='Se requiere el parámetro empresa_id',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar permisos
        if request.user.rol == 'administrador':
            if str(request.user.empresa.id) != str(empresa_id):
                return self.error_response(
                    message='No tienes permisos para ver esta información',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        try:
            tendencia = ReporteGAPService.obtener_tendencia_empresa(empresa_id)
            
            return self.success_response(
                data=tendencia,
                message='Tendencia obtenida'
            )
        
        except Exception as e:
            return self.error_response(
                message='Error al obtener tendencia',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )