# apps/respuestas/services.py

from decimal import Decimal
from django.db.models import Avg, Count, Q
from .models import Respuesta, CalculoNivel
from apps.encuestas.models import ConfigNivelDeseado

class CalculoNivelService:
    """
    Servicio para calcular niveles de madurez y brechas (GAP)
    """
    
    @staticmethod
    def calcular_gap_asignacion(asignacion):
        """
        Calcula el GAP de una asignación con respuestas
        
        Args:
            asignacion: Instancia de Asignacion
            
        Returns:
            CalculoNivel: Registro con el cálculo del GAP
        """

        # ⭐ VALIDAR: Debe tener respuestas
        total_respuestas = Respuesta.objects.filter(
            asignacion=asignacion,
            activo=True
        ).count()
        
        if total_respuestas == 0:
            raise ValueError('La asignación no tiene respuestas registradas')
        
        # ⭐ VALIDAR: Estado debe ser 'completado' (auto o por aprobación)
        if asignacion.estado != 'completado':
            raise ValueError(f'La asignación debe estar completada. Estado actual: {asignacion.estado}')
        
        # Obtener datos
        dimension = asignacion.dimension
        empresa = asignacion.empresa
        usuario = asignacion.usuario_asignado
        evaluacion_empresa = asignacion.evaluacion_empresa
        
        # Obtener nivel deseado de la evaluación específica
        try:
            config = ConfigNivelDeseado.objects.get(
                evaluacion_empresa=evaluacion_empresa,
                dimension=dimension,
                activo=True
            )
            nivel_deseado = Decimal(str(config.nivel_deseado))
        except ConfigNivelDeseado.DoesNotExist:
            # Fallback: Buscar por empresa (compatibilidad)
            try:
                config = ConfigNivelDeseado.objects.get(
                    empresa=empresa,
                    dimension=dimension,
                    evaluacion_empresa__isnull=True,
                    activo=True
                )
                nivel_deseado = Decimal(str(config.nivel_deseado))
            except ConfigNivelDeseado.DoesNotExist:
                nivel_deseado = Decimal('3.0')  # Default CMMI nivel 3
        
        # Obtener respuestas de esta asignación
        respuestas = Respuesta.objects.filter(
            asignacion=asignacion,
            activo=True
        )
        
        # Calcular nivel actual (promedio de nivel_madurez, excluyendo NO_APLICA)
        respuestas_validas = respuestas.exclude(respuesta='NO_APLICA')
        
        if respuestas_validas.exists():
            nivel_actual = respuestas_validas.aggregate(
                promedio=Avg('nivel_madurez')
            )['promedio'] or Decimal('0')
        else:
            nivel_actual = Decimal('0')
        
        # Contar tipos de respuestas
        total_preguntas = respuestas.count()
        respuestas_si_cumple = respuestas.filter(respuesta='SI_CUMPLE').count()
        respuestas_cumple_parcial = respuestas.filter(respuesta='CUMPLE_PARCIAL').count()
        respuestas_no_cumple = respuestas.filter(respuesta='NO_CUMPLE').count()
        respuestas_no_aplica = respuestas.filter(respuesta='NO_APLICA').count()
        
        # Calcular porcentaje de cumplimiento
        respuestas_aplicables = total_preguntas - respuestas_no_aplica
        if respuestas_aplicables > 0:
            porcentaje_cumplimiento = (
                (respuestas_si_cumple + respuestas_cumple_parcial) / respuestas_aplicables
            ) * 100
        else:
            porcentaje_cumplimiento = Decimal('0')
        
        # Calcular GAP
        gap = nivel_deseado - nivel_actual
        
        # Clasificar GAP
        if gap >= 3:
            clasificacion_gap = 'critico'
        elif gap >= 2:
            clasificacion_gap = 'alto'
        elif gap >= 1:
            clasificacion_gap = 'medio'
        elif gap > 0:
            clasificacion_gap = 'bajo'
        elif gap == 0:
            clasificacion_gap = 'cumplido'
        else:
            clasificacion_gap = 'superado'
        
        # Crear o actualizar el registro de cálculo
        calculo, created = CalculoNivel.objects.update_or_create(
            asignacion=asignacion,
            defaults={
                'evaluacion_empresa': evaluacion_empresa,
                'dimension': dimension,
                'empresa': empresa,
                'usuario': usuario,
                'nivel_deseado': nivel_deseado,
                'nivel_actual': nivel_actual,
                'gap': gap,
                'clasificacion_gap': clasificacion_gap,
                'total_preguntas': total_preguntas,
                'respuestas_si_cumple': respuestas_si_cumple,
                'respuestas_cumple_parcial': respuestas_cumple_parcial,
                'respuestas_no_cumple': respuestas_no_cumple,
                'respuestas_no_aplica': respuestas_no_aplica,
                'porcentaje_cumplimiento': porcentaje_cumplimiento,
            }
        )
        
        accion = "creado" if created else "actualizado"
        print(f"✅ GAP {accion}: Deseado={nivel_deseado}, Actual={nivel_actual:.2f}, GAP={gap:.2f} ({clasificacion_gap})")
        
        return calculo
    @staticmethod
    def recalcular_evaluacion(evaluacion_empresa):
        """
        Recalcula todos los GAPs de una evaluación específica
        
        Args:
            evaluacion_empresa: Instancia de EvaluacionEmpresa
        """
        from apps.asignaciones.models import Asignacion
        
        asignaciones = Asignacion.objects.filter(
            evaluacion_empresa=evaluacion_empresa,
            estado='completado',
            activo=True
        )
        
        resultados = {
            'total': asignaciones.count(),
            'exitosos': 0,
            'errores': 0
        }
        
        for asignacion in asignaciones:
            try:
                CalculoNivelService.calcular_gap_asignacion(asignacion)
                resultados['exitosos'] += 1
            except Exception as e:
                print(f"❌ Error en asignación {asignacion.id}: {str(e)}")
                resultados['errores'] += 1
        
        return resultados