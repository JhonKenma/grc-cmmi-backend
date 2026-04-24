# apps/riesgos/services/calculo_riesgo.py
"""
Servicio de cálculo y lógica de negocio para Gestión de Riesgos.
Centraliza: matriz 5x5, ALE, clasificación, frecuencias de revisión.
"""

from decimal import Decimal


class CalculoRiesgoService:
    """
    Servicio estático con toda la lógica de cálculo de riesgos.
    No depende de modelos Django para ser testeable de forma aislada.
    """

    # ── Matriz 5x5 ─────────────────────────────────────────────────────────────

    @staticmethod
    def calcular_nivel(probabilidad: int, impacto: int) -> int:
        """
        Calcula el nivel de riesgo según la matriz 5x5.
        Resultado: 1 (mínimo) a 25 (máximo)
        """
        if not (1 <= probabilidad <= 5) or not (1 <= impacto <= 5):
            raise ValueError('Probabilidad e impacto deben estar entre 1 y 5')
        return probabilidad * impacto

    @staticmethod
    def clasificar_nivel(nivel: int) -> str:
        """
        Clasifica el nivel de riesgo.

        1-5   → bajo
        6-10  → medio
        11-15 → alto
        16-25 → crítico
        """
        if nivel <= 5:
            return 'bajo'
        elif nivel <= 10:
            return 'medio'
        elif nivel <= 15:
            return 'alto'
        else:
            return 'critico'

    @staticmethod
    def get_color_clasificacion(clasificacion: str) -> str:
        """Color HEX para representar la clasificación en dashboards."""
        colores = {
            'bajo':    '#22C55E',  # verde
            'medio':   '#EAB308',  # amarillo
            'alto':    '#F97316',  # naranja
            'critico': '#EF4444',  # rojo
        }
        return colores.get(clasificacion, '#6B7280')

    @staticmethod
    def get_matriz_completa() -> list:
        """
        Retorna la matriz 5x5 completa con clasificaciones.
        Útil para renderizar el mapa de calor en el frontend.
        """
        matriz = []
        for prob in range(5, 0, -1):
            fila = []
            for imp in range(1, 6):
                nivel = prob * imp
                clasificacion = CalculoRiesgoService.clasificar_nivel(nivel)
                fila.append({
                    'probabilidad': prob,
                    'impacto': imp,
                    'nivel': nivel,
                    'clasificacion': clasificacion,
                    'color': CalculoRiesgoService.get_color_clasificacion(clasificacion),
                })
            matriz.append(fila)
        return matriz

    # ── ALE (Annual Loss Expectancy) ───────────────────────────────────────────

    @staticmethod
    def calcular_ale(sle: Decimal, aro: Decimal) -> Decimal:
        """
        ALE = SLE × ARO

        SLE (Single Loss Expectancy): pérdida si el riesgo ocurre una vez
        ARO (Annual Rate of Occurrence): frecuencia anual (0.5 = cada 2 años)
        ALE (Annual Loss Expectancy): pérdida anual esperada

        Ejemplo: SLE=$50,000, ARO=0.5 → ALE=$25,000/año
        """
        if sle is None or aro is None:
            return None
        return Decimal(str(sle)) * Decimal(str(aro))

    # ── Frecuencia de revisión ─────────────────────────────────────────────────

    @staticmethod
    def sugerir_frecuencia_revision(clasificacion: str) -> str:
        """
        ISO 31000: sugiere frecuencia de revisión según nivel de riesgo.

        Crítico → mensual
        Alto    → trimestral
        Medio   → semestral
        Bajo    → anual
        """
        frecuencias = {
            'critico': 'mensual',
            'alto':    'trimestral',
            'medio':   'semestral',
            'bajo':    'anual',
        }
        return frecuencias.get(clasificacion, 'trimestral')

    # ── Apetito de riesgo ──────────────────────────────────────────────────────

    @staticmethod
    def evaluar_apetito(nivel_riesgo: int, apetito: int, tolerancia: int = None) -> str:
        """
        COSO ERM: evalúa si el riesgo está dentro del apetito definido.

        Retorna:
        - 'dentro_de_apetito'
        - 'requiere_tratamiento'
        - 'requiere_tratamiento_inmediato'
        - 'sin_configurar'
        """
        if apetito is None:
            return 'sin_configurar'

        if tolerancia and nivel_riesgo > tolerancia:
            return 'requiere_tratamiento_inmediato'

        if nivel_riesgo > apetito:
            return 'requiere_tratamiento'

        return 'dentro_de_apetito'

    # ── Resumen estadístico ────────────────────────────────────────────────────

    @staticmethod
    def calcular_resumen_empresa(riesgos_qs) -> dict:
        """
        Calcula estadísticas generales de riesgos de una empresa.
        Recibe un queryset de Riesgo.
        """
        from django.db.models import Avg, Count, Sum

        total = riesgos_qs.count()

        por_clasificacion = {
            'bajo':    riesgos_qs.filter(clasificacion='bajo').count(),
            'medio':   riesgos_qs.filter(clasificacion='medio').count(),
            'alto':    riesgos_qs.filter(clasificacion='alto').count(),
            'critico': riesgos_qs.filter(clasificacion='critico').count(),
        }

        por_estado = {
            'borrador':        riesgos_qs.filter(estado='borrador').count(),
            'en_revision':     riesgos_qs.filter(estado='en_revision').count(),
            'aprobado':        riesgos_qs.filter(estado='aprobado').count(),
            'en_tratamiento':  riesgos_qs.filter(estado='en_tratamiento').count(),
            'mitigado':        riesgos_qs.filter(estado='mitigado').count(),
            'aceptado':        riesgos_qs.filter(estado='aceptado').count(),
            'cerrado':         riesgos_qs.filter(estado='cerrado').count(),
        }

        stats = riesgos_qs.aggregate(
            nivel_promedio=Avg('nivel_riesgo'),
            ale_total=Sum('ale'),
        )

        return {
            'total_riesgos': total,
            'por_clasificacion': por_clasificacion,
            'por_estado': por_estado,
            'nivel_promedio': round(float(stats['nivel_promedio'] or 0), 2),
            'ale_total': float(stats['ale_total'] or 0),
            'porcentaje_criticos': round(
                (por_clasificacion['critico'] / total * 100) if total > 0 else 0, 1
            ),
        }