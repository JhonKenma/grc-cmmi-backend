# apps/reportes/services_iq.py
"""
Servicio para generar reportes de análisis GAP de Evaluaciones Inteligentes (IQ).
El eje organizador es la Evaluacion (múltiples usuarios por evaluación).
Equivalente a ReporteGAPService de encuestas pero para IQ.
"""

from django.db.models import Avg, Count, Sum
from apps.asignaciones_iq.models import AsignacionEvaluacionIQ, CalculoNivelIQ
from apps.evaluaciones.models import Evaluacion


class ReporteGAPIQService:

    # ─────────────────────────────────────────────────────────────────────────
    # LISTAR EVALUACIONES IQ AUDITADAS DE UNA EMPRESA
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def obtener_evaluaciones_empresa(empresa_id):
        """
        Lista evaluaciones IQ que tienen al menos una asignación auditada.
        Usado para el selector del frontend.
        """
        evaluaciones_ids = AsignacionEvaluacionIQ.objects.filter(
            empresa_id=empresa_id,
            estado__in=['auditada', 'aprobada'],
            activo=True,
        ).values_list('evaluacion_id', flat=True).distinct()

        evaluaciones = Evaluacion.objects.filter(
            id__in=evaluaciones_ids
        ).prefetch_related('frameworks').order_by('-fecha_creacion')

        resultado = []
        for ev in evaluaciones:
            calculos = CalculoNivelIQ.objects.filter(
                asignacion__evaluacion=ev,
                asignacion__empresa_id=empresa_id,
                asignacion__estado__in=['auditada', 'aprobada'],
            )
            stats = calculos.aggregate(
                gap_avg=Avg('gap'),
                nivel_actual_avg=Avg('nivel_actual'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
            )
            total_usuarios = AsignacionEvaluacionIQ.objects.filter(
                evaluacion=ev,
                empresa_id=empresa_id,
                estado__in=['auditada', 'aprobada'],
            ).count()

            resultado.append({
                'evaluacion_id':         ev.id,
                'evaluacion_nombre':     ev.nombre,
                'descripcion':           ev.descripcion,
                'nivel_deseado':         ev.nivel_deseado,
                'nivel_deseado_display': ev.get_nivel_deseado_display(),
                'frameworks':            [fw.nombre for fw in ev.frameworks.all()],
                'total_usuarios':        total_usuarios,
                'gap_promedio':          float(stats['gap_avg'] or 0),
                'nivel_actual_promedio': float(stats['nivel_actual_avg'] or 0),
                'porcentaje_cumplimiento': float(stats['cumplimiento_avg'] or 0),
                'total_brechas':         calculos.filter(
                    clasificacion_gap__in=['critico', 'alto', 'medio', 'bajo']
                ).values('seccion', 'framework_id').distinct().count(),
            })

        return resultado

    # ─────────────────────────────────────────────────────────────────────────
    # REPORTE COMPLETO POR EVALUACIÓN
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def obtener_reporte_evaluacion(evaluacion_id: int, empresa_id: int):
        """
        Genera el reporte completo para una Evaluacion IQ.
        Agrupa todos los CalculoNivelIQ de todas las asignaciones auditadas.
        """
        try:
            evaluacion = Evaluacion.objects.prefetch_related('frameworks').get(id=evaluacion_id)
        except Evaluacion.DoesNotExist:
            raise ValueError('Evaluación no encontrada')

        asignaciones = AsignacionEvaluacionIQ.objects.filter(
            evaluacion=evaluacion,
            empresa_id=empresa_id,
            estado__in=['auditada', 'aprobada'],
            activo=True,
        ).select_related('usuario_asignado', 'auditado_por')

        if not asignaciones.exists():
            raise ValueError('No hay asignaciones auditadas para esta evaluación.')

        calculos = CalculoNivelIQ.objects.filter(
            asignacion__in=asignaciones
        ).select_related(
            'asignacion', 'asignacion__usuario_asignado'
        ).order_by('framework_id', 'seccion')

        if not calculos.exists():
            raise ValueError('No hay cálculos de GAP disponibles.')

        return {
            'evaluacion':              ReporteGAPIQService._build_evaluacion_info(evaluacion, asignaciones),
            'resumen':                 ReporteGAPIQService._calcular_resumen(calculos, asignaciones, evaluacion),
            'por_seccion':             ReporteGAPIQService._agrupar_por_seccion(calculos, asignaciones, evaluacion),
            'por_usuario':             ReporteGAPIQService._agrupar_por_usuario(calculos, asignaciones),
            'clasificaciones_gap':     ReporteGAPIQService._contar_clasificaciones(calculos),
            'brechas_identificadas':   ReporteGAPIQService._identificar_brechas(calculos, evaluacion),
            'distribucion_respuestas': ReporteGAPIQService._distribucion_respuestas(calculos),
        }

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_evaluacion_info(evaluacion, asignaciones):
        return {
            'id':                    evaluacion.id,
            'nombre':                evaluacion.nombre,
            'descripcion':           evaluacion.descripcion,
            'nivel_deseado':         float(evaluacion.nivel_deseado),
            'nivel_deseado_display': evaluacion.get_nivel_deseado_display(),
            'frameworks': [
                {'id': fw.id, 'nombre': fw.nombre, 'codigo': fw.codigo}
                for fw in evaluacion.frameworks.all()
            ],
            'total_usuarios': asignaciones.count(),
            'usuarios': [
                {
                    'id':            a.usuario_asignado.id,
                    'nombre':        a.usuario_asignado.get_full_name(),
                    'email':         a.usuario_asignado.email,
                    'estado':        a.estado,
                    'fecha_auditada': a.fecha_auditada,
                }
                for a in asignaciones
            ],
        }

    @staticmethod
    def _calcular_resumen(calculos, asignaciones, evaluacion):
        stats = calculos.aggregate(
            nivel_deseado_avg=Avg('nivel_deseado'),
            nivel_actual_avg=Avg('nivel_actual'),
            gap_avg=Avg('gap'),
            cumplimiento_avg=Avg('porcentaje_cumplimiento'),
        )

        secciones_unicas = calculos.values('seccion', 'framework_id').distinct()
        total_secciones  = secciones_unicas.count()
        total_frameworks = calculos.values('framework_id').distinct().count()

        secciones_con_brecha = 0
        secciones_criticas   = 0
        for sec in secciones_unicas:
            gap_prom = float(
                calculos.filter(
                    seccion=sec['seccion'], framework_id=sec['framework_id']
                ).aggregate(g=Avg('gap'))['g'] or 0
            )
            if gap_prom > 0:
                secciones_con_brecha += 1
            if gap_prom >= 2:
                secciones_criticas += 1

        return {
            'nivel_deseado_promedio':           float(stats['nivel_deseado_avg'] or 0),
            'nivel_actual_promedio':            float(stats['nivel_actual_avg'] or 0),
            'gap_promedio':                     float(stats['gap_avg'] or 0),
            'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
            'total_secciones':                  total_secciones,
            'total_frameworks':                 total_frameworks,
            'total_preguntas':                  sum(c.total_preguntas for c in calculos),
            'total_usuarios':                   asignaciones.count(),
            'secciones_con_brecha':             secciones_con_brecha,
            'secciones_sin_brecha':             total_secciones - secciones_con_brecha,
            'secciones_criticas':               secciones_criticas,
            # Compatibilidad
            'total_dimensiones':                total_secciones,
            'dimensiones_evaluadas':            total_secciones,
        }

    @staticmethod
    def _agrupar_por_seccion(calculos, asignaciones, evaluacion):
        from apps.asignaciones_iq.models import RespuestaEvaluacionIQ

        resultado = []
        secciones_unicas = (
            calculos.values('framework_id', 'framework_nombre', 'seccion')
            .distinct().order_by('framework_id', 'seccion')
        )

        CLASIF_DISPLAY = {
            'critico': 'Crítico', 'alto': 'Alto', 'medio': 'Medio',
            'bajo': 'Bajo', 'cumplido': 'Cumplido', 'superado': 'Superado',
        }

        for item in secciones_unicas:
            calculos_sec = calculos.filter(
                framework_id=item['framework_id'], seccion=item['seccion']
            )
            stats = calculos_sec.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
            )
            gap_prom = float(stats['gap_avg'] or 0)

            if gap_prom >= 3:    clasificacion = 'critico'
            elif gap_prom >= 2:  clasificacion = 'alto'
            elif gap_prom >= 1:  clasificacion = 'medio'
            elif gap_prom > 0:   clasificacion = 'bajo'
            elif gap_prom == 0:  clasificacion = 'cumplido'
            else:                clasificacion = 'superado'

            usuarios_data = []
            for calculo in calculos_sec.select_related('asignacion__usuario_asignado'):
                usuario    = calculo.asignacion.usuario_asignado
                asignacion = calculo.asignacion
                respuestas = RespuestaEvaluacionIQ.objects.filter(
                    asignacion=asignacion,
                    pregunta__seccion_general=item['seccion'],
                    estado='auditado',
                )
                usuarios_data.append({
                    'usuario_id':              usuario.id,
                    'usuario_nombre':          usuario.get_full_name(),
                    'nivel_actual':            float(calculo.nivel_actual),
                    'gap':                     float(calculo.gap),
                    'clasificacion_gap':       calculo.clasificacion_gap,
                    'clasificacion_gap_display': calculo.get_clasificacion_gap_display(),
                    'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
                    'total_preguntas':         calculo.total_preguntas,
                    'calculo_nivel_iq_id':     str(calculo.id),
                    'asignacion_id':           str(asignacion.id),
                    'respuestas': {
                        'si_cumple':      respuestas.filter(calificacion_auditor='SI_CUMPLE').count(),
                        'cumple_parcial': respuestas.filter(calificacion_auditor='CUMPLE_PARCIAL').count(),
                        'no_cumple':      respuestas.filter(calificacion_auditor='NO_CUMPLE').count(),
                        'no_aplica':      respuestas.filter(respuesta='NO_APLICA').count(),
                    },
                })

            resultado.append({
                'seccion': {
                    'id':               f"{item['framework_id']}__{item['seccion']}",
                    'nombre':           item['seccion'],
                    'codigo':           item['seccion'][:12].upper().replace(' ', '_'),
                    'framework_id':     item['framework_id'],
                    'framework_nombre': item['framework_nombre'],
                    'orden':            len(resultado),
                },
                'nivel_deseado':                    float(evaluacion.nivel_deseado),
                'nivel_actual_promedio':            float(stats['nivel_actual_avg'] or 0),
                'gap_promedio':                     gap_prom,
                'clasificacion_gap':                clasificacion,
                'clasificacion_gap_display':        CLASIF_DISPLAY[clasificacion],
                'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
                'total_usuarios_evaluados':         calculos_sec.count(),
                'tiene_brecha':                     gap_prom > 0.5,
                'tiene_proyecto_activo':            False,
                'proyecto_id':                      None,
                'total_proyectos':                  0,
                'respuestas': {
                    'si_cumple':      sum(u['respuestas']['si_cumple']      for u in usuarios_data),
                    'cumple_parcial': sum(u['respuestas']['cumple_parcial'] for u in usuarios_data),
                    'no_cumple':      sum(u['respuestas']['no_cumple']      for u in usuarios_data),
                    'no_aplica':      sum(u['respuestas']['no_aplica']      for u in usuarios_data),
                },
                'usuarios':              usuarios_data,
                'calculo_nivel_iq_ids':  [str(c.id) for c in calculos_sec],
            })

        return resultado

    @staticmethod
    def _agrupar_por_usuario(calculos, asignaciones):
        resultado = []
        for asignacion in asignaciones:
            calculos_u = calculos.filter(asignacion=asignacion)
            if not calculos_u.exists():
                continue
            stats = calculos_u.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
            )
            usuario = asignacion.usuario_asignado
            resultado.append({
                'usuario': {
                    'id':              usuario.id,
                    'nombre_completo': usuario.get_full_name(),
                    'email':           usuario.email,
                    'cargo':           getattr(usuario, 'cargo', None),
                },
                'nivel_actual_promedio':           float(stats['nivel_actual_avg'] or 0),
                'gap_promedio':                    float(stats['gap_avg'] or 0),
                'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
                'total_dimensiones_evaluadas':     calculos_u.count(),
                'dimensiones': [
                    {
                        'seccion_nombre':          c.seccion,
                        'framework_nombre':        c.framework_nombre,
                        'nivel_deseado':           float(c.nivel_deseado),
                        'nivel_actual':            float(c.nivel_actual),
                        'gap':                     float(c.gap),
                        'clasificacion_gap':       c.clasificacion_gap,
                        'porcentaje_cumplimiento': float(c.porcentaje_cumplimiento),
                    }
                    for c in calculos_u.order_by('framework_id', 'seccion')
                ],
            })
        return resultado

    @staticmethod
    def _contar_clasificaciones(calculos):
        secciones_unicas = calculos.values('seccion', 'framework_id').distinct()
        counts = {'critico': 0, 'alto': 0, 'medio': 0, 'bajo': 0, 'cumplido': 0, 'superado': 0}

        for sec in secciones_unicas:
            gap_prom = float(
                calculos.filter(
                    seccion=sec['seccion'], framework_id=sec['framework_id']
                ).aggregate(g=Avg('gap'))['g'] or 0
            )
            if gap_prom >= 3:    counts['critico']  += 1
            elif gap_prom >= 2:  counts['alto']     += 1
            elif gap_prom >= 1:  counts['medio']    += 1
            elif gap_prom > 0:   counts['bajo']     += 1
            elif gap_prom == 0:  counts['cumplido'] += 1
            else:                counts['superado'] += 1

        total = sum(counts.values()) or 1
        for key in list(counts.keys()):
            counts[f'{key}_porcentaje'] = round(counts[key] / total * 100, 1)
        return counts

    @staticmethod
    def _identificar_brechas(calculos, evaluacion):
        PRIORIDAD     = {'critico': 1, 'alto': 2, 'medio': 3, 'bajo': 4}
        CLASIF_DISPLAY = {'critico': 'Crítico', 'alto': 'Alto', 'medio': 'Medio', 'bajo': 'Bajo'}

        secciones_unicas = (
            calculos.values('seccion', 'framework_id', 'framework_nombre')
            .distinct().order_by('framework_id', 'seccion')
        )

        brechas = []
        for sec in secciones_unicas:
            calculos_sec = calculos.filter(seccion=sec['seccion'], framework_id=sec['framework_id'])
            stats = calculos_sec.aggregate(
                gap_avg=Avg('gap'),
                nivel_actual_avg=Avg('nivel_actual'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
            )
            gap_prom = float(stats['gap_avg'] or 0)

            if gap_prom >= 3:    clasificacion = 'critico'
            elif gap_prom >= 2:  clasificacion = 'alto'
            elif gap_prom >= 1:  clasificacion = 'medio'
            elif gap_prom > 0.5: clasificacion = 'bajo'
            else:                continue

            brechas.append({
                'prioridad':               PRIORIDAD[clasificacion],
                'seccion':                 sec['seccion'],
                'framework_id':            sec['framework_id'],
                'framework_nombre':        sec['framework_nombre'],
                'nivel_deseado':           float(evaluacion.nivel_deseado),
                'nivel_actual':            float(stats['nivel_actual_avg'] or 0),
                'gap':                     gap_prom,
                'clasificacion_gap':       clasificacion,
                'clasificacion_gap_display': CLASIF_DISPLAY[clasificacion],
                'porcentaje_cumplimiento': float(stats['cumplimiento_avg'] or 0),
                'total_preguntas':         sum(c.total_preguntas for c in calculos_sec),
                'respuestas_no_cumple':    sum(c.respuestas_no_cumple for c in calculos_sec),
                'calculo_nivel_iq_ids':    [str(c.id) for c in calculos_sec],
                'total_usuarios':          calculos_sec.count(),
                'tiene_proyecto_remediacion': False,
                'proyecto_remediacion_id':    None,
            })

        brechas.sort(key=lambda x: (x['prioridad'], -x['gap']))
        return brechas

    @staticmethod
    def _distribucion_respuestas(calculos):
        t = calculos.aggregate(
            si=Sum('respuestas_si_cumple'),
            parcial=Sum('respuestas_cumple_parcial'),
            no=Sum('respuestas_no_cumple'),
            na=Sum('respuestas_no_aplica'),
        )
        si, parcial, no, na = t['si'] or 0, t['parcial'] or 0, t['no'] or 0, t['na'] or 0
        total = si + parcial + no + na or 1
        return {
            'si_cumple': si, 'cumple_parcial': parcial,
            'no_cumple': no, 'no_aplica': na, 'total': total,
            'porcentajes': {
                'si_cumple':      round(si      / total * 100, 2),
                'cumple_parcial': round(parcial / total * 100, 2),
                'no_cumple':      round(no      / total * 100, 2),
                'no_aplica':      round(na      / total * 100, 2),
            },
        }

    # Compatibilidad
    @staticmethod
    def obtener_reporte_asignacion(asignacion_id: int):
        asignacion = AsignacionEvaluacionIQ.objects.get(id=asignacion_id)
        return ReporteGAPIQService.obtener_reporte_evaluacion(
            evaluacion_id=asignacion.evaluacion_id,
            empresa_id=asignacion.empresa_id,
        )

    @staticmethod
    def obtener_reportes_empresa(empresa_id):
        return ReporteGAPIQService.obtener_evaluaciones_empresa(empresa_id)