# apps/reportes/exporters/base.py

from abc import ABC, abstractmethod
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse


class BaseExporter(ABC):
    """
    Clase base para exportadores de reportes
    """
    
    def __init__(self, evaluacion, calculos):
        """
        Args:
            evaluacion: Instancia de EvaluacionEmpresa
            calculos: QuerySet de CalculoNivel
        """
        self.evaluacion = evaluacion
        self.calculos = calculos
        self.buffer = BytesIO()
    
    @abstractmethod
    def generate(self):
        """
        Genera el archivo en self.buffer
        Debe ser implementado por cada exportador
        """
        pass
    
    @abstractmethod
    def get_content_type(self):
        """
        Retorna el content-type del archivo
        """
        pass
    
    @abstractmethod
    def get_file_extension(self):
        """
        Retorna la extensión del archivo
        """
        pass
    
    def get_filename(self):
        """
        Genera el nombre del archivo
        """
        empresa_nombre = self.evaluacion.empresa.nombre.replace(' ', '_')
        fecha = datetime.now().strftime('%Y%m%d')
        extension = self.get_file_extension()
        
        return f'Reporte_Evaluacion_{empresa_nombre}_{fecha}.{extension}'
    
    def export(self):
        """
        Genera y retorna HttpResponse con el archivo
        """
        # Generar contenido
        self.generate()
        
        # Preparar buffer
        self.buffer.seek(0)
        
        # Crear respuesta HTTP
        response = HttpResponse(
            self.buffer,
            content_type=self.get_content_type()
        )
        
        response['Content-Disposition'] = f'attachment; filename="{self.get_filename()}"'
        
        return response
    
    # ═══════════════════════════════════════════════════════
    # MÉTODOS HELPER COMPARTIDOS
    # ═══════════════════════════════════════════════════════
    
    def get_estadisticas_generales(self):
        """Calcula estadísticas generales de la evaluación"""
        from django.db.models import Avg, Count
        
        stats = self.calculos.aggregate(
            nivel_deseado_avg=Avg('nivel_deseado'),
            nivel_actual_avg=Avg('nivel_actual'),
            gap_avg=Avg('gap'),
            cumplimiento_avg=Avg('porcentaje_cumplimiento'),
        )
        
        return {
            'total_dimensiones': self.calculos.values('dimension').distinct().count(),
            'total_usuarios': self.calculos.values('usuario').distinct().count(),
            'nivel_deseado_avg': round(stats['nivel_deseado_avg'] or 0, 2),
            'nivel_actual_avg': round(stats['nivel_actual_avg'] or 0, 2),
            'gap_avg': round(stats['gap_avg'] or 0, 2),
            'cumplimiento_avg': round(stats['cumplimiento_avg'] or 0, 2),
        }
    
    def get_clasificaciones_gap(self):
        """Cuenta las clasificaciones de GAP"""
        total = self.calculos.count()
        
        clasificaciones = {
            'critico': self.calculos.filter(clasificacion_gap='critico').count(),
            'alto': self.calculos.filter(clasificacion_gap='alto').count(),
            'medio': self.calculos.filter(clasificacion_gap='medio').count(),
            'bajo': self.calculos.filter(clasificacion_gap='bajo').count(),
            'cumplido': self.calculos.filter(clasificacion_gap='cumplido').count(),
            'superado': self.calculos.filter(clasificacion_gap='superado').count(),
        }
        
        # Agregar porcentajes
        keys_list = list(clasificaciones.keys())
        
        # Agregar porcentajes
        for key in keys_list:  # ← Iterar sobre la copia
            cantidad = clasificaciones[key]
            porcentaje = (cantidad / total * 100) if total > 0 else 0
            clasificaciones[f'{key}_porcentaje'] = round(porcentaje, 1)
        
        return clasificaciones
    
    def get_dimensiones_data(self):
        """Obtiene datos agrupados por dimensión"""
        from django.db.models import Avg, Count
        
        dimensiones_ids = self.calculos.values_list('dimension_id', flat=True).distinct()
        resultado = []
        
        for dimension_id in dimensiones_ids:
            calculos_dim = self.calculos.filter(dimension_id=dimension_id)
            dimension = calculos_dim.first().dimension
            
            stats = calculos_dim.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                total_usuarios=Count('usuario', distinct=True)
            )
            
            resultado.append({
                'dimension': dimension,
                'nivel_deseado': float(calculos_dim.first().nivel_deseado),
                'nivel_actual_avg': round(stats['nivel_actual_avg'] or 0, 2),
                'gap_avg': round(stats['gap_avg'] or 0, 2),
                'cumplimiento_avg': round(stats['cumplimiento_avg'] or 0, 2),
                'total_usuarios': stats['total_usuarios'],
            })
        
        return resultado
    
    def get_usuarios_data(self):
        """Obtiene datos agrupados por usuario"""
        from django.db.models import Avg, Count
        from apps.usuarios.models import Usuario
        
        usuarios_ids = self.calculos.values_list('usuario_id', flat=True).distinct()
        usuarios = Usuario.objects.filter(id__in=usuarios_ids)
        
        resultado = []
        
        for usuario in usuarios:
            calculos_usuario = self.calculos.filter(usuario=usuario)
            
            stats = calculos_usuario.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                total_dimensiones=Count('dimension', distinct=True)
            )
            
            resultado.append({
                'usuario': usuario,
                'nivel_actual_avg': round(stats['nivel_actual_avg'] or 0, 2),
                'gap_avg': round(stats['gap_avg'] or 0, 2),
                'cumplimiento_avg': round(stats['cumplimiento_avg'] or 0, 2),
                'total_dimensiones': stats['total_dimensiones'],
            })
        
        return resultado