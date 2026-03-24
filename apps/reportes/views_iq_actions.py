# apps/reportes/views_iq_actions.py
"""
Actions IQ para agregar al ReporteViewSet existente.

Pega estos métodos dentro de la clase ReporteViewSet en apps/reportes/views.py,
y agrega al import:
    from .services_iq import ReporteGAPIQService
    from .exporters_iq import PDFExporterIQ, ExcelExporterIQ
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response


# ──────────────────────────────────────────────────────────────────────────────
# Agrega estos 4 métodos dentro de ReporteViewSet
# ──────────────────────────────────────────────────────────────────────────────

def gap_evaluacion_iq(self, request):
    """
    GET /api/reportes/gap_evaluacion_iq/?asignacion_id={id}

    Genera reporte GAP completo para una AsignacionEvaluacionIQ auditada.
    Incluye brechas_identificadas para planificación de remediación.
    """
    from .services_iq import ReporteGAPIQService
    from apps.asignaciones_iq.models import AsignacionEvaluacionIQ

    asignacion_id = request.query_params.get('asignacion_id')

    if not asignacion_id:
        return self.error_response(
            message='Parámetro asignacion_id es requerido',
            status_code=status.HTTP_400_BAD_REQUEST
        )

    try:
        asignacion = AsignacionEvaluacionIQ.objects.select_related(
            'empresa', 'usuario_asignado'
        ).get(id=asignacion_id)
    except AsignacionEvaluacionIQ.DoesNotExist:
        return self.error_response(
            message='Asignación no encontrada',
            status_code=status.HTTP_404_NOT_FOUND
        )

    # Permisos
    user = request.user
    if user.rol == 'administrador':
        if asignacion.empresa != user.empresa:
            return self.error_response(
                message='No tienes permiso para ver esta asignación',
                status_code=status.HTTP_403_FORBIDDEN
            )
    elif user.rol not in ['superadmin', 'auditor']:
        # Usuario normal solo puede ver su propio reporte
        if asignacion.usuario_asignado != user:
            return self.error_response(
                message='No tienes permiso para ver este reporte',
                status_code=status.HTTP_403_FORBIDDEN
            )

    try:
        reporte = ReporteGAPIQService.obtener_reporte_asignacion(int(asignacion_id))
        return self.success_response(
            data=reporte,
            message='Reporte IQ generado exitosamente'
        )
    except ValueError as e:
        return self.error_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return self.error_response(
            message='Error al generar reporte IQ',
            errors=str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def listar_evaluaciones_iq(self, request):
    """
    GET /api/reportes/listar_evaluaciones_iq/?empresa_id={id}

    Lista todas las asignaciones IQ auditadas de una empresa.
    Usado por el selector del frontend.
    """
    from .services_iq import ReporteGAPIQService

    empresa_id = request.query_params.get('empresa_id')
    if not empresa_id:
        return self.error_response(
            message='empresa_id es requerido',
            status_code=status.HTTP_400_BAD_REQUEST
        )

    user = request.user
    if user.rol == 'administrador':
        if str(user.empresa.id) != str(empresa_id):
            return self.error_response(
                message='Sin permisos para esta empresa',
                status_code=status.HTTP_403_FORBIDDEN
            )

    try:
        data = ReporteGAPIQService.obtener_reportes_empresa(empresa_id)
        return self.success_response(data={'asignaciones': data})
    except Exception as e:
        return self.error_response(message=str(e), status_code=500)


def export_pdf_evaluacion_iq(self, request):
    """
    GET /api/reportes/export_pdf_evaluacion_iq/?asignacion_id={id}
    """
    from .services_iq import ReporteGAPIQService
    from .exporters_iq import PDFExporterIQ
    from apps.asignaciones_iq.models import AsignacionEvaluacionIQ, CalculoNivelIQ

    asignacion_id = request.query_params.get('asignacion_id')
    if not asignacion_id:
        return self.error_response(message='asignacion_id es requerido', status_code=400)

    try:
        asignacion = AsignacionEvaluacionIQ.objects.select_related(
            'evaluacion', 'empresa', 'usuario_asignado', 'auditado_por'
        ).get(id=asignacion_id)

        calculos = CalculoNivelIQ.objects.filter(asignacion=asignacion)

        exporter = PDFExporterIQ(asignacion, calculos)
        return exporter.export()

    except AsignacionEvaluacionIQ.DoesNotExist:
        return self.error_response(message='Asignación no encontrada', status_code=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return self.error_response(message='Error al generar PDF', errors=str(e), status_code=500)


def export_excel_evaluacion_iq(self, request):
    """
    GET /api/reportes/export_excel_evaluacion_iq/?asignacion_id={id}
    """
    from .exporters_iq import ExcelExporterIQ
    from apps.asignaciones_iq.models import AsignacionEvaluacionIQ, CalculoNivelIQ

    asignacion_id = request.query_params.get('asignacion_id')
    if not asignacion_id:
        return self.error_response(message='asignacion_id es requerido', status_code=400)

    try:
        asignacion = AsignacionEvaluacionIQ.objects.select_related(
            'evaluacion', 'empresa', 'usuario_asignado', 'auditado_por'
        ).get(id=asignacion_id)

        calculos = CalculoNivelIQ.objects.filter(asignacion=asignacion)

        exporter = ExcelExporterIQ(asignacion, calculos)
        return exporter.export()

    except AsignacionEvaluacionIQ.DoesNotExist:
        return self.error_response(message='Asignación no encontrada', status_code=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return self.error_response(message='Error al generar Excel', errors=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────────
# INSTRUCCIONES DE INTEGRACIÓN
# ──────────────────────────────────────────────────────────────────────────────
#
# En apps/reportes/views.py, dentro de ReporteViewSet agrega:
#
#   @action(detail=False, methods=['get'])
#   def gap_evaluacion_iq(self, request):
#       from .views_iq_actions import gap_evaluacion_iq
#       return gap_evaluacion_iq(self, request)
#
#   @action(detail=False, methods=['get'])
#   def listar_evaluaciones_iq(self, request):
#       from .views_iq_actions import listar_evaluaciones_iq
#       return listar_evaluaciones_iq(self, request)
#
#   @action(detail=False, methods=['get'])
#   def export_pdf_evaluacion_iq(self, request):
#       from .views_iq_actions import export_pdf_evaluacion_iq
#       return export_pdf_evaluacion_iq(self, request)
#
#   @action(detail=False, methods=['get'])
#   def export_excel_evaluacion_iq(self, request):
#       from .views_iq_actions import export_excel_evaluacion_iq
#       return export_excel_evaluacion_iq(self, request)
#