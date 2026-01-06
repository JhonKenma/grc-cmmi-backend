# apps/reportes/services.py

from decimal import Decimal
from django.db.models import Avg, Count, Q, Sum
from apps.respuestas.models import CalculoNivel, Respuesta
from apps.asignaciones.models import Asignacion
from apps.encuestas.models import ConfigNivelDeseado, Dimension
from apps.empresas.models import Empresa


class ReporteGAPService:
    """Servicio para generar reportes de análisis GAP"""
    
    @staticmethod
    def obtener_reporte_empresa(empresa_id, dimension_id=None):
        """
        Genera reporte de GAP para toda una empresa
        
        Args:
            empresa_id: UUID de la empresa
            dimension_id: UUID de dimensión (opcional, para filtrar)
            
        Returns:
            dict con estructura del reporte
        """
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            raise ValueError('Empresa no encontrada')
        
        # Filtrar cálculos
        calculos = CalculoNivel.objects.filter(
            empresa=empresa,
            activo=True
        ).select_related(
            'usuario',
            'dimension',
            'asignacion'
        )
        
        if dimension_id:
            calculos = calculos.filter(dimension_id=dimension_id)
        
        # Obtener dimensiones involucradas
        dimensiones = Dimension.objects.filter(
            id__in=calculos.values_list('dimension_id', flat=True)
        ).distinct()
        
        # Construir reporte
        reporte = {
            'empresa': {
                'id': str(empresa.id),
                'nombre': empresa.nombre,
                'ruc': empresa.ruc,
            },
            'fecha_generacion': Asignacion.objects.filter(
                empresa=empresa,
                estado='completado'
            ).order_by('-fecha_completado').first().fecha_completado if calculos.exists() else None,
            'resumen_general': ReporteGAPService._calcular_resumen_general(calculos),
            'por_dimension': ReporteGAPService._agrupar_por_dimension(calculos, dimensiones),
            'por_usuario': ReporteGAPService._agrupar_por_usuario(calculos),
            'clasificaciones': ReporteGAPService._contar_clasificaciones(calculos),
            'total_evaluaciones': calculos.count(),
        }
        
        return reporte
    
    @staticmethod
    def _calcular_resumen_general(calculos):
        """Calcula métricas generales del GAP"""
        if not calculos.exists():
            return {
                'nivel_deseado_promedio': 0,
                'nivel_actual_promedio': 0,
                'gap_promedio': 0,
                'porcentaje_cumplimiento_promedio': 0,
            }
        
        stats = calculos.aggregate(
            nivel_deseado_avg=Avg('nivel_deseado'),
            nivel_actual_avg=Avg('nivel_actual'),
            gap_avg=Avg('gap'),
            cumplimiento_avg=Avg('porcentaje_cumplimiento'),
        )
        
        return {
            'nivel_deseado_promedio': float(stats['nivel_deseado_avg'] or 0),
            'nivel_actual_promedio': float(stats['nivel_actual_avg'] or 0),
            'gap_promedio': float(stats['gap_avg'] or 0),
            'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
        }
    
    @staticmethod
    def _agrupar_por_dimension(calculos, dimensiones):
        """Agrupa resultados por dimensión"""
        resultado = []
        
        for dimension in dimensiones:
            calculos_dim = calculos.filter(dimension=dimension)
            
            if not calculos_dim.exists():
                continue
            
            # Obtener configuración de nivel deseado
            try:
                config = ConfigNivelDeseado.objects.get(
                    dimension=dimension,
                    empresa=calculos_dim.first().empresa
                )
                nivel_deseado = float(config.nivel_deseado)
            except ConfigNivelDeseado.DoesNotExist:
                nivel_deseado = 3.0
            
            stats = calculos_dim.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                total_usuarios=Count('usuario', distinct=True),
            )
            
            resultado.append({
                'dimension': {
                    'id': str(dimension.id),
                    'codigo': dimension.codigo,
                    'nombre': dimension.nombre,
                },
                'nivel_deseado': nivel_deseado,
                'nivel_actual_promedio': float(stats['nivel_actual_avg'] or 0),
                'gap_promedio': float(stats['gap_avg'] or 0),
                'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
                'total_usuarios_evaluados': stats['total_usuarios'],
                'usuarios': ReporteGAPService._obtener_usuarios_dimension(calculos_dim),
            })
        
        return resultado
    
    @staticmethod
    def _obtener_usuarios_dimension(calculos_dim):
        """Obtiene detalle de usuarios en una dimensión"""
        usuarios = []
        
        for calculo in calculos_dim:
            usuarios.append({
                'usuario': {
                    'id': calculo.usuario.id,
                    'nombre_completo': calculo.usuario.nombre_completo,
                    'email': calculo.usuario.email,
                },
                'nivel_actual': float(calculo.nivel_actual),
                'gap': float(calculo.gap),
                'clasificacion_gap': calculo.get_clasificacion_gap_display(),
                'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
                'fecha_evaluacion': calculo.asignacion.fecha_completado,
                'total_preguntas': calculo.total_preguntas,
                'respuestas': {
                    'si_cumple': calculo.respuestas_si_cumple,
                    'cumple_parcial': calculo.respuestas_cumple_parcial,
                    'no_cumple': calculo.respuestas_no_cumple,
                    'no_aplica': calculo.respuestas_no_aplica,
                }
            })
        
        return usuarios
    
    @staticmethod
    def _agrupar_por_usuario(calculos):
        """Agrupa resultados por usuario"""
        from django.contrib.auth import get_user_model
        Usuario = get_user_model()
        
        usuarios_ids = calculos.values_list('usuario_id', flat=True).distinct()
        usuarios = Usuario.objects.filter(id__in=usuarios_ids)
        
        resultado = []
        
        for usuario in usuarios:
            calculos_usuario = calculos.filter(usuario=usuario)
            
            stats = calculos_usuario.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                total_dimensiones=Count('dimension', distinct=True),
            )
            
            resultado.append({
                'usuario': {
                    'id': usuario.id,
                    'nombre_completo': usuario.nombre_completo,
                    'email': usuario.email,
                    'cargo': usuario.cargo,
                },
                'nivel_actual_promedio': float(stats['nivel_actual_avg'] or 0),
                'gap_promedio': float(stats['gap_avg'] or 0),
                'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
                'total_dimensiones_evaluadas': stats['total_dimensiones'],
                'dimensiones': [
                    {
                        'dimension': {
                            'id': str(c.dimension.id),
                            'nombre': c.dimension.nombre,
                        },
                        'nivel_actual': float(c.nivel_actual),
                        'gap': float(c.gap),
                        'clasificacion': c.get_clasificacion_gap_display(),
                    }
                    for c in calculos_usuario
                ]
            })
        
        return resultado
    
    @staticmethod
    def _contar_clasificaciones(calculos):
        """Cuenta las clasificaciones de GAP"""
        return {
            'critico': calculos.filter(clasificacion_gap='critico').count(),
            'alto': calculos.filter(clasificacion_gap='alto').count(),
            'medio': calculos.filter(clasificacion_gap='medio').count(),
            'bajo': calculos.filter(clasificacion_gap='bajo').count(),
            'cumplido': calculos.filter(clasificacion_gap='cumplido').count(),
            'superado': calculos.filter(clasificacion_gap='superado').count(),
        }
    
    @staticmethod
    def obtener_top_brechas(empresa_id, limite=10):
        """
        Obtiene las mayores brechas (GAP) de la empresa
        
        Args:
            empresa_id: UUID de la empresa
            limite: Número de resultados
            
        Returns:
            Lista de brechas ordenadas de mayor a menor
        """
        calculos = CalculoNivel.objects.filter(
            empresa_id=empresa_id,
            activo=True
        ).select_related(
            'usuario',
            'dimension'
        ).order_by('-gap')[:limite]
        
        return [
            {
                'usuario': c.usuario.nombre_completo,
                'dimension': c.dimension.nombre,
                'nivel_deseado': float(c.nivel_deseado),
                'nivel_actual': float(c.nivel_actual),
                'gap': float(c.gap),
                'clasificacion': c.get_clasificacion_gap_display(),
            }
            for c in calculos
        ]
    
    @staticmethod
    def obtener_tendencia_empresa(empresa_id):
        """
        Calcula la tendencia de mejora de la empresa
        (Comparando evaluaciones antiguas vs recientes)
        """
        # Por ahora retorna estructura básica
        # Se puede expandir cuando haya múltiples evaluaciones en el tiempo
        return {
            'mensaje': 'Funcionalidad de tendencias en desarrollo',
            'requiere_multiples_evaluaciones': True,
        }