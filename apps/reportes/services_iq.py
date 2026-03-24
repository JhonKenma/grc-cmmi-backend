# apps/reportes/services_iq.py
"""
Servicio para generar reportes de análisis GAP de Evaluaciones Inteligentes (IQ).
Paralelo a ReporteGAPService pero usando CalculoNivelIQ en lugar de CalculoNivel.
El eje organizador es seccion_general + framework en lugar de Dimension.
"""

from django.db.models import Avg, Count, Sum, Q
from apps.asignaciones_iq.models import AsignacionEvaluacionIQ, CalculoNivelIQ
from apps.empresas.models import Empresa


class ReporteGAPIQService:
    """
    Genera el reporte GAP completo para una AsignacionEvaluacionIQ auditada.

    Estructura de salida (compatible con los componentes frontend existentes):
    {
        asignacion: {...},
        resumen: {...},
        por_seccion: [           ← equivalente a por_dimension en encuestas
            {
                seccion: { nombre, framework_id, framework_nombre },
                nivel_deseado,
                nivel_actual_promedio,
                gap_promedio,
                clasificacion_gap,
                porcentaje_cumplimiento_promedio,
                tiene_brecha,            ← True si gap_promedio > 0.5
                severidad_brecha,        ← 'critica' | 'alta' | 'media' | 'baja' | 'ninguna'
                usuarios: [...],
            }
        ],
        por_usuario: [...],
        clasificaciones_gap: { critico, alto, medio, bajo, cumplido, superado },
        brechas_identificadas: [   ← Lista ordenada de brechas para remediación
            {
                seccion,
                framework_nombre,
                gap,
                clasificacion_gap,
                nivel_deseado,
                nivel_actual,
                porcentaje_cumplimiento,
                calculo_nivel_iq_id,
                prioridad,              ← 1 = más urgente
            }
        ],
        distribucion_respuestas: {...},
    }
    """

    @staticmethod
    def obtener_reporte_asignacion(asignacion_id: int):
        """
        Genera el reporte completo para una asignación IQ auditada.
        """
        try:
            asignacion = AsignacionEvaluacionIQ.objects.select_related(
                'evaluacion', 'usuario_asignado', 'empresa',
                'auditado_por', 'asignado_por'
            ).get(id=asignacion_id)
        except AsignacionEvaluacionIQ.DoesNotExist:
            raise ValueError('Asignación no encontrada')

        if asignacion.estado not in ['auditada', 'aprobada']:
            raise ValueError(
                f'La asignación debe estar auditada para generar el reporte. '
                f'Estado actual: {asignacion.get_estado_display()}'
            )

        calculos = CalculoNivelIQ.objects.filter(
            asignacion=asignacion
        ).order_by('framework_id', 'seccion')

        if not calculos.exists():
            raise ValueError(
                'No hay cálculos de GAP disponibles. '
                'Asegúrate de que la auditoría se haya cerrado correctamente.'
            )

        reporte = {
            'asignacion': ReporteGAPIQService._build_asignacion_info(asignacion),
            'resumen':    ReporteGAPIQService._calcular_resumen(calculos, asignacion),
            'por_seccion': ReporteGAPIQService._agrupar_por_seccion(calculos, asignacion),
            'por_usuario': ReporteGAPIQService._agrupar_por_usuario(calculos, asignacion),
            'clasificaciones_gap': ReporteGAPIQService._contar_clasificaciones(calculos),
            'brechas_identificadas': ReporteGAPIQService._identificar_brechas(calculos),
            'distribucion_respuestas': ReporteGAPIQService._distribucion_respuestas(calculos),
        }

        return reporte

    # ─────────────────────────────────────────────────────────────────────────
    # INFO ASIGNACIÓN
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_asignacion_info(asignacion):
        return {
            'id': asignacion.id,
            'evaluacion_nombre': asignacion.evaluacion.nombre,
            'evaluacion_descripcion': asignacion.evaluacion.descripcion,
            'empresa': asignacion.empresa.nombre,
            'usuario': asignacion.usuario_asignado.get_full_name(),
            'usuario_email': asignacion.usuario_asignado.email,
            'estado': asignacion.estado,
            'estado_display': asignacion.get_estado_display(),
            'fecha_asignacion': asignacion.fecha_asignacion,
            'fecha_inicio': asignacion.fecha_inicio,
            'fecha_limite': asignacion.fecha_limite,
            'fecha_completado': asignacion.fecha_completado,
            'fecha_auditada': asignacion.fecha_auditada,
            'auditado_por': (
                asignacion.auditado_por.get_full_name()
                if asignacion.auditado_por else None
            ),
            'nivel_deseado': float(asignacion.evaluacion.nivel_deseado),
            'nivel_deseado_display': asignacion.evaluacion.get_nivel_deseado_display(),
            'frameworks': [
                fw.nombre for fw in asignacion.evaluacion.frameworks.all()
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # RESUMEN GENERAL
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _calcular_resumen(calculos, asignacion):
        stats = calculos.aggregate(
            nivel_deseado_avg=Avg('nivel_deseado'),
            nivel_actual_avg=Avg('nivel_actual'),
            gap_avg=Avg('gap'),
            cumplimiento_avg=Avg('porcentaje_cumplimiento'),
        )

        total_secciones    = calculos.values('seccion').distinct().count()
        total_frameworks   = calculos.values('framework_id').distinct().count()
        secciones_con_brecha = calculos.filter(gap__gt=0).values('seccion').distinct().count()
        secciones_criticas   = calculos.filter(clasificacion_gap__in=['critico', 'alto']).values('seccion').distinct().count()

        return {
            # Métricas de niveles
            'nivel_deseado_promedio':         float(stats['nivel_deseado_avg'] or 0),
            'nivel_actual_promedio':          float(stats['nivel_actual_avg'] or 0),
            'gap_promedio':                   float(stats['gap_avg'] or 0),
            'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),

            # Conteos
            'total_secciones':         total_secciones,
            'total_frameworks':        total_frameworks,
            'total_preguntas':         sum(c.total_preguntas for c in calculos),
            'secciones_con_brecha':    secciones_con_brecha,
            'secciones_sin_brecha':    total_secciones - secciones_con_brecha,
            'secciones_criticas':      secciones_criticas,

            # Para compatibilidad con ResumenGeneral.tsx
            'total_dimensiones':       total_secciones,
            'dimensiones_evaluadas':   total_secciones,
            'total_usuarios':          1,  # IQ es 1 usuario por asignación
        }

    # ─────────────────────────────────────────────────────────────────────────
    # POR SECCIÓN (equivalente a por_dimension en encuestas)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _agrupar_por_seccion(calculos, asignacion):
        from apps.asignaciones_iq.models import RespuestaEvaluacionIQ

        resultado = []

        # Agrupar por framework + seccion
        frameworks_secciones = (
            calculos.values('framework_id', 'framework_nombre', 'seccion')
            .distinct()
            .order_by('framework_id', 'seccion')
        )

        for item in frameworks_secciones:
            calculo = calculos.filter(
                framework_id=item['framework_id'],
                seccion=item['seccion']
            ).first()

            if not calculo:
                continue

            gap = float(calculo.gap)

            # Clasificar severidad de brecha (para remediación)
            if gap >= 3:
                severidad = 'critica'
            elif gap >= 2:
                severidad = 'alta'
            elif gap >= 1:
                severidad = 'media'
            elif gap > 0.5:
                severidad = 'baja'
            else:
                severidad = 'ninguna'

            # Respuestas detalladas de la sección
            respuestas_seccion = RespuestaEvaluacionIQ.objects.filter(
                asignacion=asignacion,
                pregunta__seccion_general=item['seccion'],
                estado='auditado',
            )

            respuestas_resumen = {
                'si_cumple':      respuestas_seccion.filter(calificacion_auditor='SI_CUMPLE').count(),
                'cumple_parcial': respuestas_seccion.filter(calificacion_auditor='CUMPLE_PARCIAL').count(),
                'no_cumple':      respuestas_seccion.filter(calificacion_auditor='NO_CUMPLE').count(),
                'no_aplica':      respuestas_seccion.filter(respuesta='NO_APLICA').count(),
            }

            resultado.append({
                # Identificador de sección (shape compatible con frontend)
                'seccion': {
                    'id':               f"{item['framework_id']}__{item['seccion']}",
                    'nombre':           item['seccion'],
                    'codigo':           item['seccion'][:10].upper().replace(' ', '_'),
                    'framework_id':     item['framework_id'],
                    'framework_nombre': item['framework_nombre'],
                    'orden':            len(resultado),
                },
                # Métricas
                'nivel_deseado':                      float(calculo.nivel_deseado),
                'nivel_actual_promedio':              float(calculo.nivel_actual),
                'gap_promedio':                       gap,
                'clasificacion_gap':                  calculo.clasificacion_gap,
                'clasificacion_gap_display':          calculo.get_clasificacion_gap_display(),
                'porcentaje_cumplimiento_promedio':   float(calculo.porcentaje_cumplimiento),

                # Brecha
                'tiene_brecha':    gap > 0.5,
                'severidad_brecha': severidad,

                # Conteos
                'total_preguntas':        calculo.total_preguntas,
                'total_usuarios_evaluados': 1,

                # Para remediación (needed by TablaDetalleDimensiones)
                'tiene_proyecto_activo': False,   # Se actualizará cuando exista remediación IQ
                'proyecto_id':           None,
                'total_proyectos':       0,

                # Detalle de respuestas
                'respuestas': respuestas_resumen,

                # Usuario único de esta asignación
                'usuarios': [{
                    'usuario_id':              asignacion.usuario_asignado.id,
                    'usuario_nombre':          asignacion.usuario_asignado.get_full_name(),
                    'nivel_actual':            float(calculo.nivel_actual),
                    'gap':                     gap,
                    'clasificacion_gap':       calculo.clasificacion_gap,
                    'clasificacion_gap_display': calculo.get_clasificacion_gap_display(),
                    'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
                    'total_preguntas':         calculo.total_preguntas,
                    'calculo_nivel_iq_id':     str(calculo.id),
                    'asignacion_id':           str(asignacion.id),
                    'respuestas':              respuestas_resumen,
                }],

                # ID del cálculo para remediación futura
                'calculo_nivel_iq_id': str(calculo.id),
            })

        return resultado

    # ─────────────────────────────────────────────────────────────────────────
    # POR USUARIO (en IQ siempre es 1 usuario por asignación)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _agrupar_por_usuario(calculos, asignacion):
        stats = calculos.aggregate(
            nivel_actual_avg=Avg('nivel_actual'),
            gap_avg=Avg('gap'),
            cumplimiento_avg=Avg('porcentaje_cumplimiento'),
        )

        usuario = asignacion.usuario_asignado

        secciones_detalle = []
        for calculo in calculos.order_by('framework_id', 'seccion'):
            secciones_detalle.append({
                'seccion_nombre':          calculo.seccion,
                'framework_nombre':        calculo.framework_nombre,
                'nivel_deseado':           float(calculo.nivel_deseado),
                'nivel_actual':            float(calculo.nivel_actual),
                'gap':                     float(calculo.gap),
                'clasificacion_gap':       calculo.clasificacion_gap,
                'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
            })

        return [{
            'usuario': {
                'id':             usuario.id,
                'nombre_completo': usuario.get_full_name(),
                'email':          usuario.email,
                'cargo':          getattr(usuario, 'cargo', None),
            },
            'nivel_actual_promedio':           float(stats['nivel_actual_avg'] or 0),
            'gap_promedio':                    float(stats['gap_avg'] or 0),
            'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
            'total_dimensiones_evaluadas':     calculos.count(),
            'dimensiones': secciones_detalle,
        }]

    # ─────────────────────────────────────────────────────────────────────────
    # CLASIFICACIONES GAP (conteo por sección, no por usuario)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _contar_clasificaciones(calculos):
        total = calculos.count() or 1
        counts = {
            'critico':  calculos.filter(clasificacion_gap='critico').count(),
            'alto':     calculos.filter(clasificacion_gap='alto').count(),
            'medio':    calculos.filter(clasificacion_gap='medio').count(),
            'bajo':     calculos.filter(clasificacion_gap='bajo').count(),
            'cumplido': calculos.filter(clasificacion_gap='cumplido').count(),
            'superado': calculos.filter(clasificacion_gap='superado').count(),
        }
        # Agregar porcentajes (compatibilidad con PDFExporter)
        for key in list(counts.keys()):
            counts[f'{key}_porcentaje'] = round(counts[key] / total * 100, 1)

        return counts

    # ─────────────────────────────────────────────────────────────────────────
    # BRECHAS IDENTIFICADAS (para remediación / mitigación)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _identificar_brechas(calculos):
        """
        Devuelve las secciones con brecha (gap > 0) ordenadas por prioridad:
        1. Crítico  (gap >= 3) → acción inmediata
        2. Alto     (gap >= 2)
        3. Medio    (gap >= 1)
        4. Bajo     (gap >  0.5)

        Las secciones 'cumplido' y 'superado' se omiten.
        """
        brechas_qs = calculos.filter(
            clasificacion_gap__in=['critico', 'alto', 'medio', 'bajo']
        ).order_by('-gap')

        PRIORIDAD = {'critico': 1, 'alto': 2, 'medio': 3, 'bajo': 4}

        brechas = []
        for idx, calculo in enumerate(brechas_qs, start=1):
            brechas.append({
                'prioridad':               PRIORIDAD.get(calculo.clasificacion_gap, 5),
                'seccion':                 calculo.seccion,
                'framework_id':            calculo.framework_id,
                'framework_nombre':        calculo.framework_nombre,
                'nivel_deseado':           float(calculo.nivel_deseado),
                'nivel_actual':            float(calculo.nivel_actual),
                'gap':                     float(calculo.gap),
                'clasificacion_gap':       calculo.clasificacion_gap,
                'clasificacion_gap_display': calculo.get_clasificacion_gap_display(),
                'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
                'total_preguntas':         calculo.total_preguntas,
                'respuestas_no_cumple':    calculo.respuestas_no_cumple,
                'calculo_nivel_iq_id':     str(calculo.id),
                # Campos para futuro módulo de remediación IQ
                'tiene_proyecto_remediacion': False,
                'proyecto_remediacion_id':    None,
            })

        # Ordenar: primero por prioridad, luego por gap descendente
        brechas.sort(key=lambda x: (x['prioridad'], -x['gap']))
        return brechas

    # ─────────────────────────────────────────────────────────────────────────
    # DISTRIBUCIÓN DE RESPUESTAS
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _distribucion_respuestas(calculos):
        totales = calculos.aggregate(
            si=Sum('respuestas_si_cumple'),
            parcial=Sum('respuestas_cumple_parcial'),
            no=Sum('respuestas_no_cumple'),
            na=Sum('respuestas_no_aplica'),
        )

        si      = totales['si']      or 0
        parcial = totales['parcial'] or 0
        no      = totales['no']      or 0
        na      = totales['na']      or 0
        total   = si + parcial + no + na or 1

        return {
            'si_cumple':      si,
            'cumple_parcial': parcial,
            'no_cumple':      no,
            'no_aplica':      na,
            'total':          total,
            'porcentajes': {
                'si_cumple':      round(si      / total * 100, 2),
                'cumple_parcial': round(parcial / total * 100, 2),
                'no_cumple':      round(no      / total * 100, 2),
                'no_aplica':      round(na      / total * 100, 2),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # HELPER: reporte empresa (todas las asignaciones auditadas)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def obtener_reportes_empresa(empresa_id):
        """
        Lista todas las asignaciones IQ auditadas de una empresa con su GAP.
        Útil para el selector de evaluaciones en el frontend.
        """
        asignaciones = AsignacionEvaluacionIQ.objects.filter(
            empresa_id=empresa_id,
            estado__in=['auditada', 'aprobada'],
            activo=True,
        ).select_related('evaluacion', 'usuario_asignado', 'auditado_por').order_by('-fecha_auditada')

        resultado = []
        for a in asignaciones:
            calculos = CalculoNivelIQ.objects.filter(asignacion=a)
            stats    = calculos.aggregate(
                gap_avg=Avg('gap'),
                nivel_actual_avg=Avg('nivel_actual'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
            )
            resultado.append({
                'asignacion_id':    a.id,
                'evaluacion_nombre': a.evaluacion.nombre,
                'usuario':          a.usuario_asignado.get_full_name(),
                'fecha_auditada':   a.fecha_auditada,
                'estado':           a.estado,
                'gap_promedio':     float(stats['gap_avg'] or 0),
                'nivel_actual_promedio': float(stats['nivel_actual_avg'] or 0),
                'porcentaje_cumplimiento': float(stats['cumplimiento_avg'] or 0),
                'total_brechas':    calculos.filter(
                    clasificacion_gap__in=['critico', 'alto', 'medio', 'bajo']
                ).count(),
            })

        return resultado