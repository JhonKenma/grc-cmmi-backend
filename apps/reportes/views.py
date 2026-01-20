# apps/reportes/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg

from apps.core.permissions import EsAdminOSuperAdmin
from apps.respuestas.models import CalculoNivel
from .services import ReporteGAPService
from .serializers import ReporteGAPEmpresaSerializer, TopBrechasSerializer

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from datetime import datetime

from django.db.models import Avg



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
        print(f"🔍 ===== DEBUG GAP EMPRESA =====")
        print(f"🔍 Request recibido")
        print(f"🔍 Query params: {request.query_params}")
        print(f"🔍 Usuario: {request.user}")
        print(f"🔍 Rol usuario: {request.user.rol if request.user else 'No autenticado'}")
        
        serializer = ReporteGAPEmpresaSerializer(data=request.query_params)
        
        if not serializer.is_valid():
            print(f"❌ ERRORES DE VALIDACIÓN: {serializer.errors}")
            return self.error_response(
                message='Parámetros inválidos',
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"✅ Validación exitosa")
        
        empresa_id = serializer.validated_data['empresa_id']
        dimension_id = serializer.validated_data.get('dimension_id')
        
        print(f"🔍 Empresa ID: {empresa_id}")
        print(f"🔍 Dimensión ID: {dimension_id}")
        
        # Validar permisos: Admin solo puede ver su empresa
        if request.user.rol == 'administrador':
            print(f"🔍 Usuario es administrador, validando empresa...")
            print(f"🔍 Empresa del usuario: {request.user.empresa.id if request.user.empresa else 'Sin empresa'}")
            
            if str(request.user.empresa.id) != str(empresa_id):
                print(f"❌ Permiso denegado: empresa no coincide")
                return self.error_response(
                    message='No tienes permisos para ver reportes de esta empresa',
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        try:
            print(f"🔍 Llamando a ReporteGAPService.obtener_reporte_empresa...")
            
            reporte = ReporteGAPService.obtener_reporte_empresa(
                empresa_id=empresa_id,
                dimension_id=dimension_id
            )
            
            print(f"✅ Reporte generado exitosamente")
            print(f"✅ Total evaluaciones: {reporte.get('total_evaluaciones', 0)}")
            
            return self.success_response(
                data=reporte,
                message='Reporte generado exitosamente'
            )
        
        except ValueError as e:
            print(f"❌ ValueError: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            
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
            
    @action(detail=False, methods=['get'])
    def gap_evaluacion(self, request):
        """
        Genera reporte completo de GAP para una evaluación específica
        GET /api/reportes/gap_evaluacion/?evaluacion_empresa_id={uuid}
        """
        from apps.encuestas.models import EvaluacionEmpresa
        
        evaluacion_empresa_id = request.query_params.get('evaluacion_empresa_id')
        
        if not evaluacion_empresa_id:
            return self.error_response(
                message='Parámetro evaluacion_empresa_id es requerido',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Validar que la evaluación existe y el usuario tiene acceso
            evaluacion = EvaluacionEmpresa.objects.get(id=evaluacion_empresa_id)
            
            user = request.user
            if user.rol == 'administrador':
                if evaluacion.administrador != user:
                    return self.error_response(
                        message='No tienes permiso para ver esta evaluación',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            
            # Obtener cálculos de esta evaluación
            from apps.respuestas.models import CalculoNivel
            
            calculos = CalculoNivel.objects.filter(
                evaluacion_empresa=evaluacion,
                activo=True
            ).select_related(
                'dimension',
                'usuario',
                'asignacion'
            ).order_by('dimension__orden', 'usuario__id')
            
            # Construir reporte
            reporte = {
                'evaluacion': {
                    'id': str(evaluacion.id),
                    'nombre': evaluacion.encuesta.nombre,
                    'empresa': evaluacion.empresa.nombre,
                    'fecha_asignacion': evaluacion.fecha_asignacion,
                    'fecha_limite': evaluacion.fecha_limite,
                    'estado': evaluacion.estado,
                    'porcentaje_avance': float(evaluacion.porcentaje_avance),
                },
                'resumen': {
                    'total_dimensiones': evaluacion.total_dimensiones,
                    'dimensiones_evaluadas': calculos.values('dimension').distinct().count(),
                    'total_usuarios': calculos.values('usuario').distinct().count(),
                    'nivel_deseado_promedio': float(calculos.aggregate(Avg('nivel_deseado'))['nivel_deseado__avg'] or 0),
                    'nivel_actual_promedio': float(calculos.aggregate(Avg('nivel_actual'))['nivel_actual__avg'] or 0),
                    'gap_promedio': float(calculos.aggregate(Avg('gap'))['gap__avg'] or 0),
                    'porcentaje_cumplimiento_promedio': float(calculos.aggregate(Avg('porcentaje_cumplimiento'))['porcentaje_cumplimiento__avg'] or 0),
                },
                'por_dimension': self._agrupar_por_dimension_evaluacion(calculos, evaluacion),
                'por_usuario': self._agrupar_por_usuario_evaluacion(calculos),
                'clasificaciones_gap': self._contar_clasificaciones(calculos),
                'distribucion_respuestas': self._calcular_distribucion_respuestas(calculos),
            }
            
            # ========================================================
            # 📤 LOG CRÍTICO - AGREGAR AQUÍ
            # ========================================================
            print("\n" + "="*60)
            print("📤 VERIFICACIÓN FINAL ANTES DE ENVIAR AL FRONTEND:")
            print("="*60)
            
            for dim in reporte['por_dimension']:
                print(f"\n✅ {dim['dimension']['nombre']}:")
                print(f"   total_proyectos: {dim.get('total_proyectos', '❌ MISSING')}")
                print(f"   tiene_proyecto_activo: {dim.get('tiene_proyecto_activo', '❌ MISSING')}")
                print(f"   proyecto_id: {dim.get('proyecto_id', '❌ MISSING')}")
                print(f"   total_usuarios: {len(dim.get('usuarios', []))}")
            
            print("\n" + "="*60)
            print("📤 ESTRUCTURA COMPLETA (primer dimension):")
            import json
            if reporte['por_dimension']:
                primer_dim = reporte['por_dimension'][0]
                print(json.dumps({
                    'dimension': primer_dim['dimension'],
                    'total_proyectos': primer_dim.get('total_proyectos', 'MISSING'),
                    'total_usuarios': len(primer_dim.get('usuarios', [])),
                    'keys': list(primer_dim.keys())
                }, indent=2, default=str))
            print("="*60 + "\n")
            # ========================================================
            
            return self.success_response(
                data=reporte,
                message='Reporte de evaluación generado exitosamente'
            )
        
        except EvaluacionEmpresa.DoesNotExist:
            return self.error_response(
                message='Evaluación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.error_response(
                message='Error al generar reporte',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='listar_por_dimension')
    def listar_por_dimension(self, request):
        """
        Listar proyectos por dimensión
        GET /api/proyectos-remediacion/listar_por_dimension/?dimension_id=xxx
        """
        dimension_id = request.query_params.get('dimension_id')
        
        if not dimension_id:
            return Response(
                {'error': 'dimension_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener todos los calculos de esta dimensión
        from apps.respuestas.models import CalculoNivel
        calculos_ids = CalculoNivel.objects.filter(
            dimension_id=dimension_id,
            activo=True
        ).values_list('id', flat=True)
        
        # Filtrar proyectos
        queryset = self.get_queryset().filter(
            calculo_nivel_id__in=calculos_ids
        )
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': queryset.count()
            }
        })
    
    def _agrupar_por_dimension_evaluacion(self, calculos, evaluacion):
        """Agrupa cálculos por dimensión para una evaluación incluyendo usuarios individuales"""
        from apps.encuestas.models import ConfigNivelDeseado
        from django.db.models import Avg, Count
        from apps.proyectos_remediacion.models import ProyectoCierreBrecha
        from apps.respuestas.models import Respuesta
        
        dimensiones_ids = calculos.values_list('dimension_id', flat=True).distinct()
        dimensiones = evaluacion.encuesta.dimensiones.filter(id__in=dimensiones_ids, activo=True)
        
        resultado = []
        
        for dimension in dimensiones:
            calculos_dim = calculos.filter(dimension=dimension).select_related('usuario', 'asignacion')
            
            if not calculos_dim.exists():
                continue
            
            # --- ✅ CONTEO CORRECTO: Proyectos de TODOS los usuarios ---
            # Obtener IDs de todos los cálculos de esta dimensión
            calculos_ids = list(calculos_dim.values_list('id', flat=True))
            
            # Contar proyectos asociados a CUALQUIER cálculo de esta dimensión
            total_proyectos = ProyectoCierreBrecha.objects.filter(
                calculo_nivel_id__in=calculos_ids,  # ← TODOS los cálculos
                activo=True
            ).count()
            
            # Verificar si hay algún proyecto activo
            proyecto_activo = ProyectoCierreBrecha.objects.filter(
                calculo_nivel_id__in=calculos_ids,
                estado__in=['planificado', 'en_ejecucion', 'en_validacion'],
                activo=True
            ).first()
            
            print(f"🔍 Dimensión {dimension.nombre}:")
            print(f"  - Total cálculos: {len(calculos_ids)}")
            print(f"  - Total proyectos: {total_proyectos}")
            print(f"  - IDs cálculos: {calculos_ids}")
            
            # --- ESTADÍSTICAS AGREGADAS ---
            stats = calculos_dim.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                total_usuarios=Count('usuario', distinct=True),
            )
            
            # --- NIVEL DESEADO ---
            try:
                config = ConfigNivelDeseado.objects.get(
                    evaluacion_empresa=evaluacion,
                    dimension=dimension,
                    activo=True
                )
                nivel_deseado = float(config.nivel_deseado)
            except ConfigNivelDeseado.DoesNotExist:
                nivel_deseado = 3.0
            
            # --- ✅ CONSTRUIR ARRAY DE USUARIOS ---
            usuarios_data = []
            
            for calculo in calculos_dim:
                # Obtener respuestas del usuario
                respuestas = Respuesta.objects.filter(
                    asignacion=calculo.asignacion,
                    pregunta__dimension=dimension,
                    estado__in=['enviado', 'modificado_admin'],
                    activo=True
                ).select_related('pregunta')
                
                # Contar tipos de respuesta
                respuestas_resumen = {
                    'si_cumple': respuestas.filter(respuesta='SI_CUMPLE').count(),
                    'cumple_parcial': respuestas.filter(respuesta='CUMPLE_PARCIAL').count(),
                    'no_cumple': respuestas.filter(respuesta='NO_CUMPLE').count(),
                    'no_aplica': respuestas.filter(respuesta='NO_APLICA').count(),
                }
                
                usuarios_data.append({
                    'usuario_id': calculo.usuario.id,
                    'usuario_nombre': calculo.usuario.nombre_completo or calculo.usuario.email,
                    'nivel_actual': float(calculo.nivel_actual),
                    'gap': float(calculo.gap),
                    'clasificacion_gap': calculo.clasificacion_gap,
                    'clasificacion_gap_display': calculo.get_clasificacion_gap_display(),
                    'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
                    'total_preguntas': calculo.total_preguntas,
                    'calculo_nivel_id': str(calculo.id),  # ← CRÍTICO
                    'respuestas': respuestas_resumen,
                })
            
            # --- ✅ RESULTADO FINAL ---
            resultado.append({
                'dimension': {
                    'id': str(dimension.id),
                    'codigo': dimension.codigo,
                    'nombre': dimension.nombre,
                    'orden': dimension.orden,
                },
                'nivel_deseado': nivel_deseado,
                'nivel_actual_promedio': float(stats['nivel_actual_avg'] or 0),
                'gap_promedio': float(stats['gap_avg'] or 0),
                'porcentaje_cumplimiento_promedio': float(stats['cumplimiento_avg'] or 0),
                'total_usuarios_evaluados': stats['total_usuarios'],
                'tiene_proyecto_activo': proyecto_activo is not None,
                'proyecto_id': str(proyecto_activo.id) if proyecto_activo else None,
                'total_proyectos': total_proyectos,  # ← Conteo correcto
                'usuarios': usuarios_data,  # ← Array de usuarios
            })
        
        return sorted(resultado, key=lambda x: x['dimension']['orden'])


    def _agrupar_por_usuario_evaluacion(self, calculos):
        """Agrupa cálculos por usuario"""
        from django.db.models import Avg, Count
        
        usuarios_ids = calculos.values_list('usuario_id', flat=True).distinct()
        
        from apps.usuarios.models import Usuario
        usuarios = Usuario.objects.filter(id__in=usuarios_ids).order_by('id')  # ⭐ CAMBIAR
        
        resultado = []
        
        for usuario in usuarios:
            calculos_usuario = calculos.filter(usuario=usuario).order_by('dimension__orden') 
                
            stats = calculos_usuario.aggregate(
                nivel_actual_avg=Avg('nivel_actual'),
                gap_avg=Avg('gap'),
                cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                total_dimensiones=Count('dimension', distinct=True),
            )
            
            # Detalle por dimensión
            dimensiones_detalle = []
            for calculo in calculos_usuario.order_by('dimension__orden'):
                dimensiones_detalle.append({
                    'dimension_id': str(calculo.dimension.id),
                    'dimension_codigo': calculo.dimension.codigo,
                    'dimension_nombre': calculo.dimension.nombre,
                    'nivel_deseado': float(calculo.nivel_deseado),
                    'nivel_actual': float(calculo.nivel_actual),
                    'gap': float(calculo.gap),
                    'clasificacion_gap': calculo.clasificacion_gap,
                    'porcentaje_cumplimiento': float(calculo.porcentaje_cumplimiento),
                })
            
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
                'dimensiones': dimensiones_detalle,
            })
        
        return resultado

    def _calcular_distribucion_respuestas(self, calculos):
        """Calcula la distribución de tipos de respuestas"""
        from django.db.models import Sum
        
        totales = calculos.aggregate(
            total_si_cumple=Sum('respuestas_si_cumple'),
            total_cumple_parcial=Sum('respuestas_cumple_parcial'),
            total_no_cumple=Sum('respuestas_no_cumple'),
            total_no_aplica=Sum('respuestas_no_aplica'),
        )
        
        total = sum([
            totales['total_si_cumple'] or 0,
            totales['total_cumple_parcial'] or 0,
            totales['total_no_cumple'] or 0,
            totales['total_no_aplica'] or 0,
        ])
        
        return {
            'si_cumple': totales['total_si_cumple'] or 0,
            'cumple_parcial': totales['total_cumple_parcial'] or 0,
            'no_cumple': totales['total_no_cumple'] or 0,
            'no_aplica': totales['total_no_aplica'] or 0,
            'total': total,
            'porcentajes': {
                'si_cumple': round((totales['total_si_cumple'] or 0) / total * 100, 2) if total > 0 else 0,
                'cumple_parcial': round((totales['total_cumple_parcial'] or 0) / total * 100, 2) if total > 0 else 0,
                'no_cumple': round((totales['total_no_cumple'] or 0) / total * 100, 2) if total > 0 else 0,
                'no_aplica': round((totales['total_no_aplica'] or 0) / total * 100, 2) if total > 0 else 0,
            }
        }
        
    def _contar_clasificaciones(self, calculos):
        """Cuenta las clasificaciones de GAP"""
        return {
            'critico': calculos.filter(clasificacion_gap='critico').count(),
            'alto': calculos.filter(clasificacion_gap='alto').count(),
            'medio': calculos.filter(clasificacion_gap='medio').count(),
            'bajo': calculos.filter(clasificacion_gap='bajo').count(),
            'cumplido': calculos.filter(clasificacion_gap='cumplido').count(),
            'superado': calculos.filter(clasificacion_gap='superado').count(),
        }
    # ════════════════════════════════════════════════════════════════════
    # EXPORTAR PDF - RESUMEN
    # ════════════════════════════════════════════════════════════════════
    
    @action(detail=False, methods=['get'])
    def export_excel_completo(self, request):
        """
        Exportar Excel completo con todas las hojas
        GET /api/reportes/export_excel_completo/?evaluacion_empresa_id=xxx
        """
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from io import BytesIO
        from django.http import HttpResponse
        from django.db.models import Avg, Count
        
        evaluacion_empresa_id = request.query_params.get('evaluacion_empresa_id')
        
        if not evaluacion_empresa_id:
            return self.error_response(
                message='evaluacion_empresa_id es requerido',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.encuestas.models import EvaluacionEmpresa
            evaluacion = EvaluacionEmpresa.objects.select_related(
                'encuesta', 'empresa', 'administrador'
            ).get(id=evaluacion_empresa_id)
            
            # Validar permisos
            user = request.user
            if user.rol == 'administrador' and evaluacion.administrador != user:
                return self.error_response(
                    message='No tienes permiso para exportar esta evaluación',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            # Obtener cálculos
            calculos = CalculoNivel.objects.filter(
                evaluacion_empresa=evaluacion,
                activo=True
            ).select_related('dimension', 'usuario', 'asignacion')
            
            # Crear workbook
            wb = Workbook()
            
            # Estilos
            header_fill = PatternFill(start_color="1F4788", end_color="1F4788", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True, size=12)
            title_font = Font(bold=True, size=14)
            center_align = Alignment(horizontal="center", vertical="center")
            
            # ═══════════════════════════════════════════════════════
            # HOJA 1: RESUMEN GENERAL
            # ═══════════════════════════════════════════════════════
            ws1 = wb.active
            ws1.title = "Resumen General"
            
            # Título
            ws1['A1'] = "REPORTE DE EVALUACIÓN CMMI"
            ws1['A1'].font = title_font
            ws1.merge_cells('A1:B1')
            
            ws1['A2'] = f"Evaluación: {evaluacion.encuesta.nombre}"
            ws1['A3'] = f"Empresa: {evaluacion.empresa.nombre}"
            ws1['A4'] = f"Fecha: {evaluacion.fecha_asignacion.strftime('%d/%m/%Y')}"
            
            # Métricas
            ws1['A6'] = "Métrica"
            ws1['B6'] = "Valor"
            ws1['A6'].fill = header_fill
            ws1['B6'].fill = header_fill
            ws1['A6'].font = header_font
            ws1['B6'].font = header_font
            
            nivel_deseado_avg = calculos.aggregate(Avg('nivel_deseado'))['nivel_deseado__avg'] or 0
            nivel_actual_avg = calculos.aggregate(Avg('nivel_actual'))['nivel_actual__avg'] or 0
            gap_avg = calculos.aggregate(Avg('gap'))['gap__avg'] or 0
            cumplimiento_avg = calculos.aggregate(Avg('porcentaje_cumplimiento'))['porcentaje_cumplimiento__avg'] or 0
            
            ws1['A7'] = "Nivel Deseado Promedio"
            ws1['B7'] = round(nivel_deseado_avg, 2)
            
            ws1['A8'] = "Nivel Actual Promedio"
            ws1['B8'] = round(nivel_actual_avg, 2)
            
            ws1['A9'] = "GAP Promedio"
            ws1['B9'] = round(gap_avg, 2)
            
            ws1['A10'] = "% Cumplimiento Promedio"
            ws1['B10'] = round(cumplimiento_avg, 2)
            
            ws1['A11'] = "Total Dimensiones"
            ws1['B11'] = calculos.values('dimension').distinct().count()
            
            ws1['A12'] = "Total Usuarios"
            ws1['B12'] = calculos.values('usuario').distinct().count()
            
            # Ajustar anchos
            ws1.column_dimensions['A'].width = 30
            ws1.column_dimensions['B'].width = 15
            
            # ═══════════════════════════════════════════════════════
            # HOJA 2: DIMENSIONES
            # ═══════════════════════════════════════════════════════
            ws2 = wb.create_sheet("Dimensiones")
            
            headers = ["Código", "Dimensión", "Nivel Deseado", "Nivel Actual", "GAP", "% Cumplimiento", "Usuarios"]
            ws2.append(headers)
            
            # Aplicar estilo a headers
            for col_num, _ in enumerate(headers, 1):
                cell = ws2.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align
            
            # Datos por dimensión
            dimensiones_ids = calculos.values_list('dimension_id', flat=True).distinct()
            for dimension_id in dimensiones_ids:
                calculos_dim = calculos.filter(dimension_id=dimension_id)
                dimension = calculos_dim.first().dimension
                
                stats = calculos_dim.aggregate(
                    nivel_actual_avg=Avg('nivel_actual'),
                    gap_avg=Avg('gap'),
                    cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                    total_usuarios=Count('usuario', distinct=True)
                )
                
                ws2.append([
                    dimension.codigo,
                    dimension.nombre,
                    float(calculos_dim.first().nivel_deseado),
                    round(stats['nivel_actual_avg'] or 0, 2),
                    round(stats['gap_avg'] or 0, 2),
                    round(stats['cumplimiento_avg'] or 0, 2),
                    stats['total_usuarios']
                ])
            
            # Ajustar anchos
            ws2.column_dimensions['A'].width = 12
            ws2.column_dimensions['B'].width = 35
            ws2.column_dimensions['C'].width = 15
            ws2.column_dimensions['D'].width = 15
            ws2.column_dimensions['E'].width = 10
            ws2.column_dimensions['F'].width = 18
            ws2.column_dimensions['G'].width = 12
            
            # ═══════════════════════════════════════════════════════
            # HOJA 3: USUARIOS
            # ═══════════════════════════════════════════════════════
            ws3 = wb.create_sheet("Usuarios")
            
            headers = ["Usuario", "Email", "Cargo", "Nivel Actual", "GAP", "% Cumplimiento", "Dimensiones"]
            ws3.append(headers)
            
            for col_num, _ in enumerate(headers, 1):
                cell = ws3.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align
            
            usuarios_ids = calculos.values_list('usuario_id', flat=True).distinct()
            from apps.usuarios.models import Usuario
            usuarios = Usuario.objects.filter(id__in=usuarios_ids)
            
            for usuario in usuarios:
                calculos_usuario = calculos.filter(usuario=usuario)
                
                stats = calculos_usuario.aggregate(
                    nivel_actual_avg=Avg('nivel_actual'),
                    gap_avg=Avg('gap'),
                    cumplimiento_avg=Avg('porcentaje_cumplimiento'),
                    total_dimensiones=Count('dimension', distinct=True)
                )
                
                ws3.append([
                    usuario.nombre_completo,
                    usuario.email,
                    usuario.cargo or 'N/A',
                    round(stats['nivel_actual_avg'] or 0, 2),
                    round(stats['gap_avg'] or 0, 2),
                    round(stats['cumplimiento_avg'] or 0, 2),
                    stats['total_dimensiones']
                ])
            
            ws3.column_dimensions['A'].width = 25
            ws3.column_dimensions['B'].width = 30
            ws3.column_dimensions['C'].width = 20
            ws3.column_dimensions['D'].width = 15
            ws3.column_dimensions['E'].width = 10
            ws3.column_dimensions['F'].width = 18
            ws3.column_dimensions['G'].width = 15
            
            # ═══════════════════════════════════════════════════════
            # HOJA 4: CLASIFICACIÓN GAPs
            # ═══════════════════════════════════════════════════════
            ws4 = wb.create_sheet("Clasificación GAP")
            
            headers = ["Clasificación", "Cantidad"]
            ws4.append(headers)
            
            for col_num, _ in enumerate(headers, 1):
                cell = ws4.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align
            
            clasificaciones = {
                'Crítico': calculos.filter(clasificacion_gap='critico').count(),
                'Alto': calculos.filter(clasificacion_gap='alto').count(),
                'Medio': calculos.filter(clasificacion_gap='medio').count(),
                'Bajo': calculos.filter(clasificacion_gap='bajo').count(),
                'Cumplido': calculos.filter(clasificacion_gap='cumplido').count(),
                'Superado': calculos.filter(clasificacion_gap='superado').count(),
            }
            
            for clasificacion, cantidad in clasificaciones.items():
                ws4.append([clasificacion, cantidad])
            
            ws4.column_dimensions['A'].width = 20
            ws4.column_dimensions['B'].width = 15
            
            # ═══════════════════════════════════════════════════════
            # GUARDAR Y ENVIAR
            # ═══════════════════════════════════════════════════════
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f'Reporte_Evaluacion_{evaluacion.empresa.nombre}_{evaluacion_empresa_id}.xlsx'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
        
        except EvaluacionEmpresa.DoesNotExist:
            return self.error_response(
                message='Evaluación no encontrada',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.error_response(
                message='Error al generar Excel',
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )